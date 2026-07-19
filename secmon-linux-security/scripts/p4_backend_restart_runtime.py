#!/usr/bin/env python3
"""Real HTTP rollback and backend restart gate for an isolated network namespace."""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher

from backend.services.nftables import NftablesService
from database.migrate import migrate

NFT = os.environ.get("NFT_BINARY", "/usr/sbin/nft")
BASE_URL = "http://127.0.0.1:18084"
SECRET = "p4-isolated-runtime-secret-at-least-32-bytes"
PASSWORD = "p4-isolated-admin-password"
ROLLBACK_IP = "198.51.100.88"
RESTART_V4 = "198.51.100.89"
RESTART_V6 = "2001:db8:44::89"
POST_RESTART_IP = "198.51.100.90"


def request(
    method: str, path: str, body: dict[str, Any] | None = None, token: str | None = None,
) -> tuple[int, dict[str, Any], str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    encoded = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=encoded, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, json.loads(raw) if raw else {}, raw


def wait_ready(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"backend exited during startup with code {process.returncode}")
        try:
            status, _, _ = request("GET", "/readyz")
            if status == 200:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError("backend readiness timeout")


def start_backend(database: Path, log: Path) -> tuple[subprocess.Popen[str], Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "SECMON_DATABASE_PATH": str(database),
            "SECMON_API_JWT_SECRET": SECRET,
            "SECMON_NFT_BINARY": NFT,
            "SECMON_ENVIRONMENT": "test",
        }
    )
    log_handle = log.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18084",
            "--log-level",
            "warning",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    wait_ready(process)
    return process, log_handle


def stop_backend(process: subprocess.Popen[str], log_handle: Any) -> None:
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log_handle.close()
    # uvicorn does not install a SIGTERM handler in every supported runtime;
    # a deliberate process stop is therefore either a clean exit or SIGTERM.
    if process.returncode not in (0, -signal.SIGTERM):
        raise AssertionError(f"backend stopped with code {process.returncode}")


def login() -> str:
    status, payload, _ = request(
        "POST", "/api/v1/auth/login", {"username": "admin", "password": PASSWORD}
    )
    assert status == 200, f"login failed: {status}"
    return str(payload["access_token"])


def block(ip: str, token: str, reason: str = "isolated runtime") -> tuple[int, dict[str, Any], str]:
    return request("POST", "/api/v1/firewall/blocks", {"ip": ip, "reason": reason}, token)


def unblock(ip: str, token: str) -> tuple[int, dict[str, Any], str]:
    return request("DELETE", f"/api/v1/firewall/blocks/{ip}", token=token)


def initialize_database(database: Path) -> None:
    migrate(database, Path(__file__).resolve().parents[1] / "database" / "migrations")
    with sqlite3.connect(database) as conn:
        conn.execute(
            "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
            ("admin", PasswordHasher().hash(PASSWORD), "admin"),
        )


def element_present(service: NftablesService, ip: str) -> bool:
    canonical, family = service.parse_ip(ip)
    address_set = "blocked_ipv4" if family == "ipv4" else "blocked_ipv6"
    result = subprocess.run(
        [NFT, "get", "element", "inet", "secmon", address_set, "{", canonical, "}"],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    return result.returncode == 0


def main() -> None:
    service = NftablesService(binary=NFT)
    processes: list[tuple[subprocess.Popen[str], Any]] = []
    with tempfile.TemporaryDirectory(prefix="secmon-p4-http-") as temporary:
        root = Path(temporary)
        database, log = root / "secmon.db", root / "backend.log"
        initialize_database(database)
        try:
            first, first_log = start_backend(database, log)
            processes.append((first, first_log))
            first_pid = first.pid
            token = login()

            with sqlite3.connect(database) as conn:
                conn.execute(
                    "CREATE TRIGGER reject_block BEFORE INSERT ON blocked_ips BEGIN "
                    "SELECT RAISE(ABORT, 'credential=runtime-trigger-secret'); END"
                )
            status, payload, raw = block(ROLLBACK_IP, token, "rollback trigger")
            assert status == 500 and payload["error"]["code"] == "DATABASE_ERROR"
            assert "runtime-trigger-secret" not in raw and "credential" not in raw.casefold()
            assert not element_present(service, ROLLBACK_IP), "rollback left an orphaned nft element"
            with sqlite3.connect(database) as conn:
                assert conn.execute(
                    "SELECT COUNT(*) FROM blocked_ips WHERE src_ip=? AND active=1", (ROLLBACK_IP,)
                ).fetchone()[0] == 0
                audit = conn.execute(
                    "SELECT result,details_json FROM audit_logs WHERE action='firewall_block' "
                    "AND target_value=? ORDER BY id DESC LIMIT 1", (ROLLBACK_IP,)
                ).fetchone()
                assert audit == ("rollback", '{"result":"rollback","rollback":"success"}')
                assert conn.execute(
                    "SELECT COUNT(*) FROM audit_logs WHERE details_json LIKE '%runtime-trigger-secret%'"
                ).fetchone()[0] == 0
                conn.execute("DROP TRIGGER reject_block")

            for address in (RESTART_V4, RESTART_V6):
                status, payload, _ = block(address, token)
                assert status == 200 and payload["idempotent"] is False
                assert element_present(service, address)

            stop_backend(first, first_log)
            processes.clear()
            service.unblock(RESTART_V4)
            assert not element_present(service, RESTART_V4)
            assert element_present(service, RESTART_V6)

            second, second_log = start_backend(database, log)
            processes.append((second, second_log))
            assert second.pid != first_pid
            token = login()
            assert element_present(service, RESTART_V4), "startup did not reconcile missing IPv4"
            assert element_present(service, RESTART_V6), "startup lost retained IPv6"

            for address in (RESTART_V4, RESTART_V6):
                status, payload, _ = unblock(address, token)
                assert status == 200 and payload["idempotent"] is False
                assert not element_present(service, address)
            status, payload, _ = block(POST_RESTART_IP, token, "post restart")
            assert status == 200 and payload["idempotent"] is False
            assert element_present(service, POST_RESTART_IP)
            status, payload, _ = unblock(POST_RESTART_IP, token)
            assert status == 200 and payload["idempotent"] is False
            assert not element_present(service, POST_RESTART_IP)

            status, audit_payload, audit_raw = request("GET", "/api/v1/admin/audit", token=token)
            assert status == 200
            assert any(
                item["action"] == "firewall_reconcile" and item["result"] == "success"
                for item in audit_payload["items"]
            )
            assert SECRET not in audit_raw and PASSWORD not in audit_raw
            stop_backend(second, second_log)
            processes.clear()
            print(f"P4_REAL_HTTP_RESTART_PASS old_pid={first_pid} new_pid={second.pid}")
        finally:
            for process, handle in processes:
                try:
                    stop_backend(process, handle)
                except AssertionError:
                    pass
            for address in (ROLLBACK_IP, RESTART_V4, RESTART_V6, POST_RESTART_IP):
                try:
                    service.unblock(address)
                except Exception:
                    pass
            subprocess.run(
                [NFT, "delete", "table", "inet", "secmon"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )


if __name__ == "__main__":
    main()
