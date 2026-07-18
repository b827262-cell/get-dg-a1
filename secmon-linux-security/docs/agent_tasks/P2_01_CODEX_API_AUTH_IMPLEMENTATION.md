# SecMon P2 — Agent 1 / Codex API Authentication Implementation

## Role and fixed launch contract

You are Agent 1, the implementation owner. The runner launches this task with
`codex exec`, model `gpt-5.6-luna`, reasoning `xhigh`, and `workspace-write`.
Record the actual model and reasoning using the exact report lines
`ACTIVE_MODEL: gpt-5.6-luna` and `REASONING_EFFORT: xhigh`. Stop after writing
the report; do not launch Agent 2, Agent 3, or Agent 4.

This stage builds the P2 framework named **SecMon REST API +
Authentication/RBAC Foundation**. It does not complete the React Web Console;
the front-end main and administration pages remain P3 scope.

## Security and Git boundary

Never read, print, or pass the repository root `.env`. Never run `env`,
`printenv`, shell `set`, tracing, or a command that can expose environment
contents. Never put a token, API key, password, cookie, session, database,
WAL/SHM, cursor, runtime log, or virtual environment into a prompt, argument,
report, log, or Git object. Use boolean-only secret scans and report only
whether they passed.

Keep the existing `.env.example` untracked and unstaged for this P2 run unless
an already-approved SecMon dependency explicitly requires it; do not create a
new dependency merely to pull that file into a P2 commit. Treat `.envO` as
forbidden and ignored.

Before changing code, fetch `origin` without printing remote credentials and
record `origin/main` HEAD, current branch/HEAD, P1 last program HEAD, and the
P1 final acceptance status. Do not write the old `080e3fe` value as a permanent
baseline. Work only on `feature/secmon-p2-api-auth`:

- if creating it, preserve all existing user changes and never use reset or clean;
- if it exists, record its base and ahead/behind plus unique commits;
- do not force-move the branch or implement P2 directly on `main`;
- do not merge or push `main`.

Determine `DEVELOPMENT_ONLY` versus `RELEASE_ELIGIBLE` from trusted P1 evidence,
not a file's presence. `RELEASE_ELIGIBLE` requires a tracked, committed report
whose committed blob contains the exact line `P1_FORMAL_ACCEPTANCE=PASS`, whose
exact last line is `FINAL_DECISION: P1_RELEASE_GATE_PASS`, and which records an
exact Tested Code HEAD. The report commit must be reachable from current HEAD,
with no product-code drift from Tested Code HEAD through the report commit and
current HEAD. Record `origin/main` separately, but do not replace committed
local P1 evidence with an environment variable or uncommitted working-tree
edit. Otherwise remain `DEVELOPMENT_ONLY`.

In `DEVELOPMENT_ONLY`, P2 code/tests and isolated staging are permitted, but do
not use production systemd or secrets, merge main, close Issue #2, or claim
P2 Release Ready. Keep P1 Collector, SQLite, and Telegram behavior intact.

## Architecture reconnaissance

Before selecting an implementation, inspect `pyproject.toml`, the ADRs,
`systemd/secmon-api.service`, existing dependencies, package layout, database
module and migration runner. Prefer the repository's specified framework and
the existing `backend.app:app` systemd contract. Do not replace the framework
without a documented repository-driven reason.

## Required implementation

Implement only the following read-oriented P2 surface, with versioned routes
under `/api/v1` and request/response schemas:

### Health and errors

- `GET /healthz` returns minimal liveness information only.
- `GET /readyz` checks SQLite connectivity and required service state.
- Public health responses never expose absolute paths, tokens, DB schema,
  stack traces, exception details, or internal accounts; detailed health is
  authorized only.
- Every request gets a request ID. All errors use one contract such as
  `{"error":{"code":"INVALID_FILTER","message":"Invalid request","request_id":"..."}}`.
  Use correct 4xx/5xx codes, no production stack traces, and no path/schema
  leakage from 404s.

### Authentication and bootstrap

