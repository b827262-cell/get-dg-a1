# P4 API Contract

All `/api/v1` endpoints require a valid bearer session unless noted. Errors use
`{"error":{"code":...,"message":"Request could not be processed","request_id":...}}`.
Validation details, SQL diagnostics, credentials, and host nftables rules are never returned.

## Roles

| Capability | viewer | analyst | admin |
| --- | --- | --- | --- |
| Events, attackers, log sources, alerts, operational health | read | read | read |
| Update alert status/assignee | no | yes | yes |
| Firewall preview | no | yes | yes |
| Firewall block/unblock, allowlist, users, audit | no | no | yes |

State-changing authenticated endpoints are limited to 60 requests per user and client per rolling minute; excess requests return `429`.

## Detection operations

- `GET /api/v1/events` and `GET /api/v1/events/{event_id}` provide bounded event records. Filters include `start`, `end`, `source_ip`, `attack_type`, `severity`, `log_source`, and `username`; page size is at most 200. Event raw logs are truncated to 2048 characters.
- `GET /api/v1/attackers` and `GET /api/v1/attackers/{ip}` provide aggregate attacker records and at most 50 recent events. Invalid or absent IPs return `404`.
- `GET /api/v1/alerts?page=&page_size=&status=&severity=&assigned_to=&src_ip=` returns `{items,page,page_size,total}`. `GET /api/v1/alerts/{id}` returns one alert or `404`.
- `PATCH /api/v1/alerts/{id}` (analyst/admin) accepts `{"status": "...", "reason":"1..256 chars", "assigned_to": integer|null}`. At least one mutable field is required; a status transition requires its reason. A non-null assignee must be an enabled user or returns `404`. It returns `{"item": alert}` and writes an audit record.
- `GET /api/v1/operations/health` returns database reachability, aggregate log-source statuses, active-block count, and only SecMon firewall presence booleans. It never exposes a ruleset.

## Firewall and allowlist

- `GET /api/v1/firewall/status`, `GET /api/v1/firewall/blocks`, `POST /api/v1/firewall/preview` preserve the P4 isolated-table contract.
- `POST /api/v1/firewall/blocks` (admin) accepts `{"ip":"IPv4-or-IPv6","reason":"1..256 chars"}` and returns `{"item":...,"idempotent":bool}`. Enabled allowlist membership returns `409`; an audit record records the denied attempt without secrets.
- `DELETE /api/v1/firewall/blocks/{ip}` (admin) requires `{"reason":"1..256 chars"}`, is idempotent, and returns `{"ip":canonical_ip,"idempotent":bool}`. The reason is retained in the audit record.
- `GET /api/v1/allowlist` (admin) returns `{items}`. `POST /api/v1/allowlist` (admin) accepts `{"ip_or_cidr":"IP or CIDR","description":"optional"}` and returns `201 {"item":...}`. Inputs are canonicalized with standard IP-network parsing. Adding a range covering an active manual block returns `409`, avoiding a contradictory allow/block state. `DELETE /api/v1/allowlist/{id}` requires `{"reason":"1..256 chars"}` and returns `204` or `404`; the reason is retained in audit evidence.

## Audit

`GET /api/v1/admin/audit` (admin) is paged and returns `{audit_entry_count,items,page,page_size}`. `GET /api/v1/admin/audit/entries` is the bounded compatibility view. Audit values are recursively redacted for credential-bearing keys. Database triggers reject update and delete operations on `audit_logs`.
