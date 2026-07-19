# P4 Information Architecture

## Scope and security boundary

The browser console is a same-origin client for `/api/v1`. It keeps the bearer
credential only in module memory. Route visibility and client guards provide
usable navigation, but the API RBAC check remains the authorization boundary.

## Navigation

| Route | Audience | Purpose |
| --- | --- | --- |
| `#/dashboard` | viewer+ | KPIs, recent events, attack sources, operations status |
| `#/events` | viewer+ | Filtered security-event center |
| `#/event/:id` | viewer+ | Event evidence and safely rendered raw log |
| `#/attackers` | viewer+ | Attack-IP inventory |
| `#/attacker/:ip` | viewer+ | Attack-IP context, events, block/allowlist actions |
| `#/alerts` | viewer+; updates analyst+ | Alert triage and state transitions |
| `#/operations` | viewer+ | API/database/firewall health, sources, active blocks |
| `#/allowlist` | admin | Allowlist lifecycle |
| `#/audit` | admin | Immutable audit evidence view |
| `#/admin` | admin | User account inventory |

## State and feedback

Every data view starts in a loading state and has a distinct empty state. API
401 clears the in-memory session and offers sign-in; 403 reports a safe access
denial; 404 and other failures are not misrepresented as empty data. Successful
mutations refresh their owning view so the displayed state follows the server.

Raw event logs are inserted with `textContent` into a `<pre>`; they are never
treated as HTML. No credential is written to localStorage or sessionStorage.

## Operations actions

Block, unblock, allowlist add/remove, and alert transitions require a nonblank
operational reason and a confirmation prompt. The reason accompanies APIs that
accept it; the existing unblock API is sent a JSON reason defensively while the
server continues to enforce authorization and audit policy.
