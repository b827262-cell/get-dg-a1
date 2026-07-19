# P4-02 Security Review

`claude -p --model glm-5.2` was invoked as required but returned no review
artifact because its configured authentication disabled the requested runtime.
Main Codex completed the equivalent review and remediation.

## Findings and disposition

- Critical/High: none after remediation.
- Medium fixed: preview now invokes `nft --check` with canonical parsed IP and
  fixed argv; block creates only the dedicated `inet secmon` table, typed sets,
  and its input chain/rules.
- Medium fixed: loopback, unspecified and multicast addresses are rejected to
  prevent obvious management/self-lockout cases.
- Verified: no `os.system`, `shell=True`, shell command construction or
  `nft flush ruleset` exists in production code.
- Verified: command path is configuration-constrained, argv is fixed except
  for canonical `ipaddress` output, timeout and non-zero exits fail closed.
- Verified: mutations require admin on the backend; analysts can only preview;
  viewers cannot mutate; self role elevation is denied.
- Verified: audit query is admin-only and redacts password, token,
  Authorization, secret and credential fields.
- Verified: block database failure attempts firewall rollback; unblock database
  failure attempts re-block.

Residual operational safeguard: production deployment must authorize only the
fixed nft binary through its existing privileged-service policy; the API itself
does not invoke sudo.
