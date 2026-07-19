# P4 Master Plan

## Authorized baseline

- Start branch: `feature/secmon-p4-detection-operations`
- Start HEAD: `df9995329d987b646c1ab89cca65096dfc762de4`
- Baseline result: `P4_PREIMPLEMENTATION_BASELINE_PASS`

## Delivery ownership

| Owner | Scope | Independent acceptance evidence |
| --- | --- | --- |
| Agent 1 | Data model, migrations, REST APIs, RBAC, audit and backend tests | migration repeatability; 401/403/IDOR and block/allowlist evidence |
| Agent 2 | Routes, operations UI, safe action flows and frontend tests | guarded navigation, error states, confirmations and reason capture |
| Agent 3 | Threat model and independent review/runtime evidence | reproducible commands, exit codes and security findings |
| Main Codex | Integration, remediation, full gates, release decision | report-to-code-to-log cross-check |

## Required capabilities

1. Security dashboard with time/severity filters and stateful data views.
2. Event list/detail and handling lifecycle.
3. Attack-IP block, unblock, allowlist and expiry operations guarded by backend RBAC.
4. Alert policy, delivery status and truthful simulation/test-notification behavior.
5. Append-only audit history including actor, reason, before/after and outcome.
6. Service health, deployment/version/migration visibility, rollback guidance, runtime smoke and restart persistence.

## Gate sequence

1. Migration fresh/repeat and SQLite integrity checks.
2. Backend unit/integration plus API authorization and IDOR checks.
3. Frontend test, typecheck and build.
4. Runtime health/login/role/event/IP/allowlist/audit/alert/restart smoke.
5. Independent security review and remediation of Critical/High findings.
6. Main-Codex evidence cross-check and final release determination.
