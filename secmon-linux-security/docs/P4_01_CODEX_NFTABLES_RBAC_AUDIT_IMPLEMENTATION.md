# P4-01 Codex nftables, RBAC and audit implementation

## Delivered

- `backend/services/nftables.py` provides the sole nftables boundary. It parses
  addresses with `ipaddress`, accepts IPv4 and IPv6 host addresses, and only
  targets the fixed `inet secmon` table, `blocked_ipv4` and `blocked_ipv6`
  sets. Calls use `subprocess.run` with an argv list, `shell=False` by default,
  `check=False`, capture, a bounded timeout, and explicit return-code handling.
  The service has no `os.system` or shell command construction.
- `backend/app.py` adds authenticated status and block-list reads, analyst/admin
  previews, and admin-only block/unblock operations. Roles are enforced in the
  backend for every route; UI visibility is not treated as authorization.
  Canonical routes are `GET /api/v1/firewall/status`,
  `POST /api/v1/firewall/preview`, `GET|POST /api/v1/firewall/blocks`, and
  `DELETE /api/v1/firewall/blocks/{ip}`. Compatibility block/unblock aliases
  remain for existing callers.
- Block/unblock database changes are coordinated with nftables: a failed DB
  commit attempts the inverse firewall operation. Repeated requests return a
  successful idempotent result. The partial active-block uniqueness constraint
  remains the concurrent-request guard.
- `database/migrations/009_nftables_audit.sql` adds firewall audit metadata and
  supporting indexes. The admin audit API is paginated, admin-only, and
  redacts password, token, authorization, secret and credential values.
- `frontend/src/main.ts` supplies the admin firewall controls using the
  canonical APIs and memory-only bearer credentials.
- `tests/test_nftables.py`, `tests/test_api_auth.py`, and the frontend smoke
  check cover argv safety, IPv4/IPv6 parsing, failure behavior, RBAC, IDOR-like
  direct API access, idempotence, audit visibility/redaction, and UI wiring.

## Commands and outcomes

- `python -m compileall -q backend` — passed.
- `python -c '... migrate(...) ... PRAGMA quick_check ... foreign_key_check ...'`
  against `/tmp/secmon-p4-migration-check.db` — passed: `quick_check` was `ok`,
  foreign-key check was empty, and audit metadata columns were present.
- `npm test --prefix frontend` — passed (1/1).
- `git diff --check` — passed.
- `python -m pytest ...` could not be run in this execution environment because
  the installed Python interpreter does not include `pytest`; no dependencies
  were installed or changed as part of this task.

No branch was pushed, merged, or submitted as a pull request.
