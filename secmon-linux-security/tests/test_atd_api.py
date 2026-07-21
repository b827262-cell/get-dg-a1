from __future__ import annotations

import sqlite3
from pathlib import Path

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from database.migrate import migrate

_JWT_SECRET = "test-secret-with-at-least-thirty-two-bytes"
_PASSWORD = "correct-horse-battery-staple"
_CACHED_HASH: str | None = None


def _hash() -> str:
    global _CACHED_HASH
    if _CACHED_HASH is None:
        _CACHED_HASH = PasswordHasher().hash(_PASSWORD)
    return _CACHED_HASH


def _make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    database = tmp_path / "atd_api.db"
    migrate(database, Path("database/migrations"))
    with sqlite3.connect(database) as conn:
        conn.execute(
            "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
            ("viewer", _hash(), "viewer"),
        )
    client = TestClient(
        create_app(
            Settings(
                environment="test",
                database_path=database,
                api_jwt_secret=_JWT_SECRET,
                api_cors_origins=("https://console.example",),
                api_docs_enabled=False,
            )
        )
    )
    return client, database


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": _PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_sample(
    db: Path,
    *,
    interface_name: str = "eth0",
    ifindex: int = 2,
    sampled_at: str,
    rx_bytes: int | None,
    tx_bytes: int | None,
    rx_packets: int | None = None,
    tx_packets: int | None = None,
    active_tcp: int | None = None,
    active_udp: int | None = None,
    is_loopback: int = 0,
) -> None:
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT id FROM network_interfaces WHERE name = ? AND ifindex IS ?",
            (interface_name, ifindex),
        ).fetchone()
        if row is not None:
            interface_id = int(row[0])
        else:
            cur = conn.execute(
                "INSERT INTO network_interfaces(name, ifindex, is_loopback, is_up, mtu) "
                "VALUES (?,?,?,?,1500)",
                (interface_name, ifindex, is_loopback, 1),
            )
            interface_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO network_samples(interface_id, sampled_at, sensor_host, "
            "rx_bytes, tx_bytes, rx_packets, tx_packets, active_tcp, active_udp, "
            "source, collector_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                interface_id,
                sampled_at,
                "host",
                rx_bytes,
                tx_bytes,
                rx_packets,
                tx_packets,
                active_tcp,
                active_udp,
                "proc",
                "atd-a-1.0",
            ),
        )


