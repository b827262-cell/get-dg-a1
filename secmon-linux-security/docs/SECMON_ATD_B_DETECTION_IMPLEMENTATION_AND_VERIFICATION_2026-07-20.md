# SecMon ATD-B Detection Implementation and Verification

Date: 2026-07-20 (Asia/Taipei)
Branch: `feature/secmon-atd-b-detection`
Start HEAD: `70ef2db45a8f325d2b737fe2f1707a582bde825a` (ATD-A verified HEAD)
End HEAD: `0081d51d75067567b0ffdf66559bc4bbe3e105aa` (implementation commit)

## Scope and implementation

ATD-B now consumes the existing zero-privilege `network_samples` interface
counters and executes:

`sample -> validation -> delta/rate -> warm-up -> baseline/deviation -> sustained-window state machine -> dedup/cooldown/recovery -> SQLite event -> authenticated API`.

For a sampling interval `dt > 0`:

- `bytes/sec = (Δrx_bytes + Δtx_bytes) / dt`
- `bits/sec = bytes/sec * 8`
- `packets/sec = (Δrx_packets + Δtx_packets) / dt`
- dynamic threshold is `max(fixed_rate_threshold, baseline * deviation_ratio, minimum_absolute_delta)`.

Negative counters, negative deltas, reset/wrap, missing counters, equal or
timezone-less timestamps, NaN, Infinity, and non-positive `dt` produce no rate
and no alert. Baseline is a per-interface rolling mean; the point under test is
not added when anomalous, so a sustained spike cannot raise its own threshold.
Warm-up requires the configured number of valid prior rates. Defaults are a
20-sample window, 5 warm-up samples, ratio 2.0, 3 anomalous samples to alert,
3 normal samples to resolve, 300-second cooldown, and 60-second duplicate
suppression. Configuration is Pydantic-validated and the detector validates
again at runtime.

State transitions are `NORMAL -> WATCH -> ALERT -> RECOVERING -> RESOLVED ->
NORMAL`. Recovery is always emitted even during alert cooldown. Detector state
is intentionally process-local; after a service restart the baseline is rebuilt
from warm-up samples and no stale in-memory state is trusted.

## Database and API

Migration `013_atd_b_traffic_alerts.sql` adds `traffic_alerts` with interface,
ifindex, detector type, severity/state, observed rate, baseline, threshold,
deviation ratio, first/last seen, count, resolved time, evidence, nullable IP
attribution fields, and a unique event key. It uses a foreign key with cascade
and bounded indexes. Re-running the migration runner is idempotent.

Read access is protected by the existing JWT `require_read` dependency:

- `GET /api/v1/network/anomalies`
- `GET /api/v1/network/anomalies/{id}`
- `PATCH /api/v1/network/anomalies/{id}/resolved` (admin only)

Queries use fixed SQL ordering and parameters; there is no client-controlled
SQL fragment or arbitrary sort field. Unknown IDs return the generic 404 error.

## IP attribution limitation

The input contains only interface counters. Every ATD-B event is explicitly
`interface-level anomaly`; `source_ip`, `destination_ip`, `port`, and
`protocol` remain `NULL`/unknown. No attack traffic is generated and no source
IP is guessed or fabricated. Full flow attribution requires a separate,
approved collector scope.

## Verification evidence

| Gate | Result |
|---|---|
| ATD-B unit/API/migration/collector tests | PASS — 35 passed |
| Full backend pytest including ATD-A regression | PASS — 173 passed |
| ruff | PASS — `All checks passed!` |
| mypy | PASS — no issues in 22 source files |
| `make check` with project `.venv` | PASS — lint, typecheck, pytest, frontend build |
| frontend test | PASS — 2 tests |
| frontend typecheck | PASS |
| frontend build | PASS |
| migration fresh/repeat | PASS — 10 migration versions, repeat no-op |
| SQLite `quick_check` | PASS — `ok` |
| SQLite `foreign_key_check` | PASS — `[]` |
| synthetic normal/spike/sustained/recovery/reset | PASS — reset yielded no rate; sustained yielded ALERT; recovery yielded RESOLVED |
| restart baseline rebuild | PASS — fresh detector remained NORMAL until warm-up |
| non-root/CapEff | PASS — current runtime uid 1000; `CapEff=0x0`; systemd uses `User=secmon`, `NoNewPrivileges=true` |
| isolated HTTP runtime restart script | BLOCKED — executed with injected credentials, but the environment could not complete the preconditioned nftables operation; no ATD-B code path failed |

Security review found no new TODO/FIXME/NotImplemented, shell=True, debug
endpoint, dynamic sort, or unaudited SQL in ATD-B. The existing isolated P4
runtime helper was changed to require credentials from environment rather than
embedding them. API errors continue to redact DB/secret/stack details. No
systemd capability or root-runtime change was made.

## Files changed

- `backend/services/traffic_detector.py`
- `backend/collectors/network_metrics.py`
- `backend/config.py`
- `backend/app.py`
- `database/migrations/013_atd_b_traffic_alerts.sql`
- `tests/test_atd_b.py`
- `scripts/p4_backend_restart_runtime.py` (credential hygiene)
- this verification document

## Known limitations, rollback, and decision

ATD-B observes only this host's interface counters, not other company hosts;
there is no IP/port/protocol attribution, packet payload, or cross-host flow
correlation. The detector is opt-in (`SECMON_ATD_B_ENABLED=false` by default),
and process restart causes warm-up. Very high legitimate rates still require
operator-calibrated fixed thresholds or allowlisted operating windows.

Rollback is to the recorded ATD-A HEAD by stopping the collector, restoring the
previous application artifact, and leaving migration 013 unapplied on a
rollback database copy; do not delete production data. The migration is
additive and the event table can be retained for forensic read-only use.

ATD_B_IMPLEMENTATION_STATUS: PASS
ATD_B_QUALITY_GATE_STATUS: PASS
ATD_B_RUNTIME_STATUS: INCONCLUSIVE (static/non-root and synthetic PASS; isolated HTTP restart BLOCKED by nftables environment)
ATD_B_SECURITY_VALIDATION: PASS for implemented scope
ATD_B_RELEASE_GATE: INCONCLUSIVE
ATD_B_FORMAL_ACCEPTANCE: PENDING_INDEPENDENT_VERIFICATION

Implementation, tests, migration, privilege, and code-level security evidence
are complete. The overall release gate remains INCONCLUSIVE because the
isolated HTTP restart runtime could not run through its nftables precondition.
Formal acceptance is intentionally pending an independent verifier and is not
claimed by the implementer.
