+# P4 Agent 1 — Real Kernel Runtime Implementation

Read GitHub Issue #1, PR #3, and the existing P4 implementation. Work only inside this clean P4 worktree. Do not push, merge, or create a PR.

Inspect backend/services/nftables.py, firewall API, audit, migration, and tests. Create a repeatable, host-safe isolated runtime script. Prefer `ip netns`; if unavailable, use rootful Docker/Podman with NET_ADMIN only. Never use `--network host`, `--privileged`, `shell=True`, `os.system`, or `nft flush ruleset`.

Verify or repair real isolated-kernel support for fixed `inet secmon`, `blocked_ipv4`, `blocked_ipv6`, and input-chain IPv4/IPv6 drops. Cover preview in a fresh namespace, IPv4/IPv6 block/unblock, rollback, restart, and host isolation. Add focused tests and run relevant tests. Do not modify host firewall rules.

Write docs/P4_06_AGENT1_REAL_KERNEL_IMPLEMENTATION.md with: AGENT_STATUS, ACTIVE_MODEL, START_HEAD, END_HEAD, FILES_CHANGED, RUNTIME_SCRIPT, NFTABLES_FIXES, PREVIEW_FIXES, ROLLBACK_FIXES, RESTART_FIXES, TESTS_ADDED, TEST_RESULTS, KNOWN_GAPS, HANDOFF_TO_MAIN_CODEX.
