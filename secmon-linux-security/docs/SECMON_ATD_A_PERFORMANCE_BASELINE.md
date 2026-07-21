# SeMon ATD-A Performance Baseline

## 0. Document Control

| Field | Value |
|---|---|
| Document | `SECMON-ATD-A-PERFORMANCE-BASELINE` |
| Phase | ATD-A (Observability Foundation) |
| Created | 2026-07-20 (UTC) |
| Model | ZAI GLM-5.2 |
| Status | **Development-machine measurement — NOT a production capacity ceiling** |

> The figures below were captured on the developer's Arch Linux workstation to
> sanity-check that ATD-A adds negligible overhead and that the API responds
> within interactive latency budgets. They are **not** a production capacity
> statement. Production sizing must be re-measured on the deployment host under
> realistic interface counts and retention.

## 1. Test Environment

| Item | Value |
|---|---|
| OS / Kernel | Arch Linux / 7.0.11-arch1-1 |
| Architecture | x86_64 |
| Python | 3.14.5 (project floor: `>=3.11`) |
| SeMon branch | `feature/secmon-atd-a-observability` |
| Host interfaces | `eno1`, `lo`, `tailscale0`, `wlan0` (4 total; 3 sampled — loopback excluded) |
| Collector user | non-root (`uid=1000`, `euid=1000`); **no CAP_NET_ADMIN / CAP_NET_RAW** |
| MemTotal | ~15.0 GiB |
| MemAvailable | ~6.5 GiB (free during measurement) |
| Sample cadence | default `network_metrics_interval_seconds = 5.0` |

## 2. Collector Overhead

Single `NetworkMetricsCollector.collect_once()` round (read `/proc/net/dev`,
`/proc/net/sockstat{,6}`, `/sys/class/net/*`; upsert interfaces; insert 3 samples):

| Metric | Value |
|---|---|
| Round duration (min) | 0.97 ms |
| Round duration (median) | 1.60 ms |
| Round duration (max) | 2.11 ms |
| Max RSS (whole Python process) | ~44 MB |
| Sources used | `/proc/net/dev`, `/proc/net/sockstat`, `/proc/net/sockstat6`, `/sys/class/net/*` |
| Subprocess invocations | 0 (pure file reads) |
| Privileged capabilities required | 0 |

The round cost is dominated by SQLite WAL commit; even at the minimum 1-second
cadence it consumes well under 1% of one CPU on this host.

## 3. Write Volume Projection

At the default 5-second cadence with 3 sampled interfaces:

- Rounds per minute: 12
- Samples per round: 3 (one per non-loopback interface)
- **Projected writes per minute: 36** (≈ 1,728/hour, ≈ 41,472/day)

At 7-day retention (`network_metrics_retention_days = 7`) the steady-state row
count is ≈ 290k rows in `network_samples`. Each row is ~16 numeric/short-text
columns; empirically the SQLite file grows by well under 50 MB/week at this
cadence (to be re-confirmed at ATD-A acceptance with real 7-day data).

## 4. API Latency (TestClient, in-process)

30 iterations per endpoint against a freshly migrated DB with 9 real samples
across 4 interfaces; bearer-authenticated `viewer`:

| Endpoint | p50 | p95 | p99 |
|---|---|---|---|
| `GET /api/v1/network/overview` | 3.51 ms | 6.45 ms | 7.41 ms |
| `GET /api/v1/network/interfaces` | 3.60 ms | 4.82 ms | 11.78 ms |
| `GET /api/v1/network/traffic-series` (1-day range) | 3.90 ms | 7.27 ms | 9.36 ms |
| `GET /api/v1/network/top-talkers` | 3.19 ms | 4.14 ms | 7.59 ms |

All four endpoints land well inside a 50 ms interactive budget at this dataset
size. `traffic-series` performs a per-row previous-sample lookup; with the
`(interface_id, sampled_at)` composite index it remains O(rows in page). At
much larger retention (millions of rows) the series endpoint should be
benchmarked again and, if needed, downsampled via the multi-window roll-up
planned for a later phase.

## 5. SQLite Integrity

After real sample collection:

- `PRAGMA quick_check` → `ok`
- `PRAGMA foreign_key_check` → empty (no violations)
- `journal_mode = WAL`, `foreign_keys = ON`, `busy_timeout = 5000` (set by the
  collector on every connection)

## 6. Counter Semantics Verified

Two consecutive real rounds on the live host confirmed counters are stored as
raw cumulative kernel values and never regress within an uptime:

| Interface | round1 rx_bytes | round2 rx_bytes | monotonic? |
|---|---|---|---|
| `eno1` | 0 | 0 | ✓ |
| `tailscale0` | 301,330,504 | 301,330,504 | ✓ |
| `wlan0` | 28,998,804,211 | 28,998,804,548 | ✓ (rising) |

Counter reset / reboot / 32-bit wrap is handled at the **API** layer: a sample
whose counter is lower than its predecessor yields a `null` rate for that
interval (never a negative value). This is exercised by
`test_traffic_series_derives_rates_and_handles_counter_reset`.

## 7. Test Limitations

- Measurements are from a single development workstation, not the production
  SeMon host; absolute numbers will differ in production.
- `traffic-series` was benchmarked on a small dataset (9 samples). Larger
  retention windows must be re-measured before being declared production-ready.
- No concurrent writer/reader contention was simulated beyond the implicit
  SQLite WAL behaviour; production load with the API and collector hitting the
  same DB file concurrently should be re-measured.
- Network payload capture, per-IP flows, conntrack, NFLOG and nftables counters
  are **out of ATD-A scope** and contribute zero overhead here; their cost will
  be measured when introduced (ATD-B and later).

## 8. Rollback Cost

Disabling ATD-A (`SECMON_NETWORK_METRICS_ENABLED=false`) stops sampling
immediately on the next collector round; the four API endpoints remain
available (returning `collector_status: "stale"` / empty results once retention
expires) but perform no writes. No `DROP TABLE` is used for rollback; the new
tables simply go idle. Existing P0–P5 functionality is unaffected.
