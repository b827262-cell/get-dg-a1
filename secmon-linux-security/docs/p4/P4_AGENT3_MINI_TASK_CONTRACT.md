# P4 Agent 3 Contract — GPT-5.4 mini

- P4 Start HEAD: `df9995329d987b646c1ab89cca65096dfc762de4`
- Worktree: `/home/b822726/project/secmon-linux-security-p4/secmon-linux-security`
- Initial ownership: independent threat model, security review, test plan, and evidence reports; do not edit production implementation owned by Agents 1/2.

Independently inspect authentication, RBAC, IDOR, privilege escalation, CSRF, XSS, SQL/log injection, SSRF, rate limiting, sensitive-data exposure, whitelist protection, audit integrity, migrations, and release/runtime/rollback evidence. Start with a baseline threat model and test plan while implementation is in progress; after handoff, execute the requested independent checks and record evidence. Deliver `P4_AGENT3_MINI_SECURITY_RUNTIME_REVIEW.md`, `P4_THREAT_MODEL.md`, and `P4_RUNTIME_SMOKE_RESULTS.md` under `docs/p4`. Every result must be PASS, FAIL, BLOCKED, or NOT TESTED and each PASS needs command, exit code, key output, environment, and file/API. Do not claim overall release acceptance.
