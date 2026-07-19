"""Read-only SecMon P2 HTTP API with short-lived, revocable bearer sessions."""

import hashlib
import ipaddress
import json
import sqlite3
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import Settings, get_settings
from backend.services.nftables import FirewallError, NftablesService

MAX_PAGE_SIZE = 200
MAX_RANGE_DAYS = 31
PASSWORD_HASHER = PasswordHasher()
LOGIN_ATTEMPTS: dict[str, tuple[int, float]] = {}
LOGIN_ATTEMPT_LIMIT = 10_000
# This is not an account credential.  It equalizes failed-login work when a
# username does not exist, reducing account enumeration by response timing.
DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$8Ee7ITqFIpACAEgVhijP3w$KFy3XpbEMM5SvBUyWRbPH9E5tGdK5hBj3VdF1RZCkG0"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: Literal["admin", "analyst", "viewer"]


class LoginOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class RoleUpdateRequest(BaseModel):
    role: Literal["admin", "analyst", "viewer"]


class FirewallRequest(BaseModel):
    ip: str = Field(min_length=1, max_length=45)


class FirewallPreviewRequest(BaseModel):
    ip: str = Field(min_length=1, max_length=45)
    operation: Literal["block", "unblock"] = "block"


class FirewallBlockRequest(BaseModel):
    ip: str = Field(min_length=1, max_length=45)
    reason: str = Field(min_length=1, max_length=256)


SENSITIVE_AUDIT_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token", "id_token", "jwt",
    "authorization", "cookie", "set-cookie", "secret", "credential", "api_key", "bearer",
}


def _redact(value: Any, key: str = "") -> Any:
    """Keep audit records useful without ever returning credentials."""
    if key.casefold() in SENSITIVE_AUDIT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _audit_value(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return _redact(json.loads(value))
    except (TypeError, json.JSONDecodeError):
        return "[REDACTED]" if any(word in value.casefold() for word in SENSITIVE_AUDIT_KEYS) else value


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _database(settings: Settings) -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _secret(settings: Settings) -> str:
    secret = settings.api_jwt_secret
    if secret is None or len(secret.get_secret_value().encode()) < 32:
        raise RuntimeError("API authentication is not configured")
    return secret.get_secret_value()


def _error(status: int, code: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": "Request could not be processed",
                "request_id": request.state.request_id,
            }
        },
    )


