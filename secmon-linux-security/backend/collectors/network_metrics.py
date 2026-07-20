"""Zero-privilege network metrics collector for SecMon ATD-A.

Reads cumulative kernel counters from ``/proc/net/dev``, ``/proc/net/sockstat``,
``/proc/net/sockstat6`` and interface metadata from ``/sys/class/net/*``.  No
``CAP_NET_ADMIN`` / ``CAP_NET_RAW`` is required and no subprocess is spawned, so
the collector runs unprivileged under the existing ``secmon-collector.service``.

Raw counter values are stored verbatim; per-second rates are derived by the API
via per-interface differencing (see ``GET /api/v1/network/traffic-series``).
"""

from __future__ import annotations

import logging
import socket
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Linux interface statistics columns exposed by /proc/net/dev, in kernel order.
# See Documentation/networking/statistics.rst: the 16 counters follow the
# "interface | rx_bytes rx_packets rx_errs rx_drop ... | tx_bytes ..." layout.
_RX_KEYS: tuple[str, ...] = ("rx_bytes", "rx_packets", "rx_errors", "rx_drops")
_TX_KEYS: tuple[str, ...] = ("tx_bytes", "tx_packets", "tx_errors", "tx_drops")

_DB_LOCK_RETRIES = 3
_DB_LOCK_RETRY_DELAY = 0.2


@dataclass(slots=True)
class InterfaceSample:
    """One observation of one interface for one sampling round."""

    name: str
    ifindex: int | None
    mac_address: str | None
    is_loopback: bool
    is_virtual: bool
    is_up: bool
    mtu: int | None
    counters: dict[str, int | None]


