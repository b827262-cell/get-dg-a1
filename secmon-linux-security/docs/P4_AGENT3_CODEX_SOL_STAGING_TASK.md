# P4 Agent 3 — Codex Sol Staging Runtime Reverification

Perform the final staging runtime verification only. Do not modify production
application code, merge, push, or create a PR. You may use the repository's
isolated runtime scripts and create only `docs/P4_12_CODEX_SOL_STAGING_REVERIFICATION.md`.

Never modify the Host nftables ruleset. Use a network namespace, a test VM, or
an isolated NET_ADMIN container. Never use host networking, privileged
containers, or `nft flush ruleset`.

Require and record evidence for: real backend HTTP API; a real SQLite trigger
that makes blocked-IP INSERT fail after nft block; inverse kernel unblock; no
orphan kernel element/no active DB row/no false success; rollback audit;
IPv4/IPv6 block; genuine backend process stop/restart using same DB, secret,
and namespace with different PIDs; post-restart health/login/RBAC/audit and
retained kernel blocks; subsequent unblock and packet restore; unchanged Host
ruleset; and cleanup.

Do not infer a pass from mocks or service-adapter reconstruction. If the
environment prevents a scenario, preserve the raw error and mark it failed or
external blocker, never PASS.

Report AGENT_STATUS, ACTIVE_MODEL, TESTED_HEAD, ISOLATION_METHOD,
HOST_NETNS, FIREWALL_NETNS, CLIENT_NETNS, NFTABLES_VERSION, IPV4_RESULTS,
IPV6_RESULTS, RBAC_RESULTS, AUDIT_RESULTS, ROLLBACK_RESULTS,
RESTART_RESULTS, HOST_ISOLATION_RESULTS, CLEANUP_RESULTS, FAILED_SCENARIOS,
REQUIRED_FIXES, and FINAL_RECOMMENDATION in
`docs/P4_12_CODEX_SOL_STAGING_REVERIFICATION.md`.
