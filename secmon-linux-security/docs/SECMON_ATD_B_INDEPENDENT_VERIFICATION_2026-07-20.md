# SecMon ATD-B Independent Verification — 2026-07-20

## Decision summary

ATD_B_INDEPENDENT_IMPLEMENTATION_REVIEW: PASS
ATD_B_INDEPENDENT_QUALITY_GATE: PASS
ATD_B_INDEPENDENT_RUNTIME_STATUS: BLOCKED
ATD_B_INDEPENDENT_SECURITY_VALIDATION: PASS (static/API scope); runtime portion BLOCKED
ATD_B_RELEASE_GATE: INCONCLUSIVE
ATD_B_FORMAL_ACCEPTANCE: PENDING_INDEPENDENT_VERIFICATION

FINAL_DECISION: INCONCLUSIVE

The implementation and independent software-quality/security checks passed. The
required privileged nftables and HTTP restart runtime evidence could not be
completed in this environment, so the release gate is not passed.

## Git identity and drift

Commands executed from the project root:

```text
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline 70ef2db..HEAD
git show --stat --oneline 0081d51
git show --stat --oneline 0b1e0c3
```

Results:

```text
branch: feature/secmon-atd-b-detection
HEAD: 0b1e0c30d5e881cbb04cfb3324d8a6fe41f6a9bd
status: empty / clean
70ef2db..HEAD:
0b1e0c3 docs(atd): record implementation verification head
0081d51 feat(atd): implement anomaly traffic detection engine
```

`0081d51` contains the ATD-B implementation, migration, API, collector wiring,
tests, runtime-helper secret hygiene, and implementation report. `0b1e0c3`
only updates the implementation report's recorded end HEAD; it does not alter
product code, migrations, or tests. No main merge or reset was performed.

## Independent quality evidence

The first literal `make check` and `pytest` invocations were recorded as
environment failures because the shell PATH did not contain `.venv/bin`:
`ruff: Permission denied` and `pytest: command not found`. The same formal
commands were then rerun with `PATH="$PWD/.venv/bin:$PATH"`.

| Gate | Independent result |
|---|---|
| `PATH="$PWD/.venv/bin:$PATH" make check` | PASS; ruff, mypy, pytest 173 passed, frontend build |
| `PATH="$PWD/.venv/bin:$PATH" pytest` | PASS; 173 passed in 5.52s |
| `pytest -q tests/test_atd_b.py` | PASS; 10 passed |
| ATD-A/collector/API/migration tests (`test_atd_api.py test_atd_collector.py test_api_auth.py test_migrate.py`) | PASS; 43 passed |
| Frontend test | PASS; 2 passed |
| Frontend typecheck | PASS |
| Frontend build | PASS |
| ruff | PASS |
| mypy | PASS; 22 source files |
| migration fresh/repeat | PASS |
| SQLite `PRAGMA quick_check` | PASS; `ok` |
| SQLite `PRAGMA foreign_key_check` | PASS; `[]` |

The requested `tests/test_atd_a.py` path does not exist in this checkout; it
returned `ERROR: file or directory not found`. ATD-A regression was therefore
run using the actual ATD-A test modules listed above and the full suite.

## Functional probes

Independent synthetic probes produced:

```text
rate RateResult(elapsed_seconds=2.0, bytes_per_sec=750.0,
                bits_per_sec=6000.0, packets_per_sec=8.0, ...)
zero_time_delta: invalid=True, no rate
counter_reset: reset=True, no rate
states: NORMAL, NORMAL, NORMAL, WATCH, ALERT(anomaly),
        RECOVERING, RESOLVED(resolved), NORMAL
restart_rebuild: NORMAL, no event
```

The code review and tests independently covered counter reset, missing/invalid
counters, non-positive timestamps, warm-up, rolling baseline, sustained
anomaly, cooldown/deduplication, recovery, interface isolation, restart
baseline rebuild, bounded API parameters, and unknown IP attribution. The
event schema retains source IP, destination IP, port, and protocol as NULL
when only interface counters exist; no attack IP was inferred.

## API and security evidence

An independent temporary SQLite database and TestClient probe returned:

```text
unauth_list 401
viewer_list 200
viewer_detail 200
idor_missing 404
viewer_resolve 403
bad_state 422
bad_interface 422
bad_page 422
```

The ATD-B routes use authenticated dependencies, fixed server-side ordering,
parameterized filters/IDs, bounded page/page-size values, and generic error
messages with request IDs. No dynamic client-controlled ORDER BY was found in
the ATD-B routes. No ATD-B TODO/FIXME/NotImplemented, `shell=True`, hard-coded
runtime secret, or fabricated IP attribution was found. Existing unrelated
fixture/test literals were not treated as product secrets.

