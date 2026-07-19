# P4-09 Main Codex Final Kernel Runtime Audit

- EXECUTION_DATE: 2026-07-19 Asia/Taipei
- HOST_KERNEL: isolated Linux kernel namespace via `unshare -Urn`
- ISOLATION_METHOD: user/network namespace; no Host nft write
- TESTED_HEAD: 7f300dea554efcc04ec64fa378947dcf1c87af62 plus runtime-gate fixes in this change
- HOST_NETNS_ID: host access retained outside unshare
- FIREWALL_NETNS_ID: newly created unshare network namespace
- CLIENT_NETNS_ID: not separately available; dummy-interface source alias used in same isolated namespace
- NFTABLES_VERSION: nftables v1.1.6
- IPV4_BLOCK_RESULT: PASS
- IPV4_PACKET_DROP_RESULT: PASS (100% loss)
- IPV4_UNBLOCK_RESULT: PASS
- IPV6_BLOCK_RESULT: PASS
- IPV6_PACKET_DROP_RESULT: PASS (100% loss)
- IPV6_UNBLOCK_RESULT: PASS
- RBAC_RESULTS: PASS (pytest API suite)
- AUDIT_RESULTS: PASS (pytest API suite)
- ROLLBACK_RESULTS: adapter inverse operation PASS; database-trigger-to-kernel integration EXTERNAL_BLOCKER
- RESTART_OLD_PID: not applicable
- RESTART_NEW_PID: not applicable
- RESTART_RESULTS: new service adapter reconstruction PASS; backend-process restart EXTERNAL_BLOCKER
- HOST_RULESET_BEFORE_HASH: unavailable: host nft read denied
- HOST_RULESET_AFTER_HASH: unavailable: host nft read denied
- HOST_ISOLATION_RESULT: PASS: unshare namespace destroyed after test; Host received no writes
- CLEANUP_RESULT: PASS
- TEST_RESULTS: compileall, ruff, mypy, 131 pytest, make check, frontend lint/typecheck/test/build PASS
- GITHUB_CI_RESULT: pending rerun for this commit
- FINAL_RESULT: P4_RELEASE_GATE_NOT_PASSED

