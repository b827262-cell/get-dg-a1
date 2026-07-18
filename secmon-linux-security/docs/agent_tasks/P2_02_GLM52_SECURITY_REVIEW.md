# SecMon P2 — Agent 2 / GLM-5.2 Independent Security Review

## Fixed model and boundary

You are the independent security reviewer. The runner launches exactly
`claude -p --model glm-5.2` with the maximum available review depth and then
verifies the structured active model. The first report evidence line must be:

```text
ACTIVE_MODEL: glm-5.2
```

If the actual model is not exactly `glm-5.2`, or identity cannot be verified,
stop and write `STAGE_RESULT: REJECTED`; never fallback. Do not start Agent 3.

Do not modify product code, migrations, tests, systemd, runtime state, branch
history, Issue #2, or any previous report. The only permitted file write is:

`docs/P2_02_GLM52_SECURITY_REVIEW.md`

Never read or print the repository root `.env`, use `env`, `printenv`, shell
`set`, or expose any token, API key, password, cookie, session, DB, WAL/SHM,
cursor, or runtime log. Secret scans are boolean-only. Do not use broad Git
staging or change user-owned work. Confirm `.env.example` remains outside the
P2 change set unless an approved existing SecMon dependency proves it is
required, and confirm `.envO` remains ignored and unstaged.

## Independent dependency and evidence review

Record `origin/main` HEAD, current branch/HEAD, P1 last program HEAD, P1 final
acceptance status, Agent 1 tested code HEAD, and report commits dynamically.
Do not hard-code `080e3fe`. A P1 PASS requires a tracked, committed report whose
committed blob contains `P1_FORMAL_ACCEPTANCE=PASS`, ends exactly with
`FINAL_DECISION: P1_RELEASE_GATE_PASS`, records an exact Tested Code HEAD, and
has a report commit reachable from current HEAD with no product-code drift
through that HEAD. Record `origin/main` separately. Read the report from its
committed blob, not an environment variable or uncommitted working-tree edit.
If absent, classify the P2 run as
`DEVELOPMENT_ONLY`; do not bless production eligibility.

Independently verify Agent 1's branch strategy, changed paths, report marker,
actual tested HEAD, code/report relationship, and no post-test code drift. Do
not trust a claim merely because the report exists or a command exited zero.

## Required review coverage

Review the implementation and independently rerun feasible read-only gates for:

1. API architecture, repository framework/ADR alignment, `backend.app:app`,
   versioned `/api/v1`, request/response schemas, OpenAPI generation, and the
   health/readiness disclosure boundary.
2. Auth library choice, Argon2id/bcrypt configuration, no plaintext or custom
   crypto, login enumeration resistance, failure limiting/cooldown, session or
   bearer token expiry/issuer/logout behavior, cookie flags/CSRF, secret source,
   and secret absence from logs/responses/URLs.
3. Admin bootstrap: interactive password input, no CLI password/default,
   no silent Admin overwrite, audit logging, and no password/hash output.
4. RBAC bypasses, Viewer/Analyst/Admin authorization, 401/403 behavior, and
   absence of prohibited write features (auto-block, nftables/whitelist,
   alert changes, bulk deletion, arbitrary SQL).
5. Dashboard range limits and indexes; Events filters, strict IDs, stable
   pagination/sort, bounded raw logs, parameterized SQL, injection strings,
   and no raw SQL/HTML; Attackers IP parsing for IPv4/IPv6, filters, detail
   joins, and SQL safety; Log Sources read-only fields and safe error summary.
6. Error contract, request IDs, correct 4xx/5xx, 404 behavior, no stack/path/
   schema/secret leakage, production logging, CORS allowlist, proxy trust, and
   configured bind address.
7. Migration immutability, fresh/repeat behavior, schema/index correctness,
   foreign keys, busy timeout, WAL/concurrency, and Collector transaction and
   regression safety.
8. API systemd entrypoint and hardening: non-root, EnvironmentFile reference,
   restart policy, WorkingDirectory, NoNewPrivileges, ProtectSystem,
   ProtectHome, PrivateTmp, explicit write paths, no unit secrets, and API /
   Collector coexistence.
9. Git secret hygiene, prohibited runtime artifacts, P1 boundary, and no P3
   React console functionality being misreported as complete.

Rerun compileall, Ruff, mypy, pytest, `make check`, fresh/repeat migrations,
SQLite `quick_check`, `foreign_key_check`, API import/OpenAPI checks, and safe
unauthenticated/auth/RBAC/filter/pagination/CORS/error/Collector tests where
the environment permits. Mark unavailable checks `NOT VERIFIED`.

## Report and gate

The report must identify the actual model first, list dynamic HEADs and report
commit relationships, give an evidence matrix, findings by Blocker/High/
Medium/Low, and state whether Agent 3 may run. Define exact counts:

```text
BLOCKER_COUNT: <integer>
HIGH_COUNT: <integer>
```

Only with `BLOCKER_COUNT: 0` and `HIGH_COUNT: 0`, complete evidence, and no
model mismatch may the final line be:

```text
STAGE_RESULT: APPROVE_FOR_AGY
```

Otherwise the final line must be:

```text
STAGE_RESULT: REJECTED
```

Stop after the report. Do not repair, commit, push, start Agent 3, or send
Hermes from this Agent.
