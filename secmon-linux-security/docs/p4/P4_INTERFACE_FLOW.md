# P4 Interface Flow

```text
Sign in
  -> Security overview
       -> Event center -> Event detail
            -> update investigation state / resolution note
            -> attack-IP disposition
                 -> confirmation + mandatory reason
                 -> backend RBAC and allowlist protection
                 -> block or unblock outcome
                 -> immutable audit entry
       -> Attack IP management
       -> Alert settings (administrators)
       -> Audit log (authorized readers)
       -> Operations health and rollback guidance
```

All destructive controls are gated in the backend. The frontend is responsible for clear authorization feedback, reason capture, confirmation, loading/empty/error states, and post-operation refresh; hiding a control is never treated as authorization.
