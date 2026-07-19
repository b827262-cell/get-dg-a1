# P4-06 Agent 1 real kernel implementation

## AGENT_STATUS

IMPLEMENTED; runtime execution is capability-blocked in this worktree's
container. The repeatable gate exits `77` without changing firewall state when
it cannot obtain an isolated kernel namespace. It must be run by main Codex in
a rootful namespace-capable environment before calling the kernel gate PASS.

## ACTIVE_MODEL

GPT-5 Codex

## START_HEAD

`7f300dea554efcc04ec64fa378947dcf1c87af62`

## END_HEAD

`7f300dea554efcc04ec64fa378947dcf1c87af62` (no commit was created, pushed,
merged, or submitted for review)

## FILES_CHANGED

- `backend/services/nftables.py`
- `tests/test_nftables.py`
- `scripts/p4_real_kernel_runtime.sh`
- `scripts/p4_real_kernel_runtime_driver.py`
- this report

Pre-existing untracked task/evidence documents were left untouched.

## RUNTIME_SCRIPT

Run `scripts/p4_real_kernel_runtime.sh` from the worktree. It first refuses if
`inet secmon` already exists on the host, then prefers a freshly-created
`ip netns`. The driver receives its nft binary path explicitly and exercises
only that namespace. The EXIT trap removes the namespace on failure.

If namespace creation is unavailable, it accepts an accessible rootful Docker
or Podman daemon and uses `--network none` plus only `--cap-add=NET_ADMIN`; it
never uses host networking or privileged mode. Set `P4_RUNTIME_IMAGE` to an
image containing `nft` and Python (the default is `debian:stable-slim`, which
must already satisfy those dependencies). The source worktree is read-only in
the container. A non-capable environment exits `77` as a skip.

The driver verifies fresh-namespace preview, IPv4 and IPv6 block/unblock,
transaction-style inverse-operation rollback, the exact table/set/input-chain
drop rules, and state reconstruction/idempotence through a new service
instance (restart simulation). It verifies the host still has no `inet secmon`
table after successful execution.

## NFTABLES_FIXES

`preview()` previously checked one element directly. That requires the table
and set to pre-exist, so preview failed in a fresh isolated kernel. It now
passes one complete, SecMon-only ruleset to `nft --check -f -`, including fixed
`inet secmon`, both typed sets, and both input-chain drop rules. No checked
rules are installed.

All mutation argv remains fixed except canonical `ipaddress` output. There is
no shell execution, `os.system`, `nft flush ruleset`, host networking, or
privileged container mode.

## PREVIEW_FIXES

Focused assertions confirm IPv4 and IPv6 previews use exactly
`nft --check -f -` and supply the full owned ruleset. The runtime driver calls
both previews before it creates any table or set.

## ROLLBACK_FIXES

The existing API inverse operations remain intact: failed block database work
attempts `unblock`, and failed unblock database work attempts `block`. The
kernel driver exercises the same adapter-level inverse sequence (block then
unblock) and asserts the element is absent. Existing API tests cover the
database-coordination paths with their controlled firewall double.

## RESTART_FIXES

No process-local ruleset state was added. The kernel gate creates a second
`NftablesService` after both elements are installed, verifies status from nft,
checks idempotent re-block, then unblocks both families.

## TESTS_ADDED

`tests/test_nftables.py` now asserts preview's fixed stdin argv and complete
IPv4/IPv6 ruleset content. The new namespace driver is an executable real
kernel test, not a host-firewall test.

## TEST_RESULTS

- `python -m compileall -q backend scripts/p4_real_kernel_runtime_driver.py` — PASS.
- `bash -n scripts/p4_real_kernel_runtime.sh` — PASS.
- `git diff --check` — PASS.
- Direct mocked preview gate for IPv4/IPv6, fixed argv, table, sets, and drop
  rules — PASS.
- `python -m pytest tests/test_nftables.py tests/test_api_auth.py tests/test_migrate.py` — NOT RUN: this worktree's Python has no `pytest` module.
- `scripts/p4_real_kernel_runtime.sh` — SKIP (77): `ip netns add` is denied and
  Docker's socket is inaccessible; no host nftables command that writes state
  was run.

## KNOWN_GAPS

This environment lacks CAP_NET_ADMIN and access to a rootful container daemon,
so it cannot provide a truthful real-kernel PASS. The GitHub Issue #1 and PR
#3 content could not be fetched directly because GitHub access is not installed;
the local PR branch/history and existing P4 evidence were inspected instead.
Container fallback also requires a prebuilt image with `nft` and Python.

## HANDOFF_TO_MAIN_CODEX

Run the focused pytest command in the project test environment, then run
`scripts/p4_real_kernel_runtime.sh` as an authorized rootful operator on a
non-production host. Treat exit `77` as an environmental skip, not a PASS.
Do not run it where a live host `inet secmon` table already exists; the script
will refuse before creating isolation. No host firewall rules were modified by
Agent 1.
