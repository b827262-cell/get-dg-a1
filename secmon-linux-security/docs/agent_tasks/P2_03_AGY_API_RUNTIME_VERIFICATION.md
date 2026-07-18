# SecMon P2 — Agent 3 / AGY API Runtime Verification

## Fixed model and read-only role

You are Agent 3, the runtime verifier. The runner starts `agy -p` with the
Gemini 3.5 Flash High profile. The first non-empty response line must be:

```text
AGY_ACTIVE_MODEL: Gemini 3.5 Flash
```

Also record `AGY_REASONING: High`. If actual model/profile evidence is missing
or mismatched, stop; do not fallback. Do not modify product code, migrations,
tests, systemd, runtime production state, reports from other agents, or secrets.
Do not start Agent 4.

Never read or print the repository root `.env`; never use `env`, `printenv`,
shell `set`, tracing, or secret-bearing arguments. Do not use production
secrets in staging. Never stage DB/WAL/SHM, cursor, logs, or virtualenv files.

## Mode and P1 dependency

Dynamically record `origin/main` HEAD, current branch/HEAD, P1 last program
HEAD, P1 final acceptance status, Agent 1/2 tested HEADs and report commits.
Do not hard-code `080e3fe`. `RELEASE_ELIGIBLE` requires a tracked, committed P1
report whose committed blob contains `P1_FORMAL_ACCEPTANCE=PASS`, whose exact
last line is `FINAL_DECISION: P1_RELEASE_GATE_PASS`, and which records an exact
Tested Code HEAD. Its report commit must be reachable from current HEAD with no
product-code drift through that HEAD. Record `origin/main` separately. Read the
committed report blob rather than an environment variable or working-tree edit.
Otherwise use
`DEVELOPMENT_ONLY`.

In `DEVELOPMENT_ONLY`:

- use an isolated test/staging DB and a non-production port;
- do not modify or start formal production systemd;
- do not write the production DB or use formal production secrets;
- never call the result Release Ready.

Only in `RELEASE_ELIGIBLE` may you execute the production API systemd runtime
Gate. The P2 runner must stop after this report in either mode.

## Runtime verification matrix

Verify the following with real commands and sanitized evidence. Do not replace
runtime behavior with a mock, synthetic log, or hand-inserted production row:

1. API process starts and imports the actual application.
2. `GET /healthz`.
3. `GET /readyz` with SQLite/service readiness evidence.
4. Login success and failure.
5. Logout invalidates the session/token.
6. `/api/v1/auth/me`.
7. Viewer, Analyst, and Admin authorization.
8. Dashboard summary and bounded time range.
9. Events pagination, filters, detail, stable order, and page limit.
10. Attackers pagination, filters, IPv4/IPv6 detail, and threat/event bounds.
11. Log sources read-only list/detail.
12. Invalid input and injection strings.
13. Unauthenticated requests return 401.
14. Insufficient role returns 403.
15. Missing resources return 404.
16. Errors do not expose stack, absolute path, schema, secret, or account data.
17. OpenAPI schema and configuration-controlled documentation exposure.
18. CORS allowlist and proxy-header behavior.
19. API and Collector operate concurrently without regression.
20. SQLite lock and `busy_timeout` behavior.
21. API remains healthy after a controlled restart.
22. Logs contain no password, token, cookie, hash, or secret.
23. Bounded HTTP load shows no obvious FD or memory leak.
24. P1 Collector regression gates remain green.

For production mode additionally verify non-root systemd execution,
`EnvironmentFile=/etc/secmon/secmon.env`, restart-on-failure, working and
write paths, hardening, no unit secrets, and no production DB/repository
artifact leakage. For staging, explicitly mark all production-only checks
`NOT VERIFIED` rather than implying PASS.

## Report contract and stop rules

Write only:

`docs/P2_03_AGY_API_RUNTIME_VERIFICATION.md`

Include first-line model evidence, mode/P1 dependency, exact tested HEADs,
runtime environment, sanitized command/exit-code matrix, security and log
checks, findings, and whether Agent 4 may be considered. End exactly as follows:

- P1 not formally PASS and staging checks all pass:
  `STAGE_RESULT: STAGING_RUNTIME_PASS_P1_BLOCKED`
- P1 formally PASS and production checks all pass:
  `STAGE_RESULT: P2_RUNTIME_GATE_PASS`
- any technical Gate failure, missing evidence, or model mismatch:
  `STAGE_RESULT: P2_RUNTIME_GATE_NOT_PASSED`

The first outcome is a normal stop waiting for P1. The second is a normal stop
waiting for a human to invoke the independent final review. Neither starts
Agent 4. Do not modify code, commit, push, merge, close Issue #2, or send
Hermes from this Agent.
