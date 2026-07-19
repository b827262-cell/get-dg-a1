# P4 Data Model

P4 keeps SQLite foreign keys enabled for every API connection and applies ordered SQL migrations through `database/migrate.py`.

| Table | P4 operational use | Integrity controls |
| --- | --- | --- |
| `attack_events` | Immutable detector evidence displayed by event and attacker APIs | unique `event_key`; severity and port checks; bounded API projection |
| `attackers` | Per-source-IP aggregate and status | source IP primary key; indexed score/last-seen reads |
| `alerts` | Analyst workflow tied optionally to an event and assignee | severity/status checks; FK event and user; P4 indexes on status/updated time and IP |
| `blocked_ips` | Intentional isolated firewall blocks | one active block per IP partial unique index; actor/release FKs |
| `ip_allowlist` | Explicit protection from manual blocking | canonical API input; unique value; enabled/value index |
| `audit_logs` | Append-only action evidence | audit migration metadata plus P4 `BEFORE UPDATE` and `BEFORE DELETE` abort triggers |
| `log_sources` | Collector health aggregates | status check; operational health uses only aggregate counts |

Migration `010_detection_operations.sql` adds the alert and allowlist read indexes and immutable-audit triggers. It is repeatable under the existing `schema_migrations` ledger. The allowlist is enforced by the manual block path before any kernel operation, and a new allowlist that would cover an active block is rejected instead of silently creating contradictory security state.