Static runtime evidence:

```text
uid=1000(b822726) ...
CapEff: 0000000000000000
```

The systemd units statically specify `User=secmon`, `NoNewPrivileges=true`,
`ProtectSystem=strict`, `ProtectHome=true`, explicit `ReadWritePaths`, and
`Restart=on-failure`; no new capabilities were added.

Security findings:

- Critical: none found in independently inspected ATD-B scope.
- High: none found in independently inspected ATD-B scope.
- Medium: none found in independently inspected ATD-B scope.
- Low: privileged runtime evidence is unavailable in this environment; this is
  a verification blocker, not a product-code finding.

## Runtime and nftables evidence

Identity and capability checks passed as static/non-root evidence. The required
privileged checks were attempted without generating company-network traffic:

```text
nft --version
# nftables v1.1.6 (...)
nft list ruleset
# Operation not permitted (you must be root)
# netlink: Error: cache initialization failed: Operation not permitted
nft add table inet secmon
# Error: Could not process rule: Operation not permitted
nft delete table inet secmon
# Operation not permitted (you must be root)
# netlink: Error: cache initialization failed: Operation not permitted
nft list table inet secmon
# Operation not permitted (you must be root)
```

No test nftables table/rules were created, and no residual test rules were
observed. The isolated HTTP/restart command was also attempted:

```text
PYTHONPATH=. python scripts/p4_backend_restart_runtime.py
```

It exited with code 1 at the rollback assertion before the restart phase. The
environment's nftables permission restriction prevented the required isolated
firewall precondition, so HTTP restart before/after collector/detector,
rollback-after-restart, and post-rollback service state are `NOT_RUN` /
`BLOCKED`, not PASS.

No scan, flood, attack, or other traffic was generated against a company
network; all functional traffic probes were local TestClient/synthetic data.

## Known limitations and rollback

- Privileged nftables rule lifecycle and real HTTP service restart remain
  BLOCKED until a rootful isolated namespace/runner is available.
- The ATD-B state baseline is intentionally in memory; a process restart
  rebuilds it through warm-up rather than restoring an untrusted baseline.
- Interface counters cannot provide IP, port, or protocol attribution.
- Rollback is the normal feature-branch rollback to the pre-ATD-B baseline
  `70ef2db45a8f325d2b737fe2f1707a582bde825a`; do not use a destructive reset
  in a dirty worktree. The independent verification document is the only new
  file created by this audit.

## Final markers

BRANCH: feature/secmon-atd-b-detection
VERIFIED_HEAD: 0b1e0c30d5e881cbb04cfb3324d8a6fe41f6a9bd
WORKTREE_STATUS: clean before verification document; document is an audit artifact
NFTABLES_RESULTS: BLOCKED — operation requires root; no residual rules
ATD_B_RELEASE_GATE: INCONCLUSIVE
ATD_B_FORMAL_ACCEPTANCE: PENDING_INDEPENDENT_VERIFICATION
FINAL_DECISION: INCONCLUSIVE

## Privileged isolation Runtime Gate addendum

Execution host and environment:

```text
hostname: b822726-NB-TUFA16
uid=1000(b822726) gid=1000(b822726)
branch: feature/secmon-atd-b-detection
implementation HEAD: 0b1e0c30d5e881cbb04cfb3324d8a6fe41f6a9bd
```

The required baseline commands were run before this gate. The worktree had
only the previously created, uncommitted independent-verification document;
no product-code change was present. `sudo -n true` returned exit 1 with
`sudo: a password is required`.

The requested nftables backup was attempted exactly as follows:

```text
sudo -n nft list ruleset > /tmp/secmon-atd-b-nft-before.txt
exit=1
sudo: a password is required
```

An isolated, trap-protected direct lifecycle attempt used only the dedicated
name `inet secmon_atd_b_test` and did not flush or alter any existing table:

```text
nft add table inet secmon_atd_b_test                         exit=1
Error: Could not process rule: Operation not permitted
nft add chain inet secmon_atd_b_test input ...               exit=1
Operation not permitted (you must be root)
nft add rule inet secmon_atd_b_test input counter ...        exit=1
Operation not permitted (you must be root)
nft list table inet secmon_atd_b_test                        exit=1
Operation not permitted (you must be root)
trap cleanup: nft delete table inet secmon_atd_b_test       exit=1
Operation not permitted (you must be root)
```