- `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, and
  `GET /api/v1/auth/me`.
- Use a maintained password hashing library, preferably Argon2id; use bcrypt
  only if the existing project is standardized on it. Never invent hashing or
  encryption, store plaintext passwords, return/log password or hash values,
  or reveal whether an account exists on login failure.
- Add basic login failure limiting or cooldown.
- Use a maintained session/token library. Secrets come only from formal
  environment configuration; none may be written to Git. Tokens/sessions never
  go in a URL query string. Bearer mode must be short-lived and validate issuer
  and expiry without logging a complete token. Cookie mode must be HttpOnly,
  SameSite, Secure in production, and have explicit CSRF handling.
- Provide `python -m backend.cli.create_admin` (or the repository-equivalent
  CLI). Read the password interactively; never accept it in command arguments,
  hard-code a default, overwrite an existing Admin without an explicit guard,
  or print password/hash. Record create/modify outcomes in the audit log.

### RBAC and read-only resources

Use the existing roles Admin, Analyst, and Viewer. Viewer can read dashboard,
events, attackers, and log sources. Analyst has the same read rights and a
future alerts-operation extension point. Admin has the Analyst read rights;
account management may remain deferred unless existing specifications require
it. Do not add automatic blocking, nftables/whitelist writes, alert state
changes, bulk event deletion, or arbitrary SQL execution.

Implement:

- `GET /api/v1/dashboard/summary`: selected-period event count, distinct attack
  IP count, high-risk event/attacker count, current read-only block count,
  log-source health summary, and latest event time. Validate time formats,
  enforce a maximum range, and prevent unbounded scans.
- `GET /api/v1/events`, `GET /api/v1/events/{event_id}` with start/end time,
  source IP, attack type, severity, log source, username, bounded page size
  (maximum 200), stable sorting, strict event ID validation, bounded raw-log
  output, parameterized SQL only, and no HTML generation or raw SQL input.
- `GET /api/v1/attackers`, `GET /api/v1/attackers/{ip}` with strict IPv4/IPv6
  parsing, IP, minimum threat score/event count, last-seen range, status,
  bounded pagination, and stable sorting. Detail includes summary, attack-type
  statistics, recent events, related usernames, read-only block status, and
  alert summary. Never concatenate an IP into SQL.
- `GET /api/v1/log-sources`, `GET /api/v1/log-sources/{source_id}` with name,
  type, enabled, health, last event, events today, parse errors, and a safe
  summary of last error. Never expose sensitive files or arbitrary paths.

### OpenAPI, CORS, proxy, and SQLite

- OpenAPI generation must work and describe every endpoint's request/response
  schema. Swagger UI exposure is configuration-controlled. No real secrets in
  schema examples.
- Production CORS is an allowlist, never `*`. Trust proxy headers only when
  explicitly configured; never trust arbitrary `X-Forwarded-For`. Default API
  binding is loopback or an explicitly configured interface.
- Reuse the migration runner. Never edit an existing migration; add a new
  migration (for example `002`). Prove fresh and repeat migration success.
  SQLite must enable `foreign_keys`, set `busy_timeout`, remain WAL-compatible,
  preserve Collector transaction behavior, and have indexes appropriate to API
  reads. Never put a production DB in the repository.

### systemd API service

Repair or complete `systemd/secmon-api.service` while preserving the existing
service contract. Verify the actual entrypoint exists, runs non-root, references
`EnvironmentFile=/etc/secmon/secmon.env`, has `Restart=on-failure`,
`WorkingDirectory=/opt/secmon`, `NoNewPrivileges=true`, `ProtectSystem=strict`,
`ProtectHome=true`, `PrivateTmp=true`, explicit `ReadWritePaths`, and no unit
embedded secrets. Prove API and Collector can coexist; in
`DEVELOPMENT_ONLY`, use staging rather than changing formal production service
state or starting production services. Updating and testing the
version-controlled `systemd/secmon-api.service` unit template remains required;
installing or activating that unit in production is forbidden in this mode.

## Required gates

Run and record sanitized results for compileall, Ruff, mypy, pytest, `make
check`, fresh/repeat migrations, SQLite `quick_check`,
`foreign_key_check`, API import, OpenAPI generation, unauthenticated rejection,
login success/failure, role authorization, pagination, invalid filters, SQL
injection strings, IPv4/IPv6 validation, CORS, no-stack-trace responses, no
secret logging, Collector regression, and all existing front-end gates.
Unavailable production-only checks must be marked `NOT VERIFIED`, never
represented as PASS.

Before any optional commit, show `git diff --cached --name-status`, stage only
exact safe paths, reject `.env`, `.envO`, `secmon.env`, DB/WAL/SHM, cursor,
runtime logs, and virtual environments, then run a no-content secret scan.
Do not use `git add .`, `git add -A`, or `git commit -am`.

## Report contract

Write only the sanitized report:

`docs/P2_01_CODEX_API_AUTH_IMPLEMENTATION_REPORT.md`

Include dynamic Git/P1 evidence, branch, implementation and migration summary,
gate matrix, dependency mode, changed exact paths, findings by severity,
secret-scan result, and next action. End with exactly one of:

```text
STAGE_RESULT: READY_FOR_GLM52_REVIEW
```

or

```text
STAGE_RESULT: BLOCKED
```

Do not launch any later Agent.
