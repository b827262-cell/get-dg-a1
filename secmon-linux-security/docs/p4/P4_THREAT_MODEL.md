# P4 Agent 3 Threat Model and Independent Test Plan

- Reviewer: Agent 3 (GPT-5.4 mini)
- Review mode: independent, read-only of implementation; reports only
- Baseline branch / commit: `feature/secmon-p4-detection-operations` / `df9995329d987b646c1ab89cca65096dfc762de4`
- Observation time: 2026-07-19 (Asia/Taipei)
- Scope: P4 detection operations API/UI, SQLite records, audit evidence, firewall boundary, and service/runtime delivery.

## Security assets and trust boundaries

| Asset / boundary | Threat | Required control / independent check | Baseline status |
| --- | --- | --- | --- |
| Bearer session and user identity | token theft, forged/expired/revoked session, account enumeration | HS256 issuer verification; server-side session lookup/revocation; generic auth failures; bounded login attempts | PASS for existing P2 implementation; re-test P4 routes after handoff |
| RBAC-protected operations | viewer/analyst access to admin mutation, direct API bypass of UI guard | endpoint-level `require_admin`/`require_analyst`; 401/403 matrix for every new P4 route | PASS for visible P4 routes: alerts write requires analyst/admin; allowlist and firewall mutations require admin; final rerun after remediation |
| Object identifiers and cross-user data | IDOR by event, alert, attacker, user, or audit identifier | parameterized lookups; non-enumerating 404/403; ownership/role constraints where applicable | PASS for visible role-scoped global operations and parameterized alert/allowlist identifiers; no per-user alert ownership model exists to test |
| Detection/event search | SQL injection, excessive response/range scans, sensitive raw log leakage | bind parameters; strict bounded pagination/ranges; output allowlist/truncation; test injection payloads | PASS for existing `/events`; BLOCKED for P4 additions |
| Browser console | XSS, token persistence/exfiltration, route-guard bypass, CSRF | DOM `textContent`/no HTML injection; in-memory token only; backend bearer auth; safe 401/403 handling; CORS non-permissive | PASS for visible P4 UI static review and frontend checks; backend remains the authorization boundary |
| Firewall operation | SSRF/command injection, arbitrary ruleset alteration, privilege escalation, host lockout | parsed non-special IP only; fixed `/usr/sbin/nft`; argv invocation/no shell; dedicated `inet secmon` table; admin-only mutation; isolated runtime test | PASS for existing P4 firewall adapter/tests; final kernel check NOT TESTED |
| Allowlist and auto action | allowlisted or protected IP blocked; bypass through CIDR/canonicalization/races | canonical IPv4/IPv6/CIDR matching before all write/auto-block paths; auditable denial; concurrency tests | PASS for visible manual-block exact/CIDR enforcement (independent probe: 201 add, 409 block denial); auto-block is disabled by default and has no observed execution path |
| Audit evidence | audit deletion/update, secret leakage, forged action result | DB triggers prevent update/delete; app redaction; admin-only read; test direct SQL and error paths | PASS after remediation: independent probe verified accurate `alert`/`allowlist` target types and persisted alert/unblock/allowlist-remove reasons; fresh migration still rejects audit UPDATE/DELETE. |
| SQLite/migrations | partial/unsafe schema update, FK loss, migration replay failure | clean DB migration twice; quick/integrity/FK checks; test old-to-new compatibility and rollback procedure | BLOCKED pending completed Agent 1 migration set |
| Deployment/runtime | over-privileged service, secret disclosure, unsafe recovery, live-host firewall change | systemd isolation/least privilege; root-owned approval manifest; no repository `.env`; isolated netns/container gate; documented rollback | PARTIAL from static baseline; final deployment evidence NOT TESTED |

## Planned independent verification matrix

| Area | Command / method to run after handoff | Passing evidence required | Status |
| --- | --- | --- | --- |
| Static quality | shared-development-venv `ruff check backend database tests`; `mypy backend database` | exit 0 and no diagnostics | PASS at baseline; rerun final |
| Backend regression | shared-development-venv `python -m pytest` | exit 0 with final count | NOT TESTED against completed P4 implementation |
| Auth/RBAC/IDOR | focused pytest plus `TestClient` matrix for unauthenticated/viewer/analyst/admin on every new route | exit 0; forbidden mutation and cross-object access observable | BLOCKED |
| Injection/validation | hostile query/path/body values including SQL metacharacters, IP/CIDR edge cases, oversized reason/filter | stable 4xx; no data expansion/stack trace; no command execution | BLOCKED |
| Audit integrity | fresh migration then direct SQLite `UPDATE`/`DELETE audit_logs`; API audit-redaction cases | both mutation attempts abort; redacted response; exit 0 | BLOCKED |
| Allowlist protection | create enabled/disabled exact IP and CIDR cases; attempt manual and auto block | protected targets denied with truthful audit; unprotected targets retain correct behavior | BLOCKED |
| Frontend | `npm test`, `npm run typecheck`, `npm run build`; inspect P4 rendering/action flows | exit 0; no unsafe HTML sink / token persistence | BLOCKED |
| Migration health | migrate clean temp DB twice; `quick_check`, `integrity_check`, `foreign_key_check`; inspect schema/indexes/triggers | exit 0; `ok`; no FK rows; expected schema | BLOCKED |
| Isolated kernel | `scripts/p4_real_kernel_runtime.sh` | exit 0 and `P4_HOST_ISOLATION_PASS`; never run against live host table | NOT TESTED |
| systemd/secrets/recovery | static review plus a non-production staging install/restart/rollback record | no secret in repo/unit logs; least privilege and recoverable rollback evidence | NOT TESTED |

## Baseline observations

- `backend/app.py` uses parameter binding for the existing events/attacker filters, bounds page size to 200 and date ranges to 31 days, and truncates returned raw logs to 2048 characters.
- Existing browser code in `frontend/src/main.ts` builds displayed content with `textContent` / DOM nodes, URL-encodes the firewall path IP, and keeps the bearer token in memory. It is not evidence for the new P4 UI until that implementation is delivered.
- Existing firewall calls are fixed-argv `subprocess.run` calls to a settings-constrained `/usr/sbin/nft`; parsed addresses reject loopback, unspecified, and multicast addresses. This limits command injection and host-ruleset scope, but it does not by itself demonstrate P4 allowlist enforcement.
- `systemd/secmon-api.service` and `systemd/secmon-collector.service` run as `secmon`, set `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, and constrain write paths. These are static configuration observations, not a deployed-service verification.

This document intentionally does not provide release acceptance.
