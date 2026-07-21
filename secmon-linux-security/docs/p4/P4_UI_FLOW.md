# P4 UI Flow

```text
Sign in
  -> GET /auth/me
  -> Dashboard
       -> Events -> Event detail -> back to Events
       -> Attack IPs -> IP detail -> (reason + confirm) Block / Allowlist
       -> Alerts -> (reason + confirm) acknowledge / investigate / resolve
       -> Operations -> (reason + confirm) unblock active IP
       -> Allowlist (admin) -> (reason + confirm) add / remove
       -> Audit log (admin)
```

## Guard behavior

- Missing session: always returns to sign-in; a 401 clears in-memory state.
- Viewer: read-only dashboard, events, attack IPs, alerts, and operations.
- Analyst: viewer access plus alert state transitions and firewall preview at
  the API boundary (the current P4 page exposes no write firewall control).
- Admin: analyst privileges plus block, allowlist, audit, and user pages.
- A client-side guard only prevents accidental navigation; the API must return
  403 for unauthorized direct calls.

## Failure behavior

Loading is visible before each request. Empty collections receive explicit
empty-state text. 401, 403, and 404 have non-sensitive user messages, and no
failed action is reported as successful. State-changing views reload only after
the corresponding request resolves successfully.
