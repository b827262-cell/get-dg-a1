# SecMon P1 acceptance risk waiver — 2026-07-18

## Authority and scope

```text
WAIVER_AUTHORITY=PROJECT_OWNER
WAIVER_DATE=2026-07-18
```

The project owner has explicitly authorized this P1 acceptance decision without
running the external runtime checks listed below.  This document records a
risk acceptance; it does not represent any waived check as passed.

## Waived external verification

```text
TELEGRAM_API_SMOKE=NOT_RUN
TELEGRAM_HUMAN_RECEIPT=WAIVED_BY_OWNER

SSH_AUTHORIZED_ENDPOINT=NOT_PROVIDED
SSH_E2E_3X30=WAIVED_BY_OWNER

ATTACK_EVENTS_E2E=NOT_VERIFIED_DUE_TO_WAIVER
ATTACKERS_AGGREGATION_E2E=NOT_VERIFIED_DUE_TO_WAIVER
LOG_SOURCES_CURSOR_E2E=NOT_VERIFIED_DUE_TO_WAIVER
REPLAY_DEDUP_E2E=NOT_VERIFIED_DUE_TO_WAIVER
```

## Accepted residual risk

- A real SSH failed-login flow has not been shown to create a complete
  `attack_events` record.
- `attackers` aggregation has not been shown to update from a real attack
  event.
- A log-source cursor has not been shown to advance in a real E2E flow.
- A Telegram message has not been confirmed as received by a human.
- Replay/dedup has not been verified against a real event.
- This waiver does not mean that any of the above tests passed.
- Before a formal company deployment, the waived tests should be performed
  again with an explicitly authorized endpoint and a secret-safe Telegram
  verification procedure.
