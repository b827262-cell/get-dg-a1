# SecMon P1 — Agent 1 Preflight Report

## Current evidence

- Date: `2026-07-18` (`Asia/Taipei`)
- Project: `/home/b822726/project/get-dg-a1/secmon-linux-security`
- Current HEAD: `913f13c6a901c7f1b1a86b699e96a91adae3a7e7`
- Static Gate: PASS (`bash -n` for runtime helper, controller, and test harness)
- Controller: installed; `sudo -n /usr/local/sbin/secmon-maintenance status` PASS
- Sudo boundary: `sudo -n /usr/bin/id` rejected (exit `1`)
- Pytest: PASS (`115/115` collected and test run exit `0`)
- Agent 2, Agent 3, and Agent 4: not started

## Runtime VERIFY_ONLY evidence

The installed controller was updated with the NRestarts validator fix.  Its
installed helper SHA-256 matches the approved source SHA-256:

```text
1c307e76845449d732f5f8bb02d51ca1dcd0e81a7f483ad69299d748a76e83fc
```

The collector was already healthy, so `runtime-recovery` selected
`RUNTIME_MODE=VERIFY_ONLY`.  It did not execute `start`, `stop`, `restart`, or
`reset-failed`.  Six samples over 60 seconds produced:

```text
ActiveState=active
SubState=running
User=secmon
Group=secmon
BASELINE_MAINPID=1922369
FINAL_MAINPID=1922369
BASELINE_NRESTARTS=0
FINAL_NRESTARTS=0
MAINPID_STABLE=PASS
NRESTARTS_STABLE=PASS
```

All runtime safety gates passed:

```text
MANIFEST_METADATA_GATE=PASS
APPROVED_HEAD_GATE=PASS
RUNTIME_FILE_HASH_GATE=PASS
SYSTEMD_UNIT_HASH_GATE=PASS
MIGRATION_HASH_GATE=PASS
Restart=on-failure
RestartUSec=5s (normalized to 5000000 microseconds)
DB migration/idempotency=PASS
STAGE3_RESULT=SYSTEMD_RUNTIME_STABLE
RUNTIME_RECOVERY_EXIT=0
```

The runtime check also completed the SQLite integrity/schema and transaction
rollback capability gates.  Its journal check emitted only de-identified zero
counts for SQLite operational errors, missing tables, permission denials, and
tracebacks.  No database rows, tokens, or environment-file contents were
recorded.

## Remaining P1 scope

Telegram Smoke=NOT_RUN

SSH 3×30 seconds E2E=NOT_RUN

Replay Dedup=NOT_RUN

P1_FORMAL_ACCEPTANCE: NOT_PASSED

P1_RELEASE_GATE: NOT_PASSED

STAGE_RESULT: PREFLIGHT_PASS
