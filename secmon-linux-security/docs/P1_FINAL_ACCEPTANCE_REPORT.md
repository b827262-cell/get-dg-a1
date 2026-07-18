# SecMon P1 final acceptance report

Tested HEAD: `913f13c6a901c7f1b1a86b699e96a91adae3a7e7`

## Stage matrix

| Stage | Executor | Result | Evidence |
|---|---|---|---|
| Agent 1 preflight | Codex | PASS | `PREFLIGHT_PASS`; static gates, 115 pytest tests, controller install, migration/idempotency, and 60-second VERIFY_ONLY evidence recorded. |
| Agent 2 security review | Codex fallback | APPROVE_RUNTIME_EXECUTION | Claude Code did not deliver a valid report because of its local authentication/connectors failure. The fallback and its independence limitation are disclosed in the report. |
| Agent 3 Runtime E2E | AGY, `Gemini 3.1 Pro (High)` | NOT PASSED | Valid AGY report; it did not claim unavailable production evidence. |
| Agent 4 acceptance | Codex | NOT PASSED | This report. |

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

## Blocking missing runtime evidence

- Telegram API smoke: NOT_RUN.  No secret-safe operational route was available
  to send the requested alert without extracting credentials.
- Telegram human receipt: UNVERIFIED.
- Authorized SSH endpoint: NOT_FOUND.  No host was inferred, scanned, or
  contacted; therefore the three 30-second SSH E2E windows were NOT_RUN.
- Genuine `attack_events`, `attackers`, `log_sources`/cursor, and replay/dedup
  evidence: UNVERIFIED.  No synthetic event, manual SQLite change, fixture, or
  fake evidence was used.

## Release decision

The P1 runtime foundation is healthy, but the required real Telegram transport
and human receipt, explicitly authorized SSH three-window E2E, aggregation and
cursor deltas, and replay/dedup proof are absent.  Agent 2 fallback is
accurately disclosed and is not represented as GLM-5.2.  Agent 3 accurately
returned `RUNTIME_GATE_NOT_PASSED`; its conclusion blocks formal acceptance.

P1_FORMAL_ACCEPTANCE: NOT_PASSED
P1_RELEASE_GATE: NOT_PASSED
ISSUE_2_RECOMMENDATION: KEEP_OPEN
FINAL_DECISION: P1_RELEASE_GATE_NOT_PASSED
