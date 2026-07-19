# P3 frontend and security review

AGENT_STATUS: COMPLETED_BY_CODEX_VERIFY_ONLY

ACTIVE_MODEL: Codex CLI (independent substitute review; the GLM-5.2 Claude CLI was not invoked by this reviewer)

REVIEW_HEAD: `1cf66a6fa095d9379fc7be295f9c697e559018a1`

REVIEW_SCOPE: Source review of `backend/app.py`, `backend/config.py`, database migration 008,
the current `frontend/` tree, and P2 API tests.  This is a point-in-time review before the
P3 implementation is present in the working tree.  It does not approve later unreviewed
changes.

## CRITICAL_FINDINGS

None in the reviewed P2 code.

## HIGH_FINDINGS

1. **P3 protected UI and administrative functionality are absent at the review point.**
   `frontend/src/main.ts` only exports `appName`; there is no login screen, router, API
   client, dashboard, or admin UI.  The backend only has the admin-only audit-count route
   (`GET /api/v1/admin/audit`), not the required safe user list and role-change endpoints.
   This is a release-blocking implementation gap, not evidence that client-side hiding is
   adequate.  Main Codex must add server-enforced admin routes and the corresponding UI and
   tests before P3 can pass.

## MEDIUM_FINDINGS

1. **Account existence can be inferred through login timing.**  `login()` invokes Argon2
   verification only when a user row exists.  Responses are uniformly 401, but a nonexistent
   username can be measurably faster than an existing account with a bad password.  Verify a
   dummy Argon2 hash on the no-user path (or otherwise equalize the work) and add a timing-path
   unit test where practical.
2. **The process-local login limiter is not a deployment-grade control.** `LOGIN_ATTEMPTS` is
   unbounded, is reset on restart, and is not shared between workers.  It should not be relied
   on as the sole brute-force control.  Bound its storage/expiry and document an upstream or
   shared limiter for multi-worker deployment.
3. **Raw event logs are returned to all read roles.**  The events endpoints return up to 2048
   characters of `raw_log`.  P3 must render every external field with text nodes / escaped DOM
   APIs, never `innerHTML`, and avoid displaying raw logs unless operationally required.  Add
   an XSS regression test containing markup in `raw_log`, `username`, and `attack_type`.
4. **JWT secret strength is not validated.**  A non-empty `SECMON_API_JWT_SECRET` is accepted.
   Production configuration should require a suitably random minimum-length secret (or a key
   source with equivalent entropy) and reject weak deployment configuration early.

## LOW_FINDINGS

1. FastAPI documentation HTML is disabled by default, but `/openapi.json` remains enabled.
   This is not a credential leak in the reviewed schema, but disable `openapi_url` as well if
   unauthenticated endpoint/schema discovery is not intended.
2. P2 read routes provide shared security telemetry to every authenticated role.  No
   per-user-owned object route exists at this revision, so an IDOR test can only cover the
   existing globally readable IDs.  Any P3 user-management or user-scoped endpoint must define
   ownership/role rules and have cross-user tests before release.

## AUTH_FINDINGS

Positive evidence: password hashes use Argon2; the token is short-lived, signed with HS256,
issuer-validated, and backed by a server-side session row; logout sets `revoked_at`; disabled
accounts and expired/revoked sessions are rejected.  P2 tests verify failed login returns a
generic 401 and logout invalidates the old token.

Required P3 checks: keep bearer credentials out of URLs and logs; do not store them in
`localStorage`/`sessionStorage`; clear in-memory credentials and UI state on 401; protect direct
navigation as well as menu visibility; verify page refresh and expired-token handling.

## RBAC_FINDINGS

Positive evidence: all reviewed data routes depend on `current_user`; `GET
/api/v1/admin/audit` uses `require_admin`; a viewer receives 403 and an admin receives 200 in
`tests/test_api_auth.py`.

Required P3 changes: every user-list/role-update route must use `require_admin` on the backend,
allow only the fixed role enum, audit the actor and target, and prevent self-role escalation.
Frontend role-aware navigation is convenience only and cannot substitute for these checks.

## IDOR_FINDINGS

The reviewed event/attacker/log-source detail endpoints require authentication and use bound
SQLite parameters.  They expose shared telemetry, not user-owned resources; therefore their
integer/IP identifiers do not currently encode an ownership boundary.  The P3 user-management
API is not yet present, so direct-object, cross-user, and self-escalation denial tests are
mandatory implementation work rather than verified evidence.

## XSS_CSRF_FINDINGS

Current frontend code does not render API data, so no DOM sink was found.  The future dashboard
will process attacker-controlled logs and usernames; it must use `textContent`/framework
escaping and must not use HTML injection sinks.  Current P2 uses Authorization bearer headers
with `allow_credentials=False`, so cookie CSRF does not apply to the reviewed flow.  If P3
changes to cookie authentication, add CSRF defenses and `Secure`, `HttpOnly`, and `SameSite`
cookie attributes before release.

## REQUIRED_FIXES

1. Implement the missing dashboard/auth/router/admin functions using the actual P2 API.
2. Add backend admin user-list and role-update operations with `require_admin`, an allowlisted
   role body, self-escalation prevention, audit entries, and generic error responses.
3. Add allow/deny tests for admin, analyst, viewer, unauthenticated, direct URL/API calls, and
   cross-user/self-role modification.
4. Make login failure work constant-time enough to avoid username enumeration and bound the
   limiter.
5. Keep credentials in memory, safely render external event fields, and add XSS/401/403 UI
   tests.
6. Enforce production JWT-secret strength and decide whether public OpenAPI is intended.

## RECOMMENDATION

NOT_READY_AT_REVIEW_HEAD.  No Critical vulnerability was found in the reviewed P2 foundation,
but the P3 feature set and its security evidence do not yet exist at this commit.  Re-review the
final P3 diff after the required fixes and execute the full auth/RBAC/IDOR/UI test matrix.
