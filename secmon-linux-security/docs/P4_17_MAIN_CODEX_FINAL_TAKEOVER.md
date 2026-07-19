# P4-17 Main Codex Final Takeover

- Agent 1: `FIXED_BY_MAIN_CODEX` — exit 124; retained validated rollback/restart implementation and completed reports.
- Agent 2: `FIXED_BY_MAIN_CODEX` — exit 124; completed equivalent security review, removed divergent compatibility mutations, expanded audit redaction.
- Agent 3: `FIXED_BY_MAIN_CODEX` — exit 124; reproduced its normal-SIGTERM harness failure, corrected it, and reran isolated real HTTP/kernel runtime successfully.
- DB trigger rollback: `VERIFIED` — real HTTP request, real SQLite trigger, inverse nft unblock, no active row, sanitized 500 and audit.
- Backend restart: `VERIFIED` — old PID `2130184`, new PID `2130261`, same DB/secret/network namespace/nft state.
- IPv4/IPv6: `VERIFIED` — isolated real-kernel driver packet drop/restore and post-restart kernel state.
- Host isolation/cleanup: `VERIFIED` — fresh `unshare -Urn`, no Host nft writes, ephemeral namespace destroyed.
- Static/frontend regression: `VERIFIED` — 133 pytest, ruff, mypy, compileall, make check, npm lint/typecheck/test/build passed.
- GitHub CI: `PENDING` at document creation; release decision is finalized only after PR checks pass.