The required final commands were also attempted. `sudo -n nft list tables`,
the after-ruleset backup, and `sudo -n nft list table inet secmon_atd_b_test`
all returned exit 1 with `sudo: a password is required`. The resulting
before/after files were both empty because the privileged backups did not
run; `diff -u` therefore had no meaningful firewall evidence and is recorded
as `BLOCKED`, not PASS. No test table or rule was successfully created, and
the trap left no test object created by this attempt.

The existing project runtime helper was run with temporary environment-only
credentials (not recorded):

```text
SECMON_P4_RUNTIME_SECRET=<temporary> \
SECMON_P4_RUNTIME_PASSWORD=<temporary> \
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=. \
python scripts/p4_backend_restart_runtime.py
exit=1
AssertionError at scripts/p4_backend_restart_runtime.py:181:
assert status == 500 and payload["error"]["code"] == "DATABASE_ERROR"
```

The helper did not complete its restart phase, collector/detector post-restart
sampling, baseline rebuild, synthetic anomaly/recovery, or rollback assertions.
Those items are `NOT_RUN`/`BLOCKED`; no PASS is inferred from the service that
was already running. The observed system service remained active, but this is
not restart evidence. The configured production unit is
`secmon-collector.service`, with `User=secmon`, `NoNewPrivileges=true`, and
`Restart=on-failure`; no `secmon-api.service` unit exists on this host. The
running collector PID was 1922369 with `Uid: 958` and
`CapEff: 0000000000000000`. A local development uvicorn process was owned by
uid 1000; no root application process was started.

No company-network scan, flood, stress, attack, or other real traffic was
generated. All functional probes used local TestClient, synthetic counters,
or fixtures.

For this gate:

```text
ATD_B_PRIVILEGED_RUNTIME_STATUS: BLOCKED
ATD_B_RELEASE_GATE: INCONCLUSIVE
ATD_B_FORMAL_ACCEPTANCE: PENDING_PRIVILEGED_RUNTIME_VERIFICATION
```

## Operator-executed evidence review — 2026-07-21

The operator reported that API deployment and the privileged Runtime Gate were
executed outside the Codex sandbox. The required exported evidence was not
available for review:

```text
/tmp/secmon-atd-b-preflight.log: MISSING
/tmp/secmon-atd-b-runtime-gate.log: MISSING
/tmp/secmon-atd-b-cleanup.log: MISSING
```

The available files do not establish a successful privileged run. In
particular, the nftables artifacts contain these failures:

```text
/tmp/secmon-atd-b-nft-before.err: sudo: a password is required
/tmp/secmon-atd-b-nft-after.err: sudo: a password is required
/tmp/secmon-atd-b-nft-create.err: Operation not permitted
/tmp/secmon-atd-b-nft-chain.err: Operation not permitted (you must be root)
/tmp/secmon-atd-b-nft-rule.err: Operation not permitted (you must be root)
/tmp/secmon-atd-b-nft-list.err: Operation not permitted (you must be root)
/tmp/secmon-atd-b-nft-delete.err: Operation not permitted (you must be root)
```

The before and after ruleset files are empty because the privileged backups
failed; their empty-file comparison is not valid ruleset-diff evidence. The
current unprivileged table read also returned `Operation not permitted`, so
absence of a residual table is not independently verified in this session.

The available HTTP runtime artifact,
`/tmp/secmon-atd-b-http-runtime.out`, ends with an assertion failure at
`p4_backend_restart_runtime.py:181`. It contains no successful restart,
rollback, collector/detector restart, baseline rebuild, synthetic anomaly,
recovery, or unresolved-event consistency evidence. These items remain
`NOT_RUN`/`INCONCLUSIVE`; the current service state is not a substitute for
restart history.

Current read-only service snapshot:

```text
secmon-api.service: active/running, MainPID=2755284, User=secmon, Group=secmon
secmon-collector.service: active/running, MainPID=1922369, User=secmon, Group=secmon
API CapEff: 0000000000000000, NoNewPrivs: 1
collector CapEff: 0000000000000000, NoNewPrivs: 1
/healthz: HTTP 200
/readyz: HTTP 200
```

This proves the present process identity and health state only. It does not
prove the required before/after restart or rollback transitions.

The first literal `make check` in this environment failed because the shell
PATH selected a non-executable `ruff` (`ruff: Permission denied`). Re-running
the same quality gate with the repository virtual environment first in PATH
completed successfully:

```text
PATH="$PWD/.venv/bin:$PATH" make check
ruff: PASS
mypy: PASS; 22 source files
pytest: PASS; 173 passed in 4.19s
frontend build: PASS
git diff --check: PASS
```

