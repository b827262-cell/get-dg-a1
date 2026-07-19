# P3 Open Items and Main-Codex Takeover

Scope: GitHub Issue #4, Dashboard and administration integration.

| Acceptance item | Status | Main-Codex evidence |
| --- | --- | --- |
| Live Dashboard summary, events, attackers | FIXED_BY_MAIN_CODEX | `frontend/src/main.ts` calls the P2 endpoints; static and runtime smoke passed. |
| Login, logout, expiry and protected pages | VERIFIED | Volatile bearer credential, 401 clearing, logout revocation; API and Uvicorn smoke passed. |
| Admin user list and role changes | FIXED_BY_MAIN_CODEX | Server-side `GET /admin/users` and `PATCH /admin/users/{id}/role`, confirmation UI, audit entry. |
| Viewer/Analyst admin denial | VERIFIED | API test and HTTP runtime smoke returned 403. |
| Self-role elevation / direct API bypass | FIXED_BY_MAIN_CODEX | Backend rejects actor's own ID; tests cover Viewer, Analyst, and Admin self-change cases. |
| Unsafe dashboard output / token persistence | FIXED_BY_MAIN_CODEX | DOM `textContent` rendering; regression test rejects `innerHTML`, `localStorage`, and `sessionStorage`. |
| Same-origin deployment path | FIXED_BY_MAIN_CODEX | FastAPI mounts `frontend/` after API routes; root and `/dist/main.js` passed live HTTP smoke. |
| Login timing and bounded limiter | FIXED_BY_MAIN_CODEX | Dummy Argon2 verification for unknown users; expired entries pruned and in-process map capped. |
| Weak JWT secret | FIXED_BY_MAIN_CODEX | API startup/authentication rejects secrets shorter than 32 bytes. |
| Database / migration idempotency | VERIFIED | Fresh SQLite migration twice, `quick_check`, and `foreign_key_check` passed. |
| Agent 2 GLM-5.2 external response | EXTERNAL_BLOCKER | Exact Claude CLI invocation produced only a connector-auth warning and no usable review. Its earlier Codex verify-only findings were remediated and independently checked by main Codex. |
| Agent 3 AGY external response | EXTERNAL_BLOCKER | Exact `agy -p` invocation returned no usable output. Delegated runtime verifier and main Codex both completed live Uvicorn smoke. |

There are no unresolved TODO items. `EXTERNAL_BLOCKER` rows concern independent-agent evidence only, not an unverified product gate; the main-Codex implementation and validation evidence above covers their scoped checks.
