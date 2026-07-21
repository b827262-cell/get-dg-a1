# SecMon ATD-A Independent Verification — 2026-07-20

## Independence and scope

This review was performed by Codex (GPT-5) as an independent review role.  The
previous GLM-5.2 executor implemented ATD-A and performed part of its own
verification, so its PASS statements were treated only as leads and not as
evidence.  No ATD-A production code was changed by this review.

- Repository root: `/home/b822726/project/get-dg-project/secmon-linux-security`
- Project directory: `secmon-linux-security`
- Branch: `feature/secmon-atd-a-observability`
- Start: `953ec0944266a69a0eab7db10820f475410ca50a`
- Tested HEAD: `a622b1e4a7d54b4a1e7344f9a3eb760b650120df` (`a622b1e`)
- Range: five commits (`7dc6dd3`, `e4c6b41`, `efa18f2`, `af8ef35`, `a622b1e`)
- Initial worktree: clean; `git diff --check` produced no findings.

## Commit and security scope

Independent diff/stat and commit-stat review found ATD schema/migration,
zero-privilege collector, read-only API, narrowly related tests, configuration,
and ATD documentation.  `tests/test_api_auth.py` contains only removal of one
blank line.  There are no added systemd units, sudoers files, firewall/routing
or interface-management files, nor a security-control removal or test bypass.

`network_metrics.py` only reads `/proc/net/{dev,sockstat,sockstat6}` and
`/sys/class/net/*`; it uses no subprocess or `shell=True`, opens no network
socket, and contains a bounded SQLite open retry (3 attempts).  The `socket`
module is used solely for `gethostname()`.  It performs SQLite persistence but
does not invoke nftables, route, or interface mutation.  `main.py` only creates
the collector when `network_metrics_enabled` is true and catches collector
errors inside the existing loop.

The prescribed Git scan found no tracked database, pcap, `.env`, credentials,
or private-key files.  `data/` is ignored (`!! secmon-linux-security/data/`).
The range keyword scan found bearer/token wording in design text and the test
JWT secret/password in test code; these are explicit test fixtures, not real
credentials.  No real token, API key, private key, or real corporate CIDR was
identified.

## Migration and SQLite

`python -m pytest -q tests/test_migrate.py`: **PASS, 3 passed**.

On a new `/tmp` SQLite database, running the migration runner twice succeeded.
The resulting checks were `PRAGMA quick_check = [('ok',)]` and
`PRAGMA foreign_key_check = []`.  `network_samples` has
`idx_network_samples_time` and `idx_network_samples_iface_time`; its FK is
`interface_id -> network_interfaces(id)` with `ON DELETE CASCADE`.  Both
tables contain their expected columns and `network_samples` has no
`retention_until`.  The schema stores the raw cumulative counter fields.

## Counter/rate and API source review

`_derive_rates` returns null values for a first sample, invalid/zero elapsed
time, missing counter, and counter decrease; therefore it does not emit a
negative BPS/PPS value.  It computes elapsed time from adjacent timestamps,
not an assumed five-second interval.  TCP/UDP `inuse` values are stored as
gauges and not differenced.

The four endpoints are GET-only and use the existing `require_read` dependency,
whose accepted roles are `viewer`, `analyst`, and `admin` (there is no
`operator` role).  Pagination uses the existing `{items,page,page_size,total}`
shape; invalid range handling uses the existing structured error handler, and
the maximum range is 31 days.  Overview explicitly says
`endpoint_view_only` and does not claim corporate-wide visibility.  Top Talkers
returns `scope: "interface"` and contains no source/destination-IP or per-IP
flow claim.

## Quality gate and API/RBAC execution

- The earlier timeout was caused by the restricted verification sandbox's
  network namespace.  It was independently rerun after full access was
  available.
- `make check`: **PASS (exit 0)** — Ruff PASS, mypy PASS (`21 source files`),
  backend pytest **163 passed in 3.93s**, and frontend build PASS.