The current branch is `feature/secmon-atd-b-detection` at
`20da00a79c1b95c774d59c815aa0e8f9893f3d65`. The worktree contains only the
ATD-B/API verification-related changes listed by `git status --short`; no
implementation, migration, or test files were changed by this evidence
review. No commit was created.

Final determination after this review:

```text
SUDO_STATUS: BLOCKED — required privileged logs unavailable; available sudo/nft evidence failed
NFTABLES_CREATE: FAIL/INCONCLUSIVE — Operation not permitted
NFTABLES_LIST: FAIL/INCONCLUSIVE — Operation not permitted
NFTABLES_DELETE: FAIL/INCONCLUSIVE — Operation not permitted
NFTABLES_CLEANUP: INCONCLUSIVE — no privileged cleanup log
RULESET_DIFF: INCONCLUSIVE — before/after backups empty after sudo failure
HTTP_BEFORE: INCONCLUSIVE — no Runtime Gate log
HTTP_RESTART: INCONCLUSIVE — no successful restart evidence
HTTP_AFTER: INCONCLUSIVE — current health only
ROLLBACK: INCONCLUSIVE — assertion-failing artifact, no rollback evidence
COLLECTOR_AFTER_RESTART: INCONCLUSIVE
DETECTOR_AFTER_RESTART: INCONCLUSIVE
BASELINE_REBUILD: INCONCLUSIVE
UNRESOLVED_EVENT_CONSISTENCY: INCONCLUSIVE
APPLICATION_USER: PASS snapshot — secmon (UID 958)
CAP_EFF: PASS snapshot — 0000000000000000 for API and collector
FINAL_MAKE_CHECK: PASS — 173 tests and frontend build

ATD_B_PRIVILEGED_RUNTIME_STATUS: BLOCKED
ATD_B_RELEASE_GATE: INCONCLUSIVE
ATD_B_FORMAL_ACCEPTANCE: PENDING_PRIVILEGED_RUNTIME_VERIFICATION
FINAL_DECISION: INCONCLUSIVE
```

## Final evidence consolidation — 2026-07-21

This section supersedes the preceding provisional runtime determination. It
separates independently traceable detector tests from the operator-executed
privileged infrastructure gate. It does not treat absent detector output in
the Runtime Gate log as detector-runtime evidence.

### Detector functional evidence

The command below is recorded by `/tmp/secmon-atd-b-make-check.log` with exit
code 0 and `173 passed in 4.18s`:

```text
PATH="$PWD/.venv/bin:$PATH" make check
```

The following assertions in `tests/test_atd_b.py` are the traceable ATD-B
functional evidence included in that full suite:

| Requirement | Evidence | Result |
|---|---|---|
| Rate calculation and invalid/non-positive elapsed time | `test_rate_calculation_bytes_bits_packets_and_zero_time` | PASS |
| Counter reset, NaN, and negative-counter handling | `test_counter_reset_and_invalid_values_are_not_negative_rates` | PASS |
| Warm-up, rolling baseline configuration, sustained anomaly, state machine, recovery, and cooldown | `test_warmup_sustained_alert_recovery_and_cooldown` asserts `NORMAL -> WATCH -> ALERT -> RECOVERING -> RESOLVED` | PASS |
| Per-interface isolation and restart baseline rebuild | `test_interfaces_are_isolated_and_restart_rebuilds_baseline` asserts a fresh detector remains `NORMAL` during rebuild | PASS |
| Event persistence and unknown interface-counter attribution | `test_persistence_keeps_ip_attribution_unknown_and_deduplicates` executes `persist_detection` against a migrated SQLite database and asserts nullable IP/port/protocol attribution | PASS for persistence/attribution |
| Duplicate suppression | The above test name and the implementation's unique `traffic_alerts.event_key` identify the intended mechanism, but this test does not assert a second persistence operation or count update | NOT_CONFIRMED |
| Unresolved-event consistency | No existing test assertion or readable detector Runtime Gate output establishes the final unresolved-row count | NOT_CONFIRMED |
| SQLite transaction rollback | No existing ATD-B test assertion or readable detector Runtime Gate output establishes the synthetic rollback probe | NOT_CONFIRMED |

The historical implementation report
`SECMON_ATD_B_DETECTION_IMPLEMENTATION_AND_VERIFICATION_2026-07-20.md` is
supporting context only; its summary claims are not used as a substitute for
the named test assertions above.

### Privileged infrastructure runtime evidence

The operator-executed root-owned gate produced the following retained command
artifacts. No scan, flood, packet injection, or real attack traffic was
generated; its nftables probe was the fixed unhooked table
`inet secmon_atd_b_test`.

