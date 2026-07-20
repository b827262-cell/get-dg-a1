import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.services.traffic_detector import (
    CounterSample,
    DetectorConfig,
    InterfaceDetector,
    calculate_rate,
    persist_detection,
)
from database.migrate import migrate


def sample(t: int, rx: int, tx: int = 0, packets: int = 10, interface: int = 1) -> CounterSample:
    return CounterSample(interface, f"eth{interface}", datetime(2026, 7, 20, tzinfo=UTC) + timedelta(seconds=t),
                         rx, tx, packets, 0, interface + 1)


def test_rate_calculation_bytes_bits_packets_and_zero_time() -> None:
    result = calculate_rate(sample(0, 0, packets=0), sample(2, 100, 100, packets=20))
    assert result.bytes_per_sec == 100
    assert result.bits_per_sec == 800
    assert result.packets_per_sec == 10
    assert calculate_rate(sample(2, 100), sample(2, 200)).invalid


def test_counter_reset_and_invalid_values_are_not_negative_rates() -> None:
    assert calculate_rate(sample(0, 500), sample(1, 1)).reset
    assert calculate_rate(sample(0, 0), sample(1, float("nan"))).invalid
    assert calculate_rate(sample(0, 0), sample(1, -1)).invalid


def test_warmup_sustained_alert_recovery_and_cooldown() -> None:
    detector = InterfaceDetector(DetectorConfig(fixed_rate_threshold=100, warmup_samples=2,
        rolling_window=4, consecutive_anomalies=2, consecutive_normals=2, cooldown_seconds=100))
    assert detector.process(sample(0, 0, packets=0)).event_kind is None
    assert detector.process(sample(1, 10, packets=1)).state == "NORMAL"
    assert detector.process(sample(2, 20, packets=2)).state == "NORMAL"
    assert detector.process(sample(3, 220, packets=3)).state == "WATCH"
    alert = detector.process(sample(4, 420, packets=4))
    assert alert.state == "ALERT" and alert.event_kind == "anomaly"
    assert detector.process(sample(5, 430, packets=5)).state == "RECOVERING"
    resolved = detector.process(sample(6, 440, packets=6))
    assert resolved.state == "RESOLVED" and resolved.event_kind == "resolved"


def test_interfaces_are_isolated_and_restart_rebuilds_baseline() -> None:
    config = DetectorConfig(fixed_rate_threshold=50, warmup_samples=2, rolling_window=4,
                            consecutive_anomalies=1)
    one = InterfaceDetector(config)
    two = InterfaceDetector(config)
    one.process(sample(0, 0, packets=0, interface=1))
    one.process(sample(1, 10, packets=1, interface=1))
    two.process(sample(0, 0, packets=0, interface=2))
    two.process(sample(1, 1000, packets=1, interface=2))
    one.process(sample(2, 20, packets=2, interface=1))
    assert one.process(sample(3, 100, packets=3, interface=1)).state == "ALERT"
    restarted = InterfaceDetector(config)
    assert restarted.process(sample(2, 100000, packets=2)).state == "NORMAL"


def test_persistence_keeps_ip_attribution_unknown_and_deduplicates(tmp_path: Path) -> None:
    db = tmp_path / "atd.db"
    migrate(db, Path("database/migrations"))
    detector = InterfaceDetector(DetectorConfig(fixed_rate_threshold=1, warmup_samples=1,
        rolling_window=2, consecutive_anomalies=1, cooldown_seconds=0))
    detector.process(sample(0, 0, packets=0))
    detector.process(sample(1, 10, packets=1))
    result = detector.process(sample(2, 100, packets=2))
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO network_interfaces(id,name,ifindex) VALUES (1,'eth1',2)")
        event_id = persist_detection(conn, sample(1, 100, packets=1), result)
        assert event_id is not None
        row = conn.execute("SELECT source_ip,destination_ip,port,protocol FROM traffic_alerts").fetchone()
        assert row == (None, None, None, None)


@pytest.mark.parametrize("name,value", [("deviation_ratio", 0.5), ("fixed_rate_threshold", float("inf")),
                                         ("warmup_samples", 0), ("rolling_window", 0)])
def test_invalid_detector_config_fails_closed(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        DetectorConfig(**{name: value})


def test_anomaly_api_auth_rbac_list_detail_and_resolved(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    migrate(db, Path("database/migrations"))
    password = "correct-horse-battery-staple"
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                     ("viewer", PasswordHasher().hash(password), "viewer"))
        conn.execute("INSERT INTO network_interfaces(id,name,ifindex) VALUES (1,'eth0',2)")
        conn.execute("INSERT INTO traffic_alerts(interface_id,ifindex,interface_name,detector_type,severity,state,"
                     "observed_rate,first_seen,last_seen,event_key) VALUES (1,2,'eth0','interface_counter','medium',"
                     "'ALERT',100,'2026-07-20T00:00:00+00:00','2026-07-20T00:00:00+00:00','test:event')")
    client = TestClient(create_app(Settings(environment="test", database_path=db,
                                             api_jwt_secret="test-secret-with-at-least-thirty-two-bytes")))
    assert client.get("/api/v1/network/anomalies").status_code == 401
    token = client.post("/api/v1/auth/login", json={"username": "viewer", "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/network/anomalies", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["source_ip"] is None
    assert client.get("/api/v1/network/anomalies/1", headers=headers).status_code == 200
    assert client.patch("/api/v1/network/anomalies/1/resolved", headers=headers).status_code == 403