def test_network_endpoints_require_authentication(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    paths = (
        "/api/v1/network/overview",
        "/api/v1/network/interfaces",
        "/api/v1/network/traffic-series?start=2026-07-20T00:00:00Z&end=2026-07-20T01:00:00Z",
        "/api/v1/network/top-talkers",
    )
    for path in paths:
        assert client.get(path).status_code == 401, path


def test_overview_reports_no_data_when_empty(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    response = client.get("/api/v1/network/overview", headers=_auth_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["collector_status"] == "no_data"
    assert body["latest_sampled_at"] is None
    assert body["interface_count"] == 0
    assert body["data_complete"] is False
    # Honest scope notice: no "whole company" implication.
    assert "endpoint_view_only" in body["scope"]


def test_overview_returns_latest_sample_totals(tmp_path: Path) -> None:
    client, db = _make_client(tmp_path)
    _seed_sample(db, sampled_at="2026-07-20T10:00:00Z", rx_bytes=1000, tx_bytes=2000,
                 rx_packets=10, tx_packets=20, active_tcp=5, active_udp=3)
    _seed_sample(db, interface_name="eth1", ifindex=3, sampled_at="2026-07-20T10:00:00Z",
                 rx_bytes=500, tx_bytes=700, rx_packets=5, tx_packets=7, active_tcp=5, active_udp=3)
    response = client.get("/api/v1/network/overview", headers=_auth_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["collector_status"] == "healthy"
    assert body["latest_sampled_at"].startswith("2026-07-20T10:00:00")
    # Totals are taken from the latest sampled_at slice across both interfaces.
    assert body["rx_bytes_total"] == 1500
    assert body["tx_bytes_total"] == 2700
    assert body["active_tcp"] == 5
    assert body["active_udp"] == 3
    assert body["interface_count"] == 2
    assert body["data_complete"] is True


def test_interfaces_list_includes_last_sample(tmp_path: Path) -> None:
    client, db = _make_client(tmp_path)
    _seed_sample(db, sampled_at="2026-07-20T10:00:00Z", rx_bytes=1, tx_bytes=1)
    response = client.get("/api/v1/network/interfaces", headers=_auth_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "eth0"
    assert body["items"][0]["last_sample_at"].startswith("2026-07-20T10:00:00")
    assert body["page"] == 1 and body["page_size"] == 50


def test_traffic_series_requires_time_range(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    # Missing required start/end query params -> 422.
    assert (
        client.get(
            "/api/v1/network/traffic-series", headers=_auth_headers(client)
        ).status_code
        == 422
    )


def test_traffic_series_rejects_inverted_range(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    response = client.get(
        "/api/v1/network/traffic-series?start=2026-07-20T02:00:00Z&end=2026-07-20T01:00:00Z",
        headers=_auth_headers(client),
    )
    assert response.status_code == 422


def test_traffic_series_returns_empty_items_when_no_data(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    response = client.get(
        "/api/v1/network/traffic-series?start=2026-07-20T00:00:00Z&end=2026-07-20T01:00:00Z",
        headers=_auth_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_traffic_series_derives_rates_and_handles_counter_reset(tmp_path: Path) -> None:
    client, db = _make_client(tmp_path)
    # Two consecutive samples 10s apart, then a third where rx_bytes decreased
    # (simulating a kernel counter reset / reboot).
    _seed_sample(db, sampled_at="2026-07-20T10:00:00Z", rx_bytes=1000, tx_bytes=500,
                 rx_packets=10, tx_packets=5)
    _seed_sample(db, sampled_at="2026-07-20T10:00:10Z", rx_bytes=2000, tx_bytes=1500,
                 rx_packets=20, tx_packets=15)
    _seed_sample(db, sampled_at="2026-07-20T10:00:20Z", rx_bytes=500, tx_bytes=2000,
                 rx_packets=30, tx_packets=25)
    response = client.get(
        "/api/v1/network/traffic-series?start=2026-07-20T09:00:00Z&end=2026-07-20T11:00:00Z",
        headers=_auth_headers(client),
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 3
    # First sample has no predecessor -> null rates.
    assert items[0]["bps_rx"] is None
    # Second sample: (2000-1000)/10 = 100 B/s, (1500-500)/10 = 100 B/s.
    assert items[1]["bps_rx"] == 100.0
    assert items[1]["bps_tx"] == 100.0
    # Third sample: rx_bytes 2000 -> 500 (reset) -> null rx rate; tx keeps rising.
    assert items[2]["bps_rx"] is None
    assert items[2]["bps_tx"] == 50.0


def test_traffic_series_filter_by_interface(tmp_path: Path) -> None:
    client, db = _make_client(tmp_path)
    # eth0 ifindex 2 gets id 1; eth1 ifindex 3 gets id 2.
    _seed_sample(db, interface_name="eth0", ifindex=2, sampled_at="2026-07-20T10:00:00Z",
                 rx_bytes=1, tx_bytes=1)
    _seed_sample(db, interface_name="eth1", ifindex=3, sampled_at="2026-07-20T10:00:00Z",
                 rx_bytes=2, tx_bytes=2)
    response = client.get(
        "/api/v1/network/traffic-series?start=2026-07-20T00:00:00Z&end=2026-07-20T11:00:00Z&interface_id=2",
        headers=_auth_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["interface_name"] == "eth1"


def test_top_talkers_is_scoped_to_interfaces_not_ips(tmp_path: Path) -> None:
    """Critical correctness gate: ATD-A must not fabricate per-IP talkers."""
    client, db = _make_client(tmp_path)
    _seed_sample(db, interface_name="eth0", ifindex=2, sampled_at="2026-07-20T10:00:00Z",
                 rx_bytes=9000, tx_bytes=100)
    _seed_sample(db, interface_name="eth1", ifindex=3, sampled_at="2026-07-20T10:00:00Z",
                 rx_bytes=1000, tx_bytes=5000)
    # loopback must be excluded from the ranking.
    _seed_sample(db, interface_name="lo", ifindex=1, sampled_at="2026-07-20T10:00:00Z",
                 rx_bytes=999999, tx_bytes=999999, is_loopback=1)
    response = client.get("/api/v1/network/top-talkers", headers=_auth_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "interface"
    assert "ATD-B" in body["note"]
    names = [item["interface_name"] for item in body["items"]]
    assert names == ["eth0", "eth1"]  # ordered by rx_bytes desc; lo excluded
    assert body["total"] == 2
    # No field impersonates an IP source address.
    for item in body["items"]:
        assert "src_ip" not in item
        assert "ip" not in item


def test_read_paths_are_viewer_allowed(tmp_path: Path) -> None:
    """All four network endpoints are read-only and permitted to the viewer role."""
    client, _ = _make_client(tmp_path)
    headers = _auth_headers(client)  # logs in as 'viewer'
    assert client.get("/api/v1/network/overview", headers=headers).status_code == 200
    assert client.get("/api/v1/network/interfaces", headers=headers).status_code == 200
    assert client.get(
        "/api/v1/network/traffic-series?start=2026-07-20T00:00:00Z&end=2026-07-20T01:00:00Z",
        headers=headers,
    ).status_code == 200
    assert client.get("/api/v1/network/top-talkers", headers=headers).status_code == 200
