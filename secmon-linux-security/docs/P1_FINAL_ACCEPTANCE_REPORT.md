# SecMon P1 final acceptance report

Acceptance review HEAD: `b4a7b84a9c428bfe536eb27cd6c22521a31a2b01`
Owner waiver date: `2026-07-18`

## Stage matrix

| Stage | Executor | Result | Evidence |
|---|---|---|---|
| Agent 1 preflight | Codex | PASS | `PREFLIGHT_PASS`; static gates, 115 pytest tests, controller install, migration/idempotency, and 60-second VERIFY_ONLY evidence recorded. |
| Agent 2 security review | Codex fallback | APPROVE_RUNTIME_EXECUTION | Claude Code did not deliver a valid report because of its local authentication/connectors failure. The fallback and its independence limitation are disclosed in the report. |
| Agent 3 Runtime E2E | AGY, `Gemini 3.1 Pro (High)` | ACCEPTED_WITH_OWNER_WAIVERS | The original `RUNTIME_GATE_NOT_PASSED` is retained; unexecuted external checks are accepted only under the documented owner waiver. |
| Agent 4 acceptance | Codex | PASS_WITH_WAIVERS | This report and the owner-authorized waiver. |

## Verified P1 foundation

- The deployed controller status is `active/running`, MainPID `1922369`, and
  NRestarts `0`; the runtime account is documented as `secmon`.
- The Agent 1 60-second VERIFY_ONLY run recorded a stable MainPID and no
  NRestarts increase, with `Restart=on-failure` and normalized RestartUSec
  `5000000`.
- Approval-manifest metadata, approved HEAD, runtime-file, effective-unit, and
  migration-hash gates are all recorded PASS.  Migration integrity, required
  tables, and idempotency are recorded PASS.
- The least-privilege controller boundary and expiry gate passed static tests;
  a quiet tracked-file secret-signature scan found no token signature.  No
  report contains an environment-file value, database row, password, token, or
  raw journal content.

## Waived external runtime evidence

- The project owner authorized the risk waiver recorded in
  `docs/P1_ACCEPTANCE_RISK_WAIVER_2026-07-18.md`.
- Telegram API smoke remains `NOT_RUN`; Telegram human receipt is
  `WAIVED_BY_OWNER`.
- No authorized SSH endpoint was provided; SSH 3×30-second E2E is
  `WAIVED_BY_OWNER`.  No host was inferred, scanned, or contacted.
- `attack_events`, `attackers`, `log_sources`/cursor, and replay/dedup E2E
  remain `NOT_VERIFIED_DUE_TO_WAIVER`.  No synthetic event, manual SQLite
  change, fixture, or fake evidence was used.

## Release decision

The P1 technical preflight and runtime-stability evidence are PASS.  The
project owner has accepted the residual risk from the explicitly unexecuted
external E2E checks.  Agent 2 fallback remains accurately disclosed and is not
represented as GLM-5.2.  Agent 3's original `RUNTIME_GATE_NOT_PASSED` remains
part of the evidence record; its acceptance disposition is limited to the
documented owner waivers.

```text
P1_ACCEPTANCE_TYPE=OWNER_APPROVED_RISK_WAIVER
P1_TECHNICAL_PREFLIGHT=PASS
P1_RUNTIME_SERVICE_STABILITY=PASS
P1_EXTERNAL_E2E=WAIVED_BY_OWNER
P1_RESIDUAL_RISK=ACCEPTED_BY_OWNER
```

P1_FORMAL_ACCEPTANCE: PASS_WITH_WAIVERS
P1_RELEASE_GATE: PASS_WITH_WAIVERS
ISSUE_2_RECOMMENDATION: KEEP_OPEN
FINAL_DECISION: P1_RELEASE_GATE_PASS_WITH_WAIVERS
