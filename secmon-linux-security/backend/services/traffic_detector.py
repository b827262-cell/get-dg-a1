"""Conservative interface-counter anomaly detector (ATD-B).

The detector deliberately accepts only cumulative interface counters.  It never
infers an IP, port, or protocol from them.  State is in memory by design: a
process restart starts a fresh warm-up window and cannot manufacture a baseline.
"""

from __future__ import annotations

import math
import sqlite3
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

STATES = ("NORMAL", "WATCH", "ALERT", "RECOVERING", "RESOLVED")


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    fixed_rate_threshold: float = 0.0
    rolling_window: int = 20
    warmup_samples: int = 5
    deviation_ratio: float = 2.0
    minimum_absolute_delta: float = 0.0
    consecutive_anomalies: int = 3
    consecutive_normals: int = 3
    cooldown_seconds: float = 300.0
    duplicate_suppression_seconds: float = 60.0

    def __post_init__(self) -> None:
        numeric = (self.fixed_rate_threshold, self.deviation_ratio,
                   self.minimum_absolute_delta, self.cooldown_seconds,
                   self.duplicate_suppression_seconds)
        if any(not math.isfinite(x) or x < 0 for x in numeric):
            raise ValueError("detector numeric settings must be finite and non-negative")
        if self.deviation_ratio < 1:
            raise ValueError("deviation_ratio must be at least 1")
        if any(x < 1 for x in (self.rolling_window, self.warmup_samples,
                               self.consecutive_anomalies, self.consecutive_normals)):
            raise ValueError("detector counts must be positive")
        if self.warmup_samples > self.rolling_window:
            raise ValueError("warmup_samples cannot exceed rolling_window")


@dataclass(frozen=True, slots=True)
class CounterSample:
    interface_id: int
    interface: str
    sampled_at: datetime
    rx_bytes: int | float | None
    tx_bytes: int | float | None
    rx_packets: int | float | None
    tx_packets: int | float | None
    ifindex: int | None = None


@dataclass(frozen=True, slots=True)
class RateResult:
    elapsed_seconds: float | None
    bytes_per_sec: float | None
    bits_per_sec: float | None
    packets_per_sec: float | None
    reset: bool = False
    invalid: bool = False


def _valid_counter(value: int | float | None) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(float(value)) and value >= 0


def calculate_rate(previous: CounterSample | None, current: CounterSample) -> RateResult:
    """Calculate aggregate RX+TX bytes, bits, and packets per second safely."""
    if previous is None:
        return RateResult(None, None, None, None)
    if current.sampled_at.tzinfo is None or previous.sampled_at.tzinfo is None:
        return RateResult(None, None, None, None, invalid=True)
    elapsed = (current.sampled_at.astimezone(UTC) - previous.sampled_at.astimezone(UTC)).total_seconds()
    fields = (previous.rx_bytes, previous.tx_bytes, current.rx_bytes, current.tx_bytes,
              previous.rx_packets, previous.tx_packets, current.rx_packets, current.tx_packets)
    if elapsed <= 0 or any(not _valid_counter(value) for value in fields):
        return RateResult(elapsed, None, None, None, invalid=True)
    byte_delta = (float(cast(float, current.rx_bytes)) + float(cast(float, current.tx_bytes))
                  - float(cast(float, previous.rx_bytes)) - float(cast(float, previous.tx_bytes)))
    packet_delta = (float(cast(float, current.rx_packets)) + float(cast(float, current.tx_packets))
                    - float(cast(float, previous.rx_packets)) - float(cast(float, previous.tx_packets)))
    if byte_delta < 0 or packet_delta < 0:
        return RateResult(elapsed, None, None, None, reset=True)
    return RateResult(elapsed, byte_delta / elapsed, byte_delta * 8 / elapsed, packet_delta / elapsed)


@dataclass(slots=True)
class DetectionResult:
    state: str
    rate: RateResult
    baseline: float | None
    threshold: float
    anomalous: bool
    event_kind: str | None = None
    event_key: str | None = None
    count: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)


