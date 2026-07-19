# P4 Agent 1 Codex Exec Task

Implement GitHub Issue #1 in this checked-out `secmon-linux-security` project.

Deliver a secure nftables service abstraction and backend status, preview,
block and unblock APIs. Validate IPv4/IPv6 with a standard IP parser. Never
use `os.system`, `shell=True`, a shell command string, or unvalidated input in
argv/rules. Use fixed argv, timeout handling and non-zero-exit handling. Make
block/unblock idempotent, project-table isolated, rollback-capable and safe
for failure paths.

Enforce Admin/Analyst/Viewer backend RBAC (including direct API calls and
IDOR), implement audit schema/migration/API with redaction for credentials,
and provide management UI. Add backend, frontend, migration and security tests.
Run and repair relevant tests. Do not push, merge or create a PR.

Write `docs/P4_01_CODEX_NFTABLES_RBAC_AUDIT_IMPLEMENTATION.md` with files,
commands and outcomes.