- `python -m pytest -q tests/test_atd_api.py tests/test_atd_collector.py
  tests/test_migrate.py`: **PASS, 25 passed**.  This executes the unauthenticated
  and viewer/analyst/admin network-endpoint RBAC cases, rate/reset cases,
  collector cases, and migration cases.
- `python -m pytest -q tests/test_migrate.py tests/test_atd_collector.py`:
  **PASS, 14 passed**.
- `python -m compileall backend`: **PASS (exit 0)**.
- Frontend `npm --prefix frontend test`: **PASS, 1 passed**; frontend
  `typecheck` and `build`: **PASS (exit 0)**.  These were run separately
  because `make check` stops at its backend pytest prerequisite.

The API/RBAC evidence is therefore executable as well as source-reviewed.

## Non-root runtime smoke and restart

The verifier ran as `uid=1000(b822726)`, with
`CapPrm=0x0`, `CapEff=0x0`, and `CapBnd=0x0`.  With a fresh `/tmp` DB and the
feature enabled, the real collector wrote three consecutive rounds:
`(3,4)`, `(3,4)`, `(3,4)`; the third was from a newly constructed collector
instance, confirming restart continuity.  No systemd unit was started and no
attack traffic or network-system mutation was performed.

After full access was enabled, `/proc/net/dev` exposed `eno1`, `wlan0`, and
`tailscale0`.  All three interfaces had three real non-loopback samples and
their RX/TX counters were monotonic or steady.  In particular, `wlan0` and
`tailscale0` increased naturally between samples; no test traffic was sent.

## Rollback

With `SECMON_NETWORK_METRICS_ENABLED=false`, the settings probe resolves false
and `main.py` leaves `network_collector` unset, so the existing loop does not
call network sampling.  It does not drop tables or issue firewall, route, or
interface operations, and no reboot is required.  Existing stored data is not
deleted by this path.  Boundary: this flag gates main-loop initialization and
does **not** make a direct, manual `NetworkMetricsCollector.collect_once()`
call read-only; that is documented behavior, not a defect.  API continuity is
covered by the subsequently passing complete backend test suite.

## Findings and recommendation

- Critical: 0
- High: 0
- Medium: 0
- Low: 1 — interface names can be reused with a new ifindex.  The model
  correctly preserves history; ATD-D should display name, ifindex, interface
  ID, and last-seen time.  Owner: ATD-D.

No host reboot was performed: `ATD_A_HOST_REBOOT_TEST: NOT_RUN`.

All required independent checks now pass.  Formal acceptance is recommended;
the unrun host reboot remains an explicit non-blocking limitation.

```
ATD_A_IMPLEMENTATION_STATUS: IMPLEMENTED_UNCHANGED_BY_REVIEW
ATD_A_INDEPENDENT_VERIFICATION_STATUS: PASS
ATD_A_MIGRATION_STATUS: PASS
ATD_A_COLLECTOR_STATUS: PASS
ATD_A_PRIVILEGE_STATUS: PASS
ATD_A_API_RBAC_STATUS: PASS
ATD_A_COUNTER_RESET_STATUS: PASS_SOURCE_AND_COLLECTOR_TESTS
ATD_A_TOP_TALKERS_SCOPE_STATUS: PASS
ATD_A_QUALITY_GATE_STATUS: PASS
ATD_A_RUNTIME_STATUS: PASS
ATD_A_ROLLBACK_STATUS: PASS
ATD_A_HOST_REBOOT_TEST: NOT_RUN
ATD_A_SECURITY_REVIEW_STATUS: PASS_NO_CRITICAL_OR_HIGH
ATD_A_RELEASE_GATE: PASS
ATD_A_FORMAL_ACCEPTANCE_RECOMMENDATION: PASS

SECMON_ATD_OVERALL_RELEASE_GATE: FAIL
SECMON_ATD_OVERALL_FORMAL_ACCEPTANCE: PENDING
```
