# P4 Deployment and Rollback

## Deployment safeguards

1. Take a verified database backup before applying migrations.
2. Apply migrations once, restart the application, then apply them again to prove idempotency.
3. Run `PRAGMA quick_check`, `integrity_check`, and `foreign_key_check` on the deployed database.
4. Verify `/healthz`, `/readyz`, authenticated login, role boundaries, and a non-destructive event/API query.
5. Use the existing isolated-runtime harness for firewall/kernel validation; never modify host nftables from an application deployment.

## Rollback principles

- Stop rollout on migration, authorization, audit, or runtime smoke failure.
- Preserve audit logs and operation evidence; audit rows are append-only and must not be edited to conceal a failed operation.
- Roll back application code only to a known tested revision. Do not use destructive Git cleanup against a live or evidence-bearing worktree.
- Schema rollback requires a separately reviewed migration/restore plan; SQLite DDL cannot be assumed reversible.
- After rollback, repeat health, authorization, database integrity, and firewall-state reconciliation checks.
