"""Read-only SecMon P2 HTTP API with short-lived, revocable bearer sessions."""

import hashlib
import ipaddress
import sqlite3
import time
import uuid
from datetime import UTC, datetime, timedelta
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
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import Settings, get_settings

MAX_PAGE_SIZE = 200
MAX_RANGE_DAYS = 31
PASSWORD_HASHER = PasswordHasher()
LOGIN_ATTEMPTS: dict[str, tuple[int, float]] = {}


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
    if secret is None or not secret.get_secret_value():
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
        allow_methods=["GET", "POST"],
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
        count, blocked_until = LOGIN_ATTEMPTS.get(key, (0, 0.0))
        if blocked_until > time.monotonic():
            raise HTTPException(401)
        with _database(settings) as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, display_name, role FROM users WHERE username=? AND enabled=1",
                (body.username,),
            ).fetchone()
        valid = False
        if row:
            try:
                valid = PASSWORD_HASHER.verify(row["password_hash"], body.password)
            except VerifyMismatchError:
                valid = False
        if not valid:
            next_count = count + 1
            LOGIN_ATTEMPTS[key] = (next_count, time.monotonic() + 60 if next_count >= 5 else 0.0)
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

    @app.get("/api/v1/admin/audit")
    def audit_summary(user: Annotated[UserOut, Depends(require_admin)]) -> dict[str, Any]:
        """Minimal admin-only audit count; detailed account management is deferred."""
        with _database(settings) as conn:
            count = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        return {"audit_entry_count": count}

    return app


app = create_app()
