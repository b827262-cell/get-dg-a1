# P4-16 Agent 3 Final Staging Reverification

- TESTED_HEAD: `ca76564a43ed7d0aede2b95f7e1b4dc004a2e014` plus main takeover changes.
- MODEL: `gpt-5.6-luna`, reasoning effort `xhigh`
- AGENT_STATUS: TIMEOUT (exit 124); main Codex reran and completed the isolated gate.
- ISOLATION_METHOD: fresh `unshare -Urn`; Host namespace reads were denied and no Host nft mutation was attempted.
- DB_TRIGGER_RESULT: PASS — SQLite `BEFORE INSERT` trigger aborted the real HTTP request after nft block.
- HTTP_RESULT: PASS — HTTP returned sanitized `500 DATABASE_ERROR`, never success.
- KERNEL_ROLLBACK_RESULT: PASS — inverse unblock left no rollback test element.
- DATABASE_RESULT: PASS — no active `blocked_ips` row after trigger failure.
- AUDIT_RESULT: PASS — sanitized rollback audit exists and contains no trigger secret.
- PID_1: `2130184`
- PID_2: `2130261`
- RESTART_RESULT: PASS — same DB, secret, network namespace and nft state; startup reconciliation and post-restart HTTP block/unblock passed.
- IPV4_RESULT: PASS — prior real driver packet drop/restore and restart IPv4 enforcement.
- IPV6_RESULT: PASS — prior real driver packet drop/restore and restart IPv6 enforcement.
- HOST_ISOLATION: PASS — distinct ephemeral network namespace, no Host nft write, and namespace destroyed at exit.
- CLEANUP: PASS — runtime deletes only `inet secmon` in its ephemeral namespace; process temporary DB/log files are removed.
- FINAL_RECOMMENDATION: PASS.
