# P4 Agent 3 Final Staging Runtime Task

Perform verification only; do not push, merge, or create a PR. Use only an authorized unshare user/network namespace, named `ip netns`, test VM, or isolated NET_ADMIN container. Never touch Host nftables, host networking, privileged containers, or `nft flush ruleset`.

Verify a real backend HTTP process with temporary SQLite DB, secret, and test account. Install a SQLite trigger that makes `blocked_ips` INSERT fail after the admin HTTP block path has performed an nft block; prove inverse unblock, no kernel orphan, no active DB row, HTTP failure, and safe rollback audit. Then block real IPv4 and IPv6, prove packet drop, record PID 1, truly stop it, restart with same DB/secret/namespace/nft state as PID 2, prove health/login/RBAC/audit and retained kernel drop, then unblock both and prove restoration. Prove Host isolation and cleanup. If privilege is unavailable, record raw errors and do not claim PASS.

Write `docs/P4_16_AGENT3_FINAL_STAGING_REVERIFICATION.md` with TESTED_HEAD, MODEL, ISOLATION_METHOD, DB_TRIGGER_RESULT, HTTP_RESULT, KERNEL_ROLLBACK_RESULT, DATABASE_RESULT, AUDIT_RESULT, PID_1, PID_2, RESTART_RESULT, IPV4_RESULT, IPV6_RESULT, HOST_ISOLATION, CLEANUP, and FINAL_RECOMMENDATION.
