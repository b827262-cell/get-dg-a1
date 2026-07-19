# P4 Agent 2 — Codex Sol Security Review

Review the current P4 implementation for nftables, RBAC, audit, and isolated
runtime safety.  This is a review-only task: do not modify application code,
tests, scripts, git state, or GitHub state.  You may create only the requested
report.

Inspect the current branch, Issue #1 / PR #3 evidence available locally, and
the relevant backend, frontend, migration, tests, and runtime scripts.

Check specifically:

- shell, argument, and nft rule injection;
- accidental Host ruleset impact and namespace isolation;
- fixed `inet secmon` table, chain and sets only;
- unsafe IPv4/IPv6 classes;
- RBAC bypass and IDOR;
- database/kernel divergence, rollback orphan rules, and restart reconciliation;
- audit sensitive-data redaction; and cleanup residue.

For each finding, provide severity, concrete evidence, exploitability, and a
required remediation. Do not mark missing evidence as a pass.

Write `docs/P4_11_CODEX_SOL_SECURITY_REVIEW.md` with: AGENT_STATUS,
ACTIVE_MODEL, REVIEW_HEAD, CRITICAL_FINDINGS, HIGH_FINDINGS,
MEDIUM_FINDINGS, HOST_SAFETY_FINDINGS, NAMESPACE_FINDINGS,
NFTABLES_FINDINGS, ROLLBACK_FINDINGS, RESTART_FINDINGS, AUDIT_FINDINGS,
REQUIRED_FIXES, and FINAL_RECOMMENDATION.
