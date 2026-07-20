# P5 SecMon UI Release Gate — Evidence Supplement

Date: 2026-07-20 (Asia/Taipei)

## Git provenance

- P5 start HEAD: `43ddc6b424b94d271589e948b39f6def9289ed6c`
- Branch: `feature/secmon-p4-detection-operations`
- P5 end/tested HEAD: populated only after the remediation commit and final rerun.
- Initial worktree status was untracked `database/migrations/011_p4_operations_closure.sql` and `docs/acceptance/`.
- Final report, screenshots, and command results must refer only to the final tested commit recorded below; do not use the stale `36a96fc` report as release evidence.

## app.py and test_api_auth.py security review

### Argon2 production security

- `backend/app.py` retains `PASSWORD_HASHER = PasswordHasher()` with no reduced time, memory, parallelism, hash length, or salt-length parameters.
- `DUMMY_PASSWORD_HASH` remains Argon2id `m=65536,t=3,p=4` and is only used to equalise failed-login verification work.
- `backend/cli/create_admin.py` also uses the default `PasswordHasher()`.
- The performance optimisation is test-only: `tests/test_api_auth.py:get_cached_hash()` caches one password hash generated with the same default `PasswordHasher()`; it neither changes production code nor lowers parameters.

Conclusion: production password hashing strength was not lowered. Status: PASS.

### Assertion weakening review

- No security assertion was removed, skipped, or relaxed.
- The existing assertion that `/docs` is 404 is retained.
- The test fixture now explicitly sets `environment="test"` and `api_docs_enabled=False`, preventing inherited preview `SECMON_*` environment variables from changing the security-default test.
- `backend/app.py` explicitly returns 404 for `/docs` before the `StaticFiles(html=True)` mount. This prevents the frontend fallback from exposing a 200 response where API docs are disabled.

Conclusion: assertions are preserved and the implementation was tightened. Status: PASS.

### Full review diff commands

The complete, reproducible application/test diff is intentionally a Git command rather than a copied partial excerpt:

```bash
git diff --no-ext-diff --unified=5 607d2b9..P5_TESTED_HEAD -- backend/app.py tests/test_api_auth.py
git diff --no-ext-diff --unified=5 P5_START_HEAD..P5_TESTED_HEAD -- backend/app.py tests/test_api_auth.py pyproject.toml
```

Reviewed post-start additions include duration-bounded firewall blocks, expiration reconciliation, audited event dispositions, safe simulated alert delivery, and their RBAC/audit assertions. The P5 changes additionally make docs denial explicit and make the fixture independent of inherited runtime settings.

## Timeout isolation and environment comparison

First sandbox stall target: `tests/test_api_auth.py::test_health_readiness_and_openapi_are_safe`.

- In the original Codex workspace-write sandbox, full `pytest -vv -s --maxfail=1` passed six `test_agy_second_repair.py` tests then stalled at this target.
- A diagnostic script passed migration, Argon2 hashing, SQLite seed, `create_app`, and `TestClient` construction; it stalled at the first `client.get("/healthz")`.
- The preserved sandbox process had a main Python thread and an `asyncio-portal-*` thread both waiting. GDB reported that debugger and target were in different PID namespaces, so it could not provide symbolized Python frames. This is evidence of TestClient/anyio portal interaction with the Codex sandbox namespace, not a SQLite lock or Argon2 delay.
- TestClient lifespan was not entered as a context manager by this fixture; no application startup handler ran for this request. The app uses short-lived SQLite connections and this test reaches the stall before a DB-backed route. No DB lock was observed.
- No timeout setting was increased.

Host isolation reruns, all with `-vv -s --maxfail=1`, no `SECMON_*` environment variables, and logs preserved in `/tmp/secmon-p5-timeout-host-run{1,2,3}.{stdout,stderr,exit}`:

| Run | Exit | Result | stderr |
| --- | ---: | --- | --- |
| 1 | 0 | 1 passed in 0.28s | 0 bytes |
| 2 | 0 | 1 passed in 0.27s | 0 bytes |
| 3 | 0 | 1 passed in 0.29s | 0 bytes |

Codex sandbox status remains FAIL: the original isolated target stalled and the same workspace-write sandbox was no longer available after permissions changed; three sandbox repetitions and complete Python-level stack traces are therefore not claimed.

## Commands and results

All commands below were run from repository root at the content later committed as the final P5 tested revision, except where explicitly marked pre-fix or sandbox.

| Gate | Command | Exit | Result |
| --- | --- | ---: | --- |
| Host pytest (pre-fix) | `pytest -vv -s --maxfail=1` | 1 | FAIL: `/docs` returned 200 from StaticFiles fallback. |
| Host pytest | `env -u SECMON_* pytest -vv -s --maxfail=1` (eight listed runtime variables removed) | 0 | PASS: 139 passed in 3.03s. |
| Clean venv install | `python -m venv /tmp/secmon-p5-final-clean-venv.KieInw; .../pip install -e '.[dev]'` | 0 | PASS. |
| Clean venv pytest | `env -u SECMON_* .../pytest -vv -s --maxfail=1` | 0 | PASS: 139 passed in 3.00s; stderr was only the pip-version notice. |
| Frontend typecheck | `cd frontend && npm run typecheck` | 0 | PASS. |
| Frontend tests | `cd frontend && npm test` | 0 | PASS: 2 passed. |
| Frontend production build | `cd frontend && npm run build` | 0 | PASS. |
| Migration smoke | `python database/migrate.py --database <fresh>;` repeated; SQLite `quick_check`, `integrity_check`, `foreign_key_check` | 0 | PASS: checks `ok`, FK rows 0, migrations through `011_p4_operations_closure`. |
| Chromium desktop/mobile | Fresh migrated DB, real Uvicorn at `127.0.0.1:8000`, Playwright Chromium login/dashboard at 1440x900 and 375x667 | 0 | PASS. |
| CSS/JS network assets | Playwright response listener for script/stylesheet non-2xx | 0 | PASS: `asset_failures=[]` for desktop and mobile. |
| Codex workspace-write sandbox pytest | `pytest -vv -s --maxfail=1` | timeout/stall | FAIL; see timeout isolation. |

## Acceptance status

- Local host pytest: PASS.
- Clean venv pytest: PASS.
- Codex workspace-write sandbox pytest: FAIL (not revalidated three times after sandbox availability changed).
- Frontend gate: PASS.
- Runtime UI: PASS on local host only.
- Independent acceptance: FAIL: sandbox evidence remains incomplete and the prior acceptance document references a stale tested HEAD.
- Release gate: FAIL.
- Formal acceptance: FAIL.
