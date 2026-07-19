from __future__ import annotations

import sqlite3
from pathlib import Path

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app import LOGIN_ATTEMPTS, create_app
from backend.config import Settings
from database.migrate import migrate


def make_client(tmp_path: Path) -> TestClient:
    database = tmp_path / "api.db"
    migrate(database, Path("database/migrations"))
    with sqlite3.connect(database) as conn:
        password = PasswordHasher().hash("correct-horse-battery-staple")
        for username, role in (("viewer", "viewer"), ("analyst", "analyst"), ("admin", "admin")):
            conn.execute(
                "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                (username, password, role),
            )
        conn.execute(
            "INSERT INTO log_sources(name,source_type,status) VALUES ('SSH','file','healthy')"
        )
        conn.execute(
            "INSERT INTO attack_events(event_key,detected_at,sensor_host,source_type,src_ip,attack_type,severity,raw_log) VALUES ('e1','2026-07-19T00:00:00+00:00','host','ssh','192.0.2.4','brute_force',5,?)",
            ("x" * 3000,),
        )
        conn.execute(
            "INSERT INTO attackers(src_ip,first_seen,last_seen,total_events,threat_score) VALUES ('192.0.2.4','2026-07-19T00:00:00+00:00','2026-07-19T00:00:00+00:00',1,80)"
        )
    LOGIN_ATTEMPTS.clear()
    return TestClient(
        create_app(
            Settings(
                database_path=database,
                api_jwt_secret="test-secret-with-at-least-thirty-two-bytes",
                api_cors_origins=("https://console.example",),
            )
        )
    )


def token(client: TestClient, username: str = "viewer") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(client: TestClient, username: str = "viewer") -> dict[str, str]:
    return {"Authorization": f"Bearer {token(client, username)}"}


def test_health_readiness_and_openapi_are_safe(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 200


def test_login_failure_does_not_reveal_account_and_logout_revokes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for username in ("viewer", "not-a-user"):
        response = client.post(
            "/api/v1/auth/login", json={"username": username, "password": "wrong"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    bearer = headers(client)
    assert client.get("/api/v1/auth/me", headers=bearer).json()["role"] == "viewer"
    assert client.post("/api/v1/auth/logout", headers=bearer).status_code == 204
    assert client.get("/api/v1/auth/me", headers=bearer).status_code == 401


def test_expired_server_session_is_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    bearer = headers(client)
    with sqlite3.connect(tmp_path / "api.db") as conn:
        conn.execute("UPDATE api_sessions SET expires_at='2000-01-01 00:00:00'")
    assert client.get("/api/v1/auth/me", headers=bearer).status_code == 401


def test_unauthenticated_and_invalid_authorization_are_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for value in (None, "Bearer not-a-token"):
        response = client.get(
            "/api/v1/events", headers={} if value is None else {"Authorization": value}
        )
        assert response.status_code == 401
        assert "request_id" in response.json()["error"]


def test_read_roles_and_bounded_resources(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for role in ("viewer", "analyst", "admin"):
        assert (
            client.get("/api/v1/dashboard/summary", headers=headers(client, role)).status_code
            == 200
        )
    assert client.get("/api/v1/admin/audit", headers=headers(client, "viewer")).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=headers(client, "admin")).status_code == 200
    response = client.get("/api/v1/events?page_size=201", headers=headers(client))
    assert response.status_code == 422
    response = client.get("/api/v1/events", headers=headers(client))
    assert response.status_code == 200
    assert len(response.json()["items"][0]["raw_log"]) == 2048
    assert client.get("/api/v1/events/1", headers=headers(client)).status_code == 200
    assert client.get("/api/v1/events/9999", headers=headers(client)).status_code == 404
    assert client.get("/api/v1/attackers/192.0.2.4", headers=headers(client)).status_code == 200
    assert client.get("/api/v1/attackers/not-an-ip", headers=headers(client)).status_code == 404


def test_validation_errors_do_not_disclose_schema_details(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/v1/events?page_size=201", headers=headers(client))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "detail" not in response.json()


def test_injection_and_cors_are_not_permissive(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    auth = headers(client)
    response = client.get("/api/v1/events?username=' OR 1=1 --", headers=auth)
    assert response.status_code == 200 and response.json()["total"] == 0
    allowed = client.options(
        "/api/v1/events",
        headers={"Origin": "https://console.example", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers["access-control-allow-origin"] == "https://console.example"
    denied = client.options(
        "/api/v1/events",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_migration_is_repeatable_and_foreign_keys_enforced(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    migrations = Path("database/migrations")
    migrate(database, migrations)
    migrate(database, migrations)
    with sqlite3.connect(database) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version='008_api_auth_indexes'"
            ).fetchone()[0]
            == 1
        )
