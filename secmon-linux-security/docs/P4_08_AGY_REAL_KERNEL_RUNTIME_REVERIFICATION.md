# P4-08 AGY Real Kernel Runtime Reverification

- AGENT_STATUS: NO_VALID_PROJECT_ARTIFACT; FIXED_BY_MAIN_CODEX
- ACTIVE_MODEL: AGY (its claimed report was written outside this repository)
- TESTED_HEAD: 7f300dea554efcc04ec64fa378947dcf1c87af62 plus uncommitted Agent 1/main fixes
- ISOLATION_METHOD: Main Codex used `unshare -Urn`; it created a fresh user and network namespace.
- HOST_NETNS: unchanged; host nft netlink access is denied to this process.
- FIREWALL_NETNS: fresh unshare network namespace.
- CLIENT_NETNS: packet source/destination aliases on a dummy interface in the same isolated namespace; this verifies the real input hook but is not a separate client namespace.
- NFTABLES_VERSION: nftables v1.1.6.
- IPV4_RESULTS: PASS: baseline ICMP, block, real 100% packet loss, unblock, restored ICMP.
- IPV6_RESULTS: PASS: baseline ICMPv6, block, real 100% packet loss, unblock, restored ICMPv6.
- RBAC_RESULTS: VERIFIED by 131 pytest API tests.
- AUDIT_RESULTS: VERIFIED by 131 pytest API tests.
- ROLLBACK_RESULTS: adapter inverse operation PASS; database-trigger-to-real-kernel integration not executed.
- RESTART_RESULTS: service-adapter state reconstruction and post-restart idempotence PASS; external backend process restart not executed.
- HOST_ISOLATION_RESULTS: PASS: all nft mutations ran in unshare netns; host `nft list ruleset` is permission-denied, never written.
- CLEANUP_RESULTS: PASS: unshare namespace terminated and removed all temporary table/interface state.
- FAILED_SCENARIOS: Agent-produced repository report missing; separate firewall/client netns, DB-trigger rollback, and real backend process restart were not executed.
- REQUIRED_FIXES: none to the host-safe implementation; an authorized staging namespace with two netns and backend service control is required for the remaining release evidence.
- FINAL_RECOMMENDATION: do not claim full release PASS.