def _safe_int(value: str) -> int | None:
    """Parse a kernel counter as int; return None on any malformation."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_proc_net_dev(text: str) -> dict[str, dict[str, int | None]]:
    """Parse ``/proc/net/dev`` into ``{interface: {counter: value}}``.

    The two header lines are ignored.  Each data line has the form
    ``"ifname: rx0 rx1 ... rx15 tx0 tx1 ... tx15"``.  Only the four rx and four
    tx counters we persist are extracted; the remaining columns are skipped
    without being named, which keeps parsing resilient to kernel additions.
    """
    samples: dict[str, dict[str, int | None]] = {}
    for raw in text.splitlines()[2:]:
        if ":" not in raw:
            continue
        name_part, values_part = raw.split(":", 1)
        name = name_part.strip()
        if not name:
            continue
        tokens = values_part.split()
        if len(tokens) < 16:
            # Not enough columns to read both rx and tx groups safely.
            samples[name] = {key: None for key in (*_RX_KEYS, *_TX_KEYS)}
            continue
        counters: dict[str, int | None] = {}
        for key, token in zip(_RX_KEYS, tokens[0:4], strict=True):
            counters[key] = _safe_int(token)
        # tx counters occupy columns 8..11 (after the 8 rx columns).
        for key, token in zip(_TX_KEYS, tokens[8:12], strict=True):
            counters[key] = _safe_int(token)
        samples[name] = counters
    return samples


def parse_sockstat_inuse(text: str) -> tuple[int | None, int | None]:
    """Return ``(tcp_inuse, udp_inuse)`` from ``/proc/net/sockstat`` text.

    Accepts both the IPv4 labels (``TCP:`` / ``UDP:``) and the IPv6 variants
    (``TCP6:`` / ``UDP6:``).  Returns ``(None, None)`` if the relevant line is
    absent or malformed so a partial read degrades gracefully instead of
    aborting the round.
    """
    tcp_inuse: int | None = None
    udp_inuse: int | None = None
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("TCP"):
            tcp_inuse = _first_int_field(stripped)
        elif upper.startswith("UDP"):
            udp_inuse = _first_int_field(stripped)
    return tcp_inuse, udp_inuse


def _first_int_field(line: str) -> int | None:
    """Extract the first integer following the ``inuse`` token in a sockstat line."""
    # Lines look like "TCP: inuse 14 orphan 0 ..." -> the int after "inuse".
    parts = line.split()
    for idx, token in enumerate(parts):
        if token.lower() == "inuse" and idx + 1 < len(parts):
            return _safe_int(parts[idx + 1])
    return None


def _read_text(path: Path) -> str | None:
    """Read a file; return None on missing/unreadable so callers can degrade."""
    try:
        return path.read_text()
    except FileNotFoundError:
        return None
    except OSError as exc:  # permission denied, I/O error, ...
        logger.debug("Could not read %s: %s", path, exc)
        return None


class NetworkMetricsCollector:
    """Collect zero-privilege network counter samples into ``network_samples``."""

    _source_name = "Network Metrics"
    COLLECTOR_VERSION = "atd-a-1.0"

    def __init__(
        self,
        database_path: Path | None = None,
        settings: Settings | None = None,
        *,
        proc_root: Path = Path("/proc/net"),
        sys_root: Path = Path("/sys/class/net"),
    ) -> None:
        self.settings = settings or get_settings()
        self.database_path = Path(
            database_path or str(self._setting_value("database_path", "./var/secmon.db"))
        )
        self._proc_root = proc_root
        self._sys_root = sys_root
        self._hostname = socket.gethostname()
        self._last_sampled_at: datetime | None = None

    def _setting_value(self, name: str, default: object | None = None) -> object:
        """Read a setting while remaining compatible with mocked settings objects."""
        if isinstance(self.settings, Settings):
            return getattr(self.settings, name)
        return vars(self.settings).get(name, default)

    # ------------------------------------------------------------------ sources

    def _observe_interfaces(self) -> list[InterfaceSample]:
        """Read interface counters and metadata; never raise on partial failure."""
        dev_text = _read_text(self._proc_root / "dev") or ""
        counters_by_iface = parse_proc_net_dev(dev_text)

        try:
            entries = sorted(self._sys_root.iterdir()) if self._sys_root.is_dir() else []
        except OSError:
            entries = []

        samples: list[InterfaceSample] = []
        for entry in entries:
            name = entry.name
            ifindex = _safe_int((_read_text(entry / "ifindex") or "").strip())
            mac = (_read_text(entry / "address") or "").strip() or None
            is_loopback = name == "lo"
            is_virtual = (entry / "virtual").exists()
            operstate = (_read_text(entry / "operstate") or "").strip()
            # Unknown operstate (common for loopback / virtual) is treated as down
            # unless explicitly "up"; callers can still see counters regardless.
            is_up = operstate == "up"
            mtu_text = (_read_text(entry / "mtu") or "").strip()
            mtu = _safe_int(mtu_text)
            counters = counters_by_iface.get(
                name, {key: None for key in (*_RX_KEYS, *_TX_KEYS)}
            )
            samples.append(
                InterfaceSample(
                    name=name,
                    ifindex=ifindex,
                    mac_address=mac,
                    is_loopback=is_loopback,
                    is_virtual=is_virtual,
                    is_up=is_up,
                    mtu=mtu,
                    counters=counters,
                )
            )
        return samples

    def _socket_summary(self) -> tuple[int | None, int | None]:
        """Combine IPv4 and IPv6 sockstat into host-level tcp/udp inuse counts."""
        v4_text = _read_text(self._proc_root / "sockstat") or ""
        v6_text = _read_text(self._proc_root / "sockstat6") or ""
        tcp4, udp4 = parse_sockstat_inuse(v4_text)
        tcp6, udp6 = parse_sockstat_inuse(v6_text)
        active_tcp = _sum_optional(tcp4, tcp6)
        active_udp = _sum_optional(udp4, udp6)
        return active_tcp, active_udp

    # ------------------------------------------------------------------- writes

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _upsert_interface(self, conn: sqlite3.Connection, sample: InterfaceSample) -> int:
        """Insert or update an interface row; return its surrogate id."""
        row = conn.execute(
            "SELECT id FROM network_interfaces WHERE name = ? AND ifindex IS ?",
            (sample.name, sample.ifindex),
        ).fetchone()
        if row is not None:
            interface_id = int(row[0])
            conn.execute(
                "UPDATE network_interfaces SET mac_address = ?, is_loopback = ?, "
                "is_virtual = ?, is_up = ?, mtu = ?, last_seen_at = CURRENT_TIMESTAMP, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    sample.mac_address,
                    int(sample.is_loopback),
                    int(sample.is_virtual),
                    int(sample.is_up),
                    sample.mtu,
                    interface_id,
                ),
            )
            return interface_id
        cursor = conn.execute(
            "INSERT INTO network_interfaces "
            "(name, ifindex, mac_address, is_loopback, is_virtual, is_up, mtu) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                sample.name,
                sample.ifindex,
                sample.mac_address,
                int(sample.is_loopback),
                int(sample.is_virtual),
                int(sample.is_up),
                sample.mtu,
            ),
        )
        if cursor.lastrowid is None:  # pragma: no cover - insert always returns a rowid
            raise RuntimeError("network_interfaces insert returned no rowid")
        return int(cursor.lastrowid)

    def collect_once(self) -> tuple[int, int]:
        """Run one sampling round; return ``(samples_written, interface_count)``.

        - The loopback interface is recorded but not sampled, to avoid noise.
        - A repeated call within the same wall-clock second is a no-op to guard
          against accidental double scheduling; the guard resets on restart.
        - Database lock contention is retried a bounded number of times; an
          unrecoverable lock logs a warning and the round is skipped (never
          raises into the host collector loop).
        """
        sampled_at = datetime.now(UTC).replace(microsecond=0)
        if self._last_sampled_at is not None and sampled_at <= self._last_sampled_at:
            logger.debug("Skipping duplicate network sample within the same second")
            return (0, 0)
        self._last_sampled_at = sampled_at

        observed = self._observe_interfaces()
        active_tcp, active_udp = self._socket_summary()
        sampled_at_iso = sampled_at.isoformat()

        written = 0
        conn: sqlite3.Connection | None = None
        for attempt in range(_DB_LOCK_RETRIES):
            try:
                conn = self._open_connection()
                break
            except sqlite3.OperationalError as exc:
                if attempt + 1 < _DB_LOCK_RETRIES:
                    logger.debug("Database locked on open (attempt %d): %s", attempt + 1, exc)
                    continue
                logger.warning("Could not open DB after %d attempts: %s", _DB_LOCK_RETRIES, exc)
                return (0, len(observed))

        try:
            assert conn is not None  # for mypy; loop above guarantees it on this path
            for sample in observed:
                interface_id = self._upsert_interface(conn, sample)
                if sample.is_loopback:
                    # Record the interface but skip traffic sampling for loopback.
                    continue
                conn.execute(
                    "INSERT INTO network_samples "
                    "(interface_id, sampled_at, sensor_host, rx_bytes, tx_bytes, "
                    "rx_packets, tx_packets, rx_errors, tx_errors, rx_drops, tx_drops, "
                    "active_tcp, active_udp, source, collector_version) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        interface_id,
                        sampled_at_iso,
                        self._hostname,
                        sample.counters.get("rx_bytes"),
                        sample.counters.get("tx_bytes"),
                        sample.counters.get("rx_packets"),
                        sample.counters.get("tx_packets"),
                        sample.counters.get("rx_errors"),
                        sample.counters.get("tx_errors"),
                        sample.counters.get("rx_drops"),
                        sample.counters.get("tx_drops"),
                        active_tcp,
                        active_udp,
                        "proc",
                        self.COLLECTOR_VERSION,
                    ),
                )
                written += 1
            conn.commit()
        except Exception:
            logger.exception("Failed to persist network samples; rolling back")
            if conn is not None:
                conn.rollback()
        finally:
            if conn is not None:
                conn.close()

        logger.info(
            "network sample round sampled_at=%s interfaces=%d samples=%d",
            sampled_at_iso,
            len(observed),
            written,
        )
        return (written, len(observed))


def _sum_optional(left: int | None, right: int | None) -> int | None:
    """Add two optional ints; if either is missing the sum is unknown."""
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)