class InterfaceDetector:
    """One isolated state machine per interface; no cross-interface baseline."""

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self.previous: CounterSample | None = None
        self.baseline_values: deque[float] = deque(maxlen=self.config.rolling_window)
        self.state = "NORMAL"
        self.anomaly_count = 0
        self.normal_count = 0
        self.last_event_at: datetime | None = None
        self.total_anomalies = 0

    def process(self, sample: CounterSample) -> DetectionResult:
        rate = calculate_rate(self.previous, sample)
        self.previous = sample
        if rate.bytes_per_sec is None:
            return DetectionResult(self.state, rate, self._baseline(), self.config.fixed_rate_threshold,
                                   False, evidence={"reason": "counter_reset_or_invalid_time"})
        baseline = self._baseline()
        threshold = max(self.config.fixed_rate_threshold,
                        (baseline or 0.0) * self.config.deviation_ratio,
                        self.config.minimum_absolute_delta)
        anomalous = (len(self.baseline_values) >= self.config.warmup_samples
                     and rate.bytes_per_sec >= threshold
                     and (self.config.fixed_rate_threshold > 0 or baseline is not None
                          or self.config.minimum_absolute_delta > 0))
        # Do not train on the point currently being judged.  In particular,
        # sustained spikes must remain anomalous instead of lifting their own
        # threshold on the second sample.
        if not anomalous:
            self.baseline_values.append(rate.bytes_per_sec)
        event_kind: str | None = None
        if anomalous:
            self.total_anomalies += 1
            self.anomaly_count += 1
            self.normal_count = 0
            if self.state == "NORMAL":
                self.state = "WATCH"
            if self.state == "WATCH" and self.anomaly_count >= self.config.consecutive_anomalies:
                self.state = "ALERT"
                if self._can_emit(sample.sampled_at):
                    event_kind = "anomaly"
            elif self.state == "RECOVERING":
                self.state = "ALERT"
        else:
            self.anomaly_count = 0
            self.normal_count += 1
            if self.state == "WATCH":
                self.state = "NORMAL"
            elif self.state == "ALERT":
                self.state = "RECOVERING"
            elif self.state == "RECOVERING" and self.normal_count >= self.config.consecutive_normals:
                self.state = "RESOLVED"
                # Recovery is a lifecycle transition, not a duplicate alert;
                # cooldown must never hide the resolved signal.
                event_kind = "resolved"
            elif self.state == "RESOLVED" and self.normal_count >= self.config.consecutive_normals:
                self.state = "NORMAL"
        if event_kind:
            self.last_event_at = sample.sampled_at
        key = f"interface:{sample.interface_id}:atd-b"
        return DetectionResult(self.state, rate, baseline, threshold, anomalous, event_kind, key,
                                self.total_anomalies,
                                {"scope": "interface-level anomaly", "interface": sample.interface,
                                 "reset": rate.reset, "invalid": rate.invalid})

    def _baseline(self) -> float | None:
        if not self.baseline_values:
            return None
        return sum(self.baseline_values) / len(self.baseline_values)

    def _can_emit(self, timestamp: datetime) -> bool:
        return self.last_event_at is None or (timestamp - self.last_event_at).total_seconds() >= self.config.cooldown_seconds


def persist_detection(conn: sqlite3.Connection, sample: CounterSample, result: DetectionResult) -> int | None:
    """Insert/update a deduplicated event. Returns its id when an event is emitted."""
    if result.event_kind is None or result.event_key is None:
        return None
    now = sample.sampled_at.astimezone(UTC).isoformat()
    row = conn.execute("SELECT id, state FROM traffic_alerts WHERE event_key=?", (result.event_key,)).fetchone()
    if row is not None:
        conn.execute("UPDATE traffic_alerts SET last_seen=?, count=count+1, state=?, resolved_at=? WHERE id=?",
                     (now, result.state, now if result.event_kind == "resolved" else None, row[0]))
        conn.commit()
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO traffic_alerts(interface_id,ifindex,interface_name,detector_type,severity,state,"
        "observed_rate,baseline,threshold,deviation_ratio,first_seen,last_seen,count,resolved_at,evidence,"
        "source_ip,destination_ip,port,protocol,event_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sample.interface_id, sample.ifindex, sample.interface, "interface_counter", "medium", result.state,
         result.rate.bytes_per_sec, result.baseline, result.threshold,
         (cast(float, result.rate.bytes_per_sec) / result.baseline if result.baseline else None), now, now, 1,
         now if result.event_kind == "resolved" else None, str(result.evidence), None, None, None, None, result.event_key),
    )
    conn.commit()
    return int(cast(int, cur.lastrowid))
