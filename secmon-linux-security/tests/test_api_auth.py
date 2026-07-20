from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app import LOGIN_ATTEMPTS, create_app
from backend.config import Settings
from backend.services.nftables import FirewallError, FirewallStatus
from database.migrate import migrate


_CACHED_HASH: str | None = None

def get_cached_hash() -> str:
    global _CACHED_HASH
    if _CACHED_HASH is None:
        _CACHED_HASH = PasswordHasher().hash("correct-horse-battery-staple")
    return _CACHED_HASH


def make_client(tmp_path: Path) -> TestClient:
    database = tmp_path / "api.db"
    migrate(database, Path("database/migrations"))
    with sqlite3.connect(database) as conn:
        password = get_cached_hash()
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
                environment="test",
                database_path=database,
                api_jwt_secret="test-secret-with-at-least-thirty-two-bytes",
                api_cors_origins=("https://console.example",),
                api_docs_enabled=False,
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
    console = client.get("/")
    assert console.status_code == 200 and 'id="app"' in console.text


def test_event_disposition_requires_analyst_and_is_audited(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = {"status": "investigating", "handling_note": "validated triage evidence"}
    assert client.patch("/api/v1/events/1/disposition", json=payload).status_code == 401
    assert client.patch("/api/v1/events/1/disposition", headers=headers(client, "viewer"), json=payload).status_code == 403
    response = client.patch("/api/v1/events/1/disposition", headers=headers(client, "analyst"), json=payload)
    assert response.status_code == 200
    detail = client.get("/api/v1/events/1", headers=headers(client)).json()
    assert detail["handling_status"] == "investigating"
    assert detail["handling_note"] == "validated triage evidence"
    audit = client.get("/api/v1/admin/audit", headers=headers(client, "admin")).json()["items"]
    assert any(item["action"] == "event_disposition" and item["target_type"] == "security_event" for item in audit)


def test_alert_rules_deliveries_and_safe_simulation(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = {"name": "high ssh", "minimum_severity": 4, "event_threshold": 2, "window_minutes": 5,
            "quiet_start": "23:00", "quiet_end": "06:00", "suppression_minutes": 30,
            "channels": ["simulation", "email"], "recipients": ["ops@example.invalid"]}
    assert client.post("/api/v1/alert-rules", json=body).status_code == 401
    assert client.post("/api/v1/alert-rules", headers=headers(client, "analyst"), json=body).status_code == 403
    created = client.post("/api/v1/alert-rules", headers=headers(client, "admin"), json=body)
    assert created.status_code == 201
    rule_id = created.json()["item"]["id"]
    simulated = client.post(f"/api/v1/alert-rules/{rule_id}/test", headers=headers(client, "admin"), json={"channel": "simulation"})
    unavailable = client.post(f"/api/v1/alert-rules/{rule_id}/test", headers=headers(client, "admin"), json={"channel": "email", "destination": "ops@example.invalid"})
    assert simulated.json()["status"] == "simulated"
    assert unavailable.json()["status"] == "failed"
    deliveries = client.get("/api/v1/alert-deliveries", headers=headers(client, "admin")).json()["items"]
    assert {row["status"] for row in deliveries} == {"simulated", "failed"}


def test_temporary_block_expiry_is_reconciled(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    fake = FakeFirewall()
    client.app.state.firewall = fake  # type: ignore[attr-defined]
    admin = headers(client, "admin")
    assert client.post("/api/v1/firewall/blocks", headers=admin, json={"ip": "192.0.2.77", "reason": "short investigation", "duration_minutes": 1}).status_code == 200
    with sqlite3.connect(tmp_path / "api.db") as conn:
        conn.execute("UPDATE blocked_ips SET expires_at='2000-01-01 00:00:00' WHERE src_ip='192.0.2.77'")
    assert client.get("/api/v1/firewall/blocks", headers=admin).json()["items"] == []
    assert "192.0.2.77" not in fake.elements
    with sqlite3.connect(tmp_path / "api.db") as conn:
        assert conn.execute("SELECT active FROM blocked_ips WHERE src_ip='192.0.2.77'").fetchone()[0] == 0


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


def test_admin_user_management_requires_admin_and_prevents_self_escalation(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    viewer = headers(client, "viewer")
    analyst = headers(client, "analyst")
    admin = headers(client, "admin")
    assert client.get("/api/v1/admin/users", headers=viewer).status_code == 403
    assert client.patch("/api/v1/admin/users/1/role", headers=analyst, json={"role": "admin"}).status_code == 403
    users = client.get("/api/v1/admin/users", headers=admin)
    assert users.status_code == 200
    assert all("password_hash" not in item for item in users.json())
    admin_id = next(item["id"] for item in users.json() if item["username"] == "admin")
    viewer_id = next(item["id"] for item in users.json() if item["username"] == "viewer")
    assert client.patch(f"/api/v1/admin/users/{admin_id}/role", headers=admin, json={"role": "viewer"}).status_code == 403
    changed = client.patch(f"/api/v1/admin/users/{viewer_id}/role", headers=admin, json={"role": "analyst"})
    assert changed.status_code == 200 and changed.json()["role"] == "analyst"


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
        conn.execute("INSERT INTO audit_logs(action) VALUES ('test')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE audit_logs SET action='tampered'")


def test_alert_operations_are_rbac_scoped_and_audited(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    with sqlite3.connect(tmp_path / "api.db") as conn:
        conn.execute(
            "INSERT INTO alerts(event_id,src_ip,title,severity) VALUES (1,'192.0.2.4','SSH attack',5)"
        )
        analyst_id = conn.execute("SELECT id FROM users WHERE username='analyst'").fetchone()[0]
    viewer, analyst, admin = headers(client), headers(client, "analyst"), headers(client, "admin")
    assert client.get("/api/v1/alerts", headers=viewer).json()["total"] == 1
    assert client.patch("/api/v1/alerts/1", headers=viewer, json={"status": "resolved", "reason": "triage"}).status_code == 403
    assert client.patch("/api/v1/alerts/1", headers=analyst, json={"status": "resolved"}).status_code == 422
    changed = client.patch("/api/v1/alerts/1", headers=analyst, json={"status": "investigating", "assigned_to": analyst_id, "reason": "triage"})
    assert changed.status_code == 200 and changed.json()["item"]["status"] == "investigating"
    cleared = client.patch("/api/v1/alerts/1", headers=analyst, json={"assigned_to": None})
    assert cleared.status_code == 200 and cleared.json()["item"]["assigned_to"] is None
    audit = client.get("/api/v1/admin/audit", headers=admin).json()["items"]
    assert any(item["action"] == "alert_update" and item["target_type"] == "alert" for item in audit)


def test_allowlist_protects_addresses_from_manual_blocks(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.app.state.firewall = FakeFirewall()  # type: ignore[attr-defined]
    viewer, admin = headers(client), headers(client, "admin")
    assert client.get("/api/v1/allowlist", headers=viewer).status_code == 403
    created = client.post("/api/v1/allowlist", headers=admin, json={"ip_or_cidr": "192.0.2.4", "description": "operator"})
    assert created.status_code == 201 and created.json()["item"]["ip_or_cidr"] == "192.0.2.4/32"
    denied = client.post("/api/v1/firewall/blocks", headers=admin, json={"ip": "192.0.2.4", "reason": "test"})
    assert denied.status_code == 409
    assert client.request("DELETE", f"/api/v1/allowlist/{created.json()['item']['id']}", headers=admin, json={"reason": "temporary exception ended"}).status_code == 204
    assert client.post("/api/v1/firewall/blocks", headers=admin, json={"ip": "192.0.2.4", "reason": "test"}).status_code == 200
    audit = client.get("/api/v1/admin/audit", headers=admin).json()["items"]
    assert any(item["action"] == "allowlist_remove" and item["target_type"] == "allowlist" and item["details"]["reason"] == "temporary exception ended" for item in audit)


def test_operations_health_is_authenticated_and_non_sensitive(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.app.state.firewall = FakeFirewall()  # type: ignore[attr-defined]
    assert client.get("/api/v1/operations/health").status_code == 401
    response = client.get("/api/v1/operations/health", headers=headers(client))
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert set(response.json()["firewall"]) == {"available", "table_present", "ipv4_set_present", "ipv6_set_present"}


class FakeFirewall:
    def __init__(self) -> None:
        self.elements: set[str] = set()

    def status(self) -> FirewallStatus:
        return FirewallStatus(True, True, True, True)

    def preview(self, ip: str, operation: str = "block") -> dict[str, object]:
        if ip == "bad":
            raise FirewallError("invalid")
        return {"ip": ip, "operation": operation}

    def parse_ip(self, ip: str) -> tuple[str, str]:
        if ip == "bad":
            raise FirewallError("invalid")
        return ip, "ipv4"

    def block(self, ip: str) -> str:
        self.elements.add(ip)
        return ip

    def unblock(self, ip: str) -> str:
        self.elements.discard(ip)
        return ip


def test_firewall_rbac_audit_and_idempotence(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.app.state.firewall = FakeFirewall()  # type: ignore[attr-defined]
    viewer, analyst, admin = headers(client, "viewer"), headers(client, "analyst"), headers(client, "admin")
    assert client.get("/api/v1/firewall/status").status_code == 401
    assert client.post("/api/v1/firewall/blocks", headers=viewer, json={"ip": "192.0.2.4", "reason": "test"}).status_code == 403
    assert client.post("/api/v1/firewall/blocks", headers=analyst, json={"ip": "192.0.2.4", "reason": "test"}).status_code == 403
    assert client.post("/api/v1/firewall/preview", headers=analyst, json={"ip": "192.0.2.4"}).status_code == 200
    first = client.post("/api/v1/firewall/blocks", headers=admin, json={"ip": "192.0.2.4", "reason": "test"})
    repeat = client.post("/api/v1/firewall/blocks", headers=admin, json={"ip": "192.0.2.4", "reason": "test"})
    assert first.json()["idempotent"] is False and repeat.json()["idempotent"] is True
    assert client.post("/api/v1/firewall/preview", headers=admin, json={"ip": "bad"}).status_code == 422
    entries = client.get("/api/v1/admin/audit", headers=admin)
    assert entries.status_code == 200
    assert any(entry["action"] == "firewall_block" for entry in entries.json()["items"])
    assert all("password" not in str(entry).lower() and "authorization" not in str(entry).lower() for entry in entries.json()["items"])


def test_block_trigger_failure_compensates_and_returns_sanitized_error(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    fake = FakeFirewall()
    client.app.state.firewall = fake  # type: ignore[attr-defined]
    admin = headers(client, "admin")
    with sqlite3.connect(tmp_path / "api.db") as conn:
        conn.execute(
            "CREATE TRIGGER reject_block BEFORE INSERT ON blocked_ips BEGIN "
            "SELECT RAISE(ABORT, 'password=trigger-secret'); END"
        )

    response = client.post(
        "/api/v1/firewall/blocks",
        headers=admin,
        json={"ip": "192.0.2.88", "reason": "must roll back"},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DATABASE_ERROR"
    assert "trigger-secret" not in response.text and "password" not in response.text.lower()
    assert "192.0.2.88" not in fake.elements
    with sqlite3.connect(tmp_path / "api.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM blocked_ips WHERE src_ip='192.0.2.88' AND active=1"
        ).fetchone()[0] == 0
        audit = conn.execute(
            "SELECT result,details_json FROM audit_logs "
            "WHERE action='firewall_block' AND target_value='192.0.2.88' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert audit == ("rollback", '{"result":"rollback","rollback":"success"}')


def test_startup_reconciles_active_block_then_http_unblock_works(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    with sqlite3.connect(tmp_path / "api.db") as conn:
        conn.execute(
            "INSERT INTO blocked_ips(src_ip,reason,blocked_at,active,firewall_synced) "
            "VALUES (?,?,CURRENT_TIMESTAMP,1,0)",
            ("192.0.2.89", "restart test"),
        )
    fake = FakeFirewall()
    client.app.state.firewall = fake  # type: ignore[attr-defined]

    with client:
        assert "192.0.2.89" in fake.elements
        admin = headers(client, "admin")
        response = client.request("DELETE", "/api/v1/firewall/blocks/192.0.2.89", headers=admin, json={"reason": "restart verification"})
        assert response.status_code == 200
        assert response.json()["idempotent"] is False

    assert "192.0.2.89" not in fake.elements
    with sqlite3.connect(tmp_path / "api.db") as conn:
        block = conn.execute(
            "SELECT active,firewall_synced FROM blocked_ips WHERE src_ip='192.0.2.89'"
        ).fetchone()
        reconciliation = conn.execute(
            "SELECT result,details_json FROM audit_logs "
            "WHERE action='firewall_reconcile' AND target_value='192.0.2.89'"
        ).fetchone()
    assert block == (0, 1)
    assert reconciliation == ("success", '{"result":"success"}')
