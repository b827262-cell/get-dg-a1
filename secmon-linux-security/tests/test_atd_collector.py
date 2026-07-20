from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.collectors.network_metrics import (
    NetworkMetricsCollector,
    parse_proc_net_dev,
    parse_sockstat_inuse,
)
from database.migrate import migrate


@pytest.fixture
def migrated_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "atd.db"
    migrate(db_path, Path("database/migrations"))
    return db_path


_PROC_NET_DEV_SAMPLE = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0
  eth0: 4294967296 1000 1 2 0 0 0 0 8589934592 2000 3 4 0 0 0 0
tailscale0: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
"""


def test_parse_proc_net_dev_extracts_rx_tx_counters() -> None:
    samples = parse_proc_net_dev(_PROC_NET_DEV_SAMPLE)
    assert set(samples) == {"lo", "eth0", "tailscale0"}
    eth0 = samples["eth0"]
    assert eth0["rx_bytes"] == 4294967296
    assert eth0["rx_packets"] == 1000
    assert eth0["rx_errors"] == 1
    assert eth0["rx_drops"] == 2
    assert eth0["tx_bytes"] == 8589934592
    assert eth0["tx_packets"] == 2000
    assert eth0["tx_errors"] == 3
    assert eth0["tx_drops"] == 4
    # Big counter values survive 32-bit wrap (>= 2**32).
    assert eth0["rx_bytes"] >= 2**32


def test_parse_proc_net_dev_ignores_header_and_blank_lines() -> None:
    text = "header1\nheader2\n\n  eth0: 1 2 3 4 0 0 0 0 5 6 7 8 0 0 0 0\n"
    samples = parse_proc_net_dev(text)
    assert samples == {
        "eth0": {
            "rx_bytes": 1,
            "rx_packets": 2,
            "rx_errors": 3,
            "rx_drops": 4,
            "tx_bytes": 5,
            "tx_packets": 6,
            "tx_errors": 7,
            "tx_drops": 8,
        }
    }


def test_parse_proc_net_dev_short_line_yields_null_counters() -> None:
    # A malformed line with fewer than 16 columns must not raise.
    samples = parse_proc_net_dev("h1\nh2\nweird: 1 2 3\n")
    assert samples == {
        "weird": {
            "rx_bytes": None,
            "rx_packets": None,
            "rx_errors": None,
            "rx_drops": None,
            "tx_bytes": None,
            "tx_packets": None,
            "tx_errors": None,
            "tx_drops": None,
        }
    }


def test_parse_sockstat_inuse_handles_v4_and_v6() -> None:
    tcp, udp = parse_sockstat_inuse("TCP: inuse 14 orphan 0\nUDP: inuse 7\n")
    assert tcp == 14
    assert udp == 7
    # sockstat6 uses the same shape; a partial read returns None for the missing one.
    tcp6, udp6 = parse_sockstat_inuse("TCP6: inuse 3\nUDP6: inuse 1\n")
    assert (tcp6, udp6) == (3, 1)
    none_tcp, none_udp = parse_sockstat_inuse("")
    assert (none_tcp, none_udp) == (None, None)


def _build_fake_sysroot(root: Path, ifaces: dict[str, dict[str, str]]) -> None:
    for name, attrs in ifaces.items():
        iface_dir = root / name
        iface_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in attrs.items():
            (iface_dir / filename).write_text(content)


def _settings(db_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        database_path=db_path,
        network_metrics_enabled=True,
        network_metrics_interval_seconds=5.0,
    )


def test_collect_once_persists_non_loopback_samples(migrated_db: Path, tmp_path: Path) -> None:
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "dev").write_text(_PROC_NET_DEV_SAMPLE)
    (proc / "sockstat").write_text("TCP: inuse 14 orphan 0\nUDP: inuse 7\n")
    (proc / "sockstat6").write_text("TCP6: inuse 3\nUDP6: inuse 1\n")

    sys_root = tmp_path / "sys"
    sys_root.mkdir()
    _build_fake_sysroot(
        sys_root,
        {
            "lo": {"ifindex": "1", "address": "00:00:00:00:00:00", "operstate": "unknown", "mtu": "65536"},
            "eth0": {"ifindex": "2", "address": "aa:bb:cc:dd:ee:ff", "operstate": "up", "mtu": "1500"},
            "tailscale0": {"ifindex": "3", "address": "", "operstate": "up", "mtu": "1280"},
        },
    )
    (sys_root / "tailscale0" / "virtual").mkdir()  # mark tailscale0 as virtual

    collector = NetworkMetricsCollector(
        database_path=migrated_db,
        settings=_settings(migrated_db),
        proc_root=proc,
        sys_root=sys_root,
    )
    written, interface_count = collector.collect_once()
    assert interface_count == 3
    # Only non-loopback interfaces get traffic samples.
    assert written == 2

    with sqlite3.connect(migrated_db) as conn:
        conn.row_factory = sqlite3.Row
        ifaces = {
            row["name"]: dict(row)
            for row in conn.execute("SELECT * FROM network_interfaces")
        }
        assert ifaces["lo"]["is_loopback"] == 1
        assert ifaces["eth0"]["is_up"] == 1
        assert ifaces["eth0"]["mtu"] == 1500
        assert ifaces["tailscale0"]["is_virtual"] == 1
        samples = [
            dict(row)
            for row in conn.execute(
                "SELECT s.*, i.name FROM network_samples s "
                "JOIN network_interfaces i ON i.id = s.interface_id ORDER BY i.name"
            )
        ]
    sampled_names = {row["name"] for row in samples}
    assert sampled_names == {"eth0", "tailscale0"}
    eth0_sample = next(row for row in samples if row["name"] == "eth0")
    assert eth0_sample["rx_bytes"] == 4294967296
    assert eth0_sample["tx_bytes"] == 8589934592
    # active_tcp/udp aggregate v4 + v6 sockstat.
    assert eth0_sample["active_tcp"] == 17  # 14 + 3
    assert eth0_sample["active_udp"] == 8  # 7 + 1
    assert eth0_sample["collector_version"] == NetworkMetricsCollector.COLLECTOR_VERSION
    assert eth0_sample["source"] == "proc"


def test_collect_once_is_idempotent_within_same_second(migrated_db: Path, tmp_path: Path) -> None:
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "dev").write_text("h1\nh2\neth0: 1 2 0 0 0 0 0 0 3 4 0 0 0 0 0 0\n")
    (proc / "sockstat").write_text("TCP: inuse 1\n")
    sys_root = tmp_path / "sys"
    sys_root.mkdir()
    _build_fake_sysroot(
        sys_root, {"eth0": {"ifindex": "2", "operstate": "up", "mtu": "1500", "address": "aa"}}
    )
    collector = NetworkMetricsCollector(
        database_path=migrated_db,
        settings=_settings(migrated_db),
        proc_root=proc,
        sys_root=sys_root,
    )
    first = collector.collect_once()
    second = collector.collect_once()
    assert first[0] == 1
    # Same wall-clock second -> no-op.
    assert second == (0, 0)

    with sqlite3.connect(migrated_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM network_samples").fetchone()[0]
    assert count == 1


def test_missing_proc_files_degrade_gracefully(migrated_db: Path, tmp_path: Path) -> None:
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    # No dev / sockstat files at all.
    sys_root = tmp_path / "sys"
    sys_root.mkdir()
    _build_fake_sysroot(sys_root, {"eth0": {"ifindex": "2", "operstate": "up", "mtu": "1500", "address": "aa"}})
    collector = NetworkMetricsCollector(
        database_path=migrated_db,
        settings=_settings(migrated_db),
        proc_root=proc,
        sys_root=sys_root,
    )
    written, interface_count = collector.collect_once()
    assert interface_count == 1
    assert written == 1
    with sqlite3.connect(migrated_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM network_samples JOIN network_interfaces i ON i.id = interface_id"
        ).fetchone()
    # Counters are null but the row still exists; active_tcp/udp null.
    assert row["rx_bytes"] is None
    assert row["active_tcp"] is None


def test_permission_denied_on_sysfs_is_skipped(migrated_db: Path, tmp_path: Path) -> None:
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "dev").write_text("h1\nh2\neth0: 1 2 0 0 0 0 0 0 3 4 0 0 0 0 0 0\n")
    # sysfs root that is not a directory -> no interfaces observed.
    sys_root = tmp_path / "sys"
    sys_root.write_text("not a dir")
    collector = NetworkMetricsCollector(
        database_path=migrated_db,
        settings=_settings(migrated_db),
        proc_root=proc,
        sys_root=sys_root,
    )
    written, interface_count = collector.collect_once()
    assert interface_count == 0
    assert written == 0


def test_loopback_recorded_but_not_sampled(migrated_db: Path, tmp_path: Path) -> None:
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "dev").write_text("h1\nh2\nlo: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0\n")
    sys_root = tmp_path / "sys"
    sys_root.mkdir()
    _build_fake_sysroot(sys_root, {"lo": {"ifindex": "1", "operstate": "unknown", "mtu": "65536", "address": "00"}})
    collector = NetworkMetricsCollector(
        database_path=migrated_db,
        settings=_settings(migrated_db),
        proc_root=proc,
        sys_root=sys_root,
    )
    written, interface_count = collector.collect_once()
    assert interface_count == 1
    assert written == 0  # loopback produces no sample
    with sqlite3.connect(migrated_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM network_samples").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM network_interfaces").fetchone()[0] == 1


def test_special_interface_names_are_accepted(migrated_db: Path, tmp_path: Path) -> None:
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "dev").write_text(
        "h1\nh2\n"
        "docker0: 1 1 0 0 0 0 0 0 2 2 0 0 0 0 0 0\n"
        "br-abcdef123456: 3 3 0 0 0 0 0 0 4 4 0 0 0 0 0 0\n"
        "veth1234: 5 5 0 0 0 0 0 0 6 6 0 0 0 0 0 0\n"
    )
    sys_root = tmp_path / "sys"
    sys_root.mkdir()
    for name in ("docker0", "br-abcdef123456", "veth1234"):
        _build_fake_sysroot(sys_root, {name: {"ifindex": "5", "operstate": "up", "mtu": "1500", "address": "aa"}})
        (sys_root / name / "virtual").mkdir()
    collector = NetworkMetricsCollector(
        database_path=migrated_db,
        settings=_settings(migrated_db),
        proc_root=proc,
        sys_root=sys_root,
    )
    written, interface_count = collector.collect_once()
    assert interface_count == 3
    assert written == 3


def test_duplicate_round_is_safe_and_resets_after_new_second(
    migrated_db: Path, tmp_path: Path
) -> None:
    """A fresh collector instance (e.g. after restart) resumes writing."""
    proc = tmp_path / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "dev").write_text("h1\nh2\neth0: 1 2 0 0 0 0 0 0 3 4 0 0 0 0 0 0\n")
    sys_root = tmp_path / "sys"
    sys_root.mkdir()
    _build_fake_sysroot(sys_root, {"eth0": {"ifindex": "2", "operstate": "up", "mtu": "1500", "address": "aa"}})

    first = NetworkMetricsCollector(
        database_path=migrated_db, settings=_settings(migrated_db), proc_root=proc, sys_root=sys_root
    )
    first.collect_once()
    # A brand-new instance has no memory of the previous sampled_at -> writes again.
    second = NetworkMetricsCollector(
        database_path=migrated_db, settings=_settings(migrated_db), proc_root=proc, sys_root=sys_root
    )
    second.collect_once()
    with sqlite3.connect(migrated_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM network_samples").fetchone()[0]
    # Two writes because the second instance reset the per-second guard.
    assert count == 2