def _parse_time(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(name) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _range(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    start_at, end_at = _parse_time(start, "start"), _parse_time(end, "end")
    if (
        start_at
        and end_at
        and (end_at < start_at or end_at - start_at > timedelta(days=MAX_RANGE_DAYS))
    ):
        raise ValueError("range")
    return (start_at.isoformat() if start_at else None, end_at.isoformat() if end_at else None)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="SecMon API",
        version="1.0",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api_cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next: Any) -> Response:
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return cast(Response, response)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND"}
        return _error(exc.status_code, codes.get(exc.status_code, "INVALID_REQUEST"), request)

    @app.exception_handler(ValueError)
    async def value_error(request: Request, _: ValueError) -> JSONResponse:
        return _error(422, "INVALID_FILTER", request)

    @app.exception_handler(FirewallError)
    async def firewall_error(request: Request, _: FirewallError) -> JSONResponse:
        return _error(503, "FIREWALL_UNAVAILABLE", request)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, _: sqlite3.Error) -> JSONResponse:
        """Return a stable error without exposing SQLite or trigger diagnostics."""
        return _error(500, "DATABASE_ERROR", request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return _error(422, "INVALID_REQUEST", request)

    def current_user(authorization: Annotated[str | None, Header()] = None) -> UserOut:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401)
        try:
            claims = jwt.decode(
                authorization[7:],
                _secret(settings),
                algorithms=["HS256"],
                issuer=settings.api_jwt_issuer,
            )
            session_id, user_id = str(claims["sid"]), int(claims["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError, RuntimeError):
            raise HTTPException(401) from None
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT u.id, u.username, u.display_name, u.role FROM users u JOIN api_sessions s ON s.user_id=u.id WHERE s.session_id=? AND s.revoked_at IS NULL AND s.expires_at > CURRENT_TIMESTAMP AND u.enabled=1",
                (session_id,),
            ).fetchone()
        if row is None or row["id"] != user_id:
            raise HTTPException(401)
        return UserOut(**dict(row))

    def require_read(user: Annotated[UserOut, Depends(current_user)]) -> UserOut:
        return user

    def require_admin(user: Annotated[UserOut, Depends(current_user)]) -> UserOut:
        if user.role != "admin":
            raise HTTPException(403)
        return user

    def require_analyst(user: Annotated[UserOut, Depends(current_user)]) -> UserOut:
        if user.role not in {"admin", "analyst"}:
            raise HTTPException(403)
        return user

    app.state.firewall = NftablesService(settings.nft_binary, settings.nft_timeout_seconds)

    def firewall() -> NftablesService:
        return cast(NftablesService, app.state.firewall)

    def write_audit(
        conn: sqlite3.Connection, user: UserOut, request: Request, action: str,
        target_value: str, details: dict[str, Any],
    ) -> None:
        conn.execute(
            "INSERT INTO audit_logs(user_id,action,target_type,target_value,client_ip,request_id,details_json,actor_role,result) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (user.id, action, "firewall_block", target_value, request.client.host if request.client else None,
             request.state.request_id, json.dumps(_redact(details), separators=(",", ":")), user.role,
             str(details.get("result", "success"))),
        )

    def reconcile_firewall() -> None:
        """Restore every active database block when a backend process starts."""
        with _database(settings) as conn:
            rows = conn.execute(
                "SELECT id,src_ip FROM blocked_ips WHERE active=1 ORDER BY id"
            ).fetchall()
        operation_id = f"startup:{uuid.uuid4()}"
        for row in rows:
            result = "success"
            try:
                firewall().block(row["src_ip"])
            except FirewallError:
                result = "failure"
            with _database(settings) as conn:
                conn.execute(
                    "UPDATE blocked_ips SET firewall_synced=? WHERE id=? AND active=1",
                    (1 if result == "success" else 0, row["id"]),
                )
                conn.execute(
                    "INSERT INTO audit_logs(action,target_type,target_value,request_id,details_json,result) "
                    "VALUES ('firewall_reconcile','firewall_block',?,?,?,?)",
                    (
                        row["src_ip"],
                        operation_id,
                        json.dumps({"result": result}, separators=(",", ":")),
                        result,
                    ),
                )

    app.state.reconcile_firewall = reconcile_firewall
    app.router.add_event_handler("startup", reconcile_firewall)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        try:
            with _database(settings) as conn:
                conn.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            raise HTTPException(503) from None
        return {"status": "ready"}

    @app.post("/api/v1/auth/login", response_model=LoginOut)
    def login(body: LoginRequest, request: Request) -> LoginOut:
        key = hashlib.sha256(body.username.casefold().encode()).hexdigest()
        now = time.monotonic()
        for attempt_key, (_, expires) in list(LOGIN_ATTEMPTS.items()):
            if expires and expires <= now:
                LOGIN_ATTEMPTS.pop(attempt_key, None)
        count, blocked_until = LOGIN_ATTEMPTS.get(key, (0, 0.0))
        if blocked_until > now:
            raise HTTPException(401)
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, display_name, role FROM users WHERE username=? AND enabled=1",
                (body.username,),
            ).fetchone()
        try:
            verified: bool = PASSWORD_HASHER.verify(
                row["password_hash"] if row else DUMMY_PASSWORD_HASH, body.password
            )
        except VerifyMismatchError:
            verified = False
        valid = bool(row) and verified
        if not valid:
            next_count = count + 1
            if len(LOGIN_ATTEMPTS) >= LOGIN_ATTEMPT_LIMIT and key not in LOGIN_ATTEMPTS:
                LOGIN_ATTEMPTS.pop(next(iter(LOGIN_ATTEMPTS)))
            LOGIN_ATTEMPTS[key] = (next_count, now + 60 if next_count >= 5 else 0.0)
            raise HTTPException(401)
        LOGIN_ATTEMPTS.pop(key, None)
        session_id = str(uuid.uuid4())
        expiry = _utc_now() + timedelta(seconds=settings.api_token_ttl_seconds)
        database_expiry = expiry.strftime("%Y-%m-%d %H:%M:%S")
        with _database(settings) as conn:
            conn.execute(
                "INSERT INTO api_sessions(session_id, user_id, expires_at) VALUES (?, ?, ?)",
                (session_id, row["id"], database_expiry),
            )
            conn.execute(
                "INSERT INTO audit_logs(user_id, action, target_type, request_id) VALUES (?, 'login', 'session', ?)",
                (row["id"], request.state.request_id),
            )
        token = jwt.encode(
            {
                "sub": str(row["id"]),
                "sid": session_id,
                "iss": settings.api_jwt_issuer,
                "exp": expiry,
            },
            _secret(settings),
            algorithm="HS256",
        )
        return LoginOut(access_token=token, expires_in=settings.api_token_ttl_seconds)

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(
        user: Annotated[UserOut, Depends(current_user)], authorization: Annotated[str, Header()]
    ) -> Response:
        claims = jwt.decode(
            authorization[7:],
            _secret(settings),
            algorithms=["HS256"],
            issuer=settings.api_jwt_issuer,
        )
        with _database(settings) as conn:
            conn.execute(
                "UPDATE api_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE session_id=? AND user_id=?",
                (claims["sid"], user.id),
            )
        return Response(status_code=204)

    @app.get("/api/v1/auth/me", response_model=UserOut)
    def me(user: Annotated[UserOut, Depends(require_read)]) -> UserOut:
        return user

    @app.get("/api/v1/dashboard/summary")
    def summary(
        user: Annotated[UserOut, Depends(require_read)],
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        start_at, end_at = _range(start, end)
        clauses, params = [], []
        if start_at:
            clauses.append("detected_at >= ?")
            params.append(start_at)
        if end_at:
            clauses.append("detected_at <= ?")
            params.append(end_at)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with _database(settings) as conn:
            stats = conn.execute(
                f"SELECT COUNT(*) events, COUNT(DISTINCT src_ip) attackers, COALESCE(SUM(severity >= 4),0) high_risk, MAX(detected_at) latest_event_at FROM attack_events{where}",
                params,
            ).fetchone()
            blocks = conn.execute("SELECT COUNT(*) FROM blocked_ips WHERE active=1").fetchone()[0]
            sources = conn.execute(
                "SELECT status, COUNT(*) count FROM log_sources GROUP BY status"
            ).fetchall()
        return {
            **dict(stats),
            "read_only_block_count": blocks,
            "log_source_health": {x["status"]: x["count"] for x in sources},
        }

    @app.get("/api/v1/events")
    def events(
        user: Annotated[UserOut, Depends(require_read)],
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
        start: str | None = None,
        end: str | None = None,
        source_ip: str | None = None,
        attack_type: str | None = None,
        severity: int | None = Query(None, ge=1, le=5),
        log_source: int | None = Query(None, ge=1),
        username: str | None = None,
    ) -> dict[str, Any]:
        start_at, end_at = _range(start, end)
        clauses, params = [], []
        for column, value in (
            ("detected_at >=", start_at),
            ("detected_at <=", end_at),
            ("src_ip =", source_ip),
            ("attack_type =", attack_type),
            ("severity =", severity),
            ("source_id =", log_source),
            ("username =", username),
        ):
            if value is not None:
                clauses.append(f"{column} ?")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with _database(settings) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM attack_events{where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT id, detected_at, source_id, src_ip, attack_type, severity, username, substr(raw_log,1,2048) raw_log FROM attack_events{where} ORDER BY detected_at DESC, id DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @app.get("/api/v1/events/{event_id}")
    def event(event_id: int, user: Annotated[UserOut, Depends(require_read)]) -> dict[str, Any]:
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT id, detected_at, source_id, src_ip, attack_type, severity, username, substr(raw_log,1,2048) raw_log FROM attack_events WHERE id=?",
                (event_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(404)
        return dict(row)

    @app.get("/api/v1/attackers")
    def attackers(
        user: Annotated[UserOut, Depends(require_read)],
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
        minimum_threat_score: int = Query(0, ge=0),
        minimum_event_count: int = Query(0, ge=0),
        status: str | None = None,
    ) -> dict[str, Any]:
        clauses: list[str] = ["threat_score >= ?", "total_events >= ?"]
        params: list[Any] = [minimum_threat_score, minimum_event_count]
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(clauses)
        with _database(settings) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM attackers{where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM attackers{where} ORDER BY last_seen DESC, src_ip ASC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @app.get("/api/v1/attackers/{ip}")
    def attacker(ip: str, user: Annotated[UserOut, Depends(require_read)]) -> dict[str, Any]:
        try:
            parsed = str(ipaddress.ip_address(ip))
        except ValueError:
            raise HTTPException(404) from None
        with _database(settings) as conn:
            row = conn.execute("SELECT * FROM attackers WHERE src_ip=?", (parsed,)).fetchone()
            if row is None:
                raise HTTPException(404)
            events_for_ip = conn.execute(
                "SELECT id, detected_at, attack_type, severity FROM attack_events WHERE src_ip=? ORDER BY detected_at DESC, id DESC LIMIT 50",
                (parsed,),
            ).fetchall()
            blocked = (
                conn.execute(
                    "SELECT COUNT(*) FROM blocked_ips WHERE src_ip=? AND active=1", (parsed,)
                ).fetchone()[0]
                > 0
            )
        return {
            "summary": dict(row),
            "recent_events": [dict(x) for x in events_for_ip],
            "read_only_blocked": blocked,
        }

    @app.get("/api/v1/log-sources")
    def sources(user: Annotated[UserOut, Depends(require_read)]) -> dict[str, Any]:
        with _database(settings) as conn:
            rows = conn.execute(
                "SELECT id,name,source_type,enabled,status,last_event_at,events_today,parse_errors_today FROM log_sources ORDER BY id"
            ).fetchall()
        return {"items": [dict(r) for r in rows]}

    @app.get("/api/v1/log-sources/{source_id}")
    def source(source_id: int, user: Annotated[UserOut, Depends(require_read)]) -> dict[str, Any]:
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT id,name,source_type,enabled,status,last_event_at,events_today,parse_errors_today,substr(last_error,1,256) last_error FROM log_sources WHERE id=?",
                (source_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(404)
        return dict(row)

    @app.get("/api/v1/firewall/status")
    def firewall_status(user: Annotated[UserOut, Depends(require_read)]) -> dict[str, bool]:
        """Expose configuration health, never nftables' full host ruleset."""
        state = firewall().status()
        return {
            "available": state.available,
            "table_present": state.table_present,
            "ipv4_set_present": state.ipv4_set_present,
            "ipv6_set_present": state.ipv6_set_present,
        }

    @app.post("/api/v1/firewall/preview")
    def firewall_preview(
        body: FirewallPreviewRequest, user: Annotated[UserOut, Depends(require_analyst)]
    ) -> dict[str, object]:
        """Analysts may validate the exact isolated operation but cannot execute it."""
        try:
            if body.operation == "block":
                return firewall().preview(body.ip)
            return firewall().preview(body.ip, body.operation)
        except FirewallError:
            raise HTTPException(422) from None

    @app.get("/api/v1/firewall/blocks")
    def firewall_blocks(user: Annotated[UserOut, Depends(require_read)]) -> dict[str, Any]:
        with _database(settings) as conn:
            rows = conn.execute(
                "SELECT id,src_ip,reason,block_source,blocked_at,blocked_by,firewall_synced "
                "FROM blocked_ips WHERE active=1 ORDER BY blocked_at DESC,id DESC"
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.post("/api/v1/firewall/blocks")
    def block_ip(
        body: FirewallBlockRequest, request: Request, user: Annotated[UserOut, Depends(require_admin)]
    ) -> dict[str, Any]:
        try:
            ip, _ = firewall().parse_ip(body.ip)
        except FirewallError:
            with _database(settings) as conn:
                write_audit(conn, user, request, "firewall_block", "[REDACTED]", {"result": "failure"})
            raise HTTPException(422) from None
        with _database(settings) as conn:
            existing = conn.execute(
                "SELECT id,src_ip,reason,blocked_at FROM blocked_ips WHERE src_ip=? AND active=1", (ip,)
            ).fetchone()
        if existing is not None:
            return {"item": dict(existing), "idempotent": True}
        firewall().block(ip)
        try:
            with _database(settings) as conn:
                # The partial unique index is also a concurrency guard.  If a
                # second request won, return its record and remove our element.
                try:
                    cursor = conn.execute(
                        "INSERT INTO blocked_ips(src_ip,reason,blocked_by,blocked_at,active,firewall_synced) "
                        "VALUES (?,?,?,CURRENT_TIMESTAMP,1,1)", (ip, body.reason, user.id)
                    )
                except sqlite3.IntegrityError:
                    existing = conn.execute(
                        "SELECT id,src_ip,reason,blocked_at FROM blocked_ips WHERE src_ip=? AND active=1", (ip,)
                    ).fetchone()
                    if existing is not None:
                        return {"item": dict(existing), "idempotent": True}
                    raise
                conn.execute("UPDATE attackers SET status='blocked' WHERE src_ip=?", (ip,))
                write_audit(conn, user, request, "firewall_block", ip, {"ip": ip, "reason": body.reason})
                row = conn.execute(
                    "SELECT id,src_ip,reason,blocked_at FROM blocked_ips WHERE id=?", (cursor.lastrowid,)
                ).fetchone()
        except Exception:
            rollback_result = "success"
            try:
                firewall().unblock(ip)
            except FirewallError:
                # The database operation failed, and the error is deliberately
                # not hidden from operations; no false success response follows.
                rollback_result = "failure"
            # Use a new transaction: the original one was intentionally rolled
            # back.  This makes a kernel/DB compensation visible without ever
            # turning the failed request into a successful block.
            try:
                with _database(settings) as conn:
                    write_audit(
                        conn, user, request, "firewall_block", ip,
                        {"result": "rollback", "rollback": rollback_result},
                    )
            except sqlite3.Error:
                # Preserve the original database error; audit persistence must
                # not mask it or claim a successful firewall operation.
                pass
            raise
        return {"item": dict(row), "idempotent": False}

    @app.delete("/api/v1/firewall/blocks/{ip}")
    def unblock_ip(
        ip: str, request: Request, user: Annotated[UserOut, Depends(require_admin)]
    ) -> dict[str, Any]:
        try:
            canonical_ip, _ = firewall().parse_ip(ip)
        except FirewallError:
            with _database(settings) as conn:
                write_audit(conn, user, request, "firewall_unblock", "[REDACTED]", {"result": "failure"})
            raise HTTPException(422) from None
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT id FROM blocked_ips WHERE src_ip=? AND active=1", (canonical_ip,)
            ).fetchone()
        # Delete first at the firewall boundary; a missing element is an
        # idempotent success, while an operational error leaves the DB intact.
        firewall().unblock(canonical_ip)
        if row is None:
            return {"ip": canonical_ip, "idempotent": True}
        try:
            with _database(settings) as conn:
                conn.execute(
                    "UPDATE blocked_ips SET active=0,released_at=CURRENT_TIMESTAMP,released_by=?,firewall_synced=1 "
                    "WHERE id=? AND active=1", (user.id, row["id"])
                )
                conn.execute(
                    "UPDATE attackers SET status='observed' WHERE src_ip=? AND status='blocked'", (canonical_ip,)
                )
                write_audit(conn, user, request, "firewall_unblock", canonical_ip, {"ip": canonical_ip})
        except Exception:
            try:
                firewall().block(canonical_ip)
            except FirewallError:
                pass
            raise
        return {"ip": canonical_ip, "idempotent": False}

    @app.get("/api/v1/admin/audit")
    def audit_summary(
        user: Annotated[UserOut, Depends(require_admin)], page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    ) -> dict[str, Any]:
        """Admin-only audit trail with credential-bearing values redacted."""
        with _database(settings) as conn:
            count = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
            rows = conn.execute(
                "SELECT a.id,a.action,a.target_type,a.target_value,a.old_value,a.new_value,a.client_ip,"
                "a.request_id,a.created_at,a.details_json,a.actor_role,a.result,u.username FROM audit_logs a "
                "LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC,a.id DESC LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["old_value"] = _audit_value(item["old_value"])
            item["new_value"] = _audit_value(item["new_value"])
            item["details"] = _audit_value(item.pop("details_json"))
            items.append(item)
        return {"audit_entry_count": count, "items": items, "page": page, "page_size": page_size}

    @app.get("/api/v1/admin/audit/entries")
    def audit_entries(user: Annotated[UserOut, Depends(require_admin)]) -> dict[str, Any]:
        """Compatibility view of the redacted audit trail."""
        return audit_summary(user, 1, MAX_PAGE_SIZE)

    @app.get("/api/v1/admin/users", response_model=list[UserOut])
    def admin_users(user: Annotated[UserOut, Depends(require_admin)]) -> list[UserOut]:
        """Return only the account fields needed by the administration UI."""
        with _database(settings) as conn:
            rows = conn.execute(
                "SELECT id, username, display_name, role FROM users WHERE enabled=1 ORDER BY username"
            ).fetchall()
        return [UserOut(**dict(row)) for row in rows]

    @app.patch("/api/v1/admin/users/{user_id}/role", response_model=UserOut)
    def update_user_role(
        user_id: int,
        body: RoleUpdateRequest,
        request: Request,
        user: Annotated[UserOut, Depends(require_admin)],
    ) -> UserOut:
        """Change another enabled user's role; self-service elevation is intentionally forbidden."""
        if user_id == user.id:
            raise HTTPException(403)
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT id, username, display_name, role FROM users WHERE id=? AND enabled=1", (user_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(404)
            conn.execute("UPDATE users SET role=? WHERE id=?", (body.role, user_id))
            conn.execute(
                "INSERT INTO audit_logs(user_id, action, target_type, target_value, request_id) VALUES (?, 'role_update', 'user', ?, ?)",
                (user.id, str(user_id), request.state.request_id),
            )
            updated = dict(row)
            updated["role"] = body.role
        return UserOut(**updated)

    # Serve the compiled, same-origin console after API routes so browser requests
    # retain the P2 bearer contract without an undocumented proxy dependency.
    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
