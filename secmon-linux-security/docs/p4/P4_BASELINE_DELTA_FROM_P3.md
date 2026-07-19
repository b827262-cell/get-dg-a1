# P4 Baseline Delta from P3

## Relationship

- P3 acceptance HEAD: `5c43c46155dd8923c6a31bbbeb4253837d07e300`
- Authorized P4 start HEAD: `df9995329d987b646c1ab89cca65096dfc762de4`
- `git merge-base --is-ancestor` exit code: `0`

The P3 acceptance commit is an ancestor of the authorized P4 start commit.

## Commits after P3

```text
df99953 Merge pull request #3 from b827262-cell/feature/secmon-p4-nftables-rbac-audit
75a0dd7 docs(p4): record final release gate
5e67180 test(p4): complete final rollback and restart gates
ca76564 test(p4): complete codex sol security and staging gates
d35df30 test(p4): complete real kernel nftables runtime gate
7f300de docs(p4): update CI release audit
9c0c7fc docs(p4): record final release audit
20c6635 test(p4): complete firewall security and runtime gates
3768c45 feat(p4): add nftables rbac and audit controls
e97cc60 Merge pull request #2 from b827262-cell/feature/secmon-p3-dashboard-admin
```

## Classification

The delta includes a main merge commit, P3 acceptance integration history, P4 nftables/RBAC/audit functionality, runtime and rollback test fixes, security/staging test work, CI/release-audit documentation, and final release-gate documentation. It is therefore retained as part of the authorized P4 baseline rather than assumed unrelated.