| Requirement | Artifact and exact result | Result |
|---|---|---|
| Preflight | `/tmp/secmon-atd-b-preflight.log`: `PREFLIGHT=PASS` | PASS |
| Runtime / cleanup exits | `/tmp/secmon-atd-b-final-report.txt`: `PREFLIGHT_EXIT_CODE: 0`, `RUNTIME_EXIT_CODE: 0`, `CLEANUP_EXIT_CODE: 0` | PASS |
| Isolated table create and readback | `/tmp/secmon-atd-b-runtime-summary.txt`: `NFTABLES_CREATE=PASS`, `NFTABLES_LIST=PASS` | PASS |
| Delete, cleanup, and absence | Runtime summary: `NFTABLES_DELETE=PASS`, `NFTABLES_CLEANUP=PASS`; final report: `NFTABLES_TEST_TABLE_ABSENT: PASS`, `TEST_TABLE_LIST_EXIT_CODE: 1` | PASS |
| Ruleset comparison | Runtime summary: `RULESET_RAW_DIFF=PRESENT`, `RULESET_NORMALIZED_DIFF=PASS`, `RULESET_DIFF=PASS`. The gate retains raw before/after and raw diff, and normalizes only `counter packets <number> bytes <number>` before the second comparison. | PASS |
| HTTP before/restart/after | Runtime summary: `HTTP_BEFORE=PASS`, `HTTP_RESTART_COMMAND=PASS`, `READINESS_POLLING=PASS`, `READINESS_ATTEMPTS=2`, `HTTP_HEALTH_AFTER=PASS`, `HTTP_READY_AFTER=PASS` | PASS |
| Collector restart | Runtime summary: `COLLECTOR_AFTER_RESTART=PASS` | PASS |
| API and collector least privilege | Final report records both units as `secmon` (UID 958), `CapEff: 0000000000000000`, and `NoNewPrivs: 1` | PASS |

The Runtime Gate log does **not** contain synthetic detector, baseline rebuild,
recovery, rollback, or unresolved-event markers. These items therefore remain
detector-functional evidence only where the named tests establish them; they
are not claimed as privileged Runtime Gate PASS results.

### Quality gate evidence

`/tmp/secmon-atd-b-make-check.log` records the full command above with:

```text
ruff check backend database tests        All checks passed!
mypy backend database                   Success: no issues found in 22 source files
pytest                                  173 passed in 4.18s
npm --prefix frontend run build         PASS
```

`/tmp/secmon-atd-b-final-report.txt` also records
`FINAL_MAKE_CHECK_EXIT_CODE: 0` and `GIT_DIFF_CHECK_EXIT_CODE: 0`.

### Security evidence

The committed source configuration and runtime artifacts establish the
following:

- `systemd/secmon-api.service` fixes `User=secmon`, `Group=secmon`,
  loopback-only `127.0.0.1:8080`, `NoNewPrivileges=true`, and no added
  capabilities.
- `scripts/secmon-atd-b-privileged-runtime.sh` fixes the API and collector
  units, health endpoints, and the only nftables target
  `inet secmon_atd_b_test`; it has no caller-supplied table, service, endpoint,
  command, or shell fragment.
- `scripts/deploy-secmon-api-runtime.sh` uses the declared application
  artifact and production dependency declaration, does not embed credentials,
  and does not start or restart a service.
- `docs/SECMON_API_SYSTEMD_DEPLOYMENT_2026-07-20.md` records the operator-only
  installation, health, identity, capability, and rollback procedure.

### Formal determination

The privileged infrastructure runtime is complete. However,
`UNRESOLVED_EVENT_CONSISTENCY` and `ROLLBACK` lack a traceable existing test
assertion or readable detector evidence artifact. They are deliberately not
promoted from implementation intent or a missing Runtime Gate log.

```text
ATD_B_DETECTOR_FUNCTIONAL_EVIDENCE: PARTIAL — rate/reset/warm-up/baseline/anomaly/state/recovery/restart/persistence PASS; duplicate suppression, unresolved-event consistency, and rollback NOT_CONFIRMED
ATD_B_PRIVILEGED_INFRASTRUCTURE_RUNTIME: PASS
ATD_B_QUALITY_GATE: PASS
ATD_B_SECURITY_VALIDATION: PASS
UNRESOLVED_EVENT_CONSISTENCY: NOT_CONFIRMED
ROLLBACK_EVIDENCE: NOT_CONFIRMED
ATD_B_RELEASE_GATE: INCONCLUSIVE
ATD_B_FORMAL_ACCEPTANCE: PENDING_TRACEABLE_UNRESOLVED_AND_ROLLBACK_EVIDENCE
FINAL_DECISION: INCONCLUSIVE
```
