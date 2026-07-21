# SeMon ATD-A 實作計畫（第一階段：可觀測性基礎）

## 0. 文件控制

| 欄位 | 內容 |
|---|---|
| 文件代碼 | `SECMON-ATD-A-IMPLEMENTATION-PLAN` |
| 任務代碼 | `SECMON-ATD-INDEPENDENT-DESIGN-REVIEW-0720`（衍生） |
| 階段 | ATD-A（異常流量偵測子系統·第一期：可觀測性基礎；等同主設計文件之 `P1-A`） |
| 建立日期 | 2026-07-20（UTC） |
| 執行模型 | `ZAI GLM-5.2` |
| 前置審查 | `docs/SECMON_ATD_INDEPENDENT_DESIGN_REVIEW_2026-07-20.md` → **PASS** |
| 對應設計 | `docs/SECMON_ANOMALOUS_TRAFFIC_DETECTION_MASTER_DESIGN.md` v1.1-draft §19 P1-A |
| 文件狀態 | `Draft`（計畫；**未實作**） |

> 本文件**只規劃** ATD-A 實作，**不寫程式碼、不建 migration、不修改 systemd/nftables**。實作須另立任務與分支，並依本計畫驗收。

---

## 1. ATD-A 範圍與目標

### 1.1 In Scope（本階段做）

- `network_interfaces`、`network_samples` 兩張資料表（migration `012_anomalous_traffic_detection.sql` 的**第一部分**，僅這兩表 + 索引）。
- Collector skeleton：以最小權限讀取低權限計量來源（`/proc/net/dev`、`ip -s link`、`/proc/net/snmp`、`ss -s`），1s 採樣週期，寫入 `network_samples`。
- 基本 API（4 個唯讀端點）：`/api/v1/network/overview`、`/api/v1/network/interfaces`、`/api/v1/network/top-talkers`、`/api/v1/network/traffic-series`。
- 單元測試、migration fresh/repeat 測試、SQLite integrity 測試、Collector restart / Host reboot 模擬測試。

### 1.2 Out of Scope（本階段不做）

- `network_flows`、`traffic_baselines`、`detection_rules`、`traffic_alerts`、`traffic_incidents`、`asset_profiles`、`network_allowlists`、`response_actions`（屬 ATD-B~E）。
- L1/L2/L3 偵測、告警、事件、Incident（屬 ATD-B/C）。
- nftables / Response Engine（屬 ATD-E）。
- 前台 Dashboard 新頁（屬 ATD-D；本階段僅 API）。
- IPv6 來源擴充（本階段 schema 已含 `*_ip_type` 欄，Collector 先支援 v4，v6 列為 ATD-A.1 小增補）。
- nftables counters / conntrack 全表 / NFLOG（屬 ATD-B 來源擴充；本階段只用無需 CAP 的來源）。

### 1.3 完成定義（Definition of Done）

ATD-A 視為完成，當且僅當：

1. `012_anomalous_traffic_detection.sql` 能 fresh run 與 repeat run（重複套用同一 migration 不報錯），且 `PRAGMA quick_check='ok'`。
2. `network_interfaces`、`network_samples` 存在且欄位/型別/索引符合 §3 規格。
3. Collector 能以**非 root `secmon` user**、**零新特權**讀取 §4 所列來源並寫入 `network_samples`（採樣週期可設定，預設 1s）。
4. 4 個 API 端點回應符合既有 `/api/v1` 慣例（分頁 `{"items","page","page_size","total"}`、錯誤 `{"error":{"code","message","request_id"}}`、JWT bearer、小寫角色 RBAC、`require_write_rate` 不適用因皆唯讀）。
5. 全部單元測試 + migration 測試 + integrity 測試通過（pytest）。
6. `make check`（lint/typecheck/test）通過。
7. **未**啟用任何告警、**未**觸碰 nftables、**未**寫入既有 11 張表的任何資料。
8. 效能量化已實測記錄（samples/s、寫入量、磁碟成長）→ 解除 M-13/M-14。

---

## 2. 前置條件（§15 審查 C-1~C-8）

| 條件 | 狀態 |
|---|---|
| C-1 審查 PASS | ✅ |
| C-2 主設計 v1.1-draft 修正完成 | ✅ |
| C-3 migration 規格遵循 §12 對齊 8 點 | 本計畫 §3 落實 |
| C-4 零新特權（複用 `secmon` user） | 本計畫 §4/§6 落實 |
| C-5 API 沿用既有慣例 | 本計畫 §5 落實 |
| C-6 不新增 systemd unit | 本計畫 §6 落實（沿用 `secmon-collector`） |
| C-7 補 `test_migrate_repeat_run` | 本計畫 §7 落實 |
| C-8 ATD-A 後補效能量化 | 本計畫 §1.3/§7 落實 |

---

## 3. 資料模型（migration 規格）

### 3.1 檔案

`database/migrations/012_anomalous_traffic_detection.sql`

### 3.2 必須遵循的對齊規則（解 M-1/H-1/H-2/H-4/M-2）

- 全部 `CREATE TABLE IF NOT EXISTS`、`CREATE INDEX IF NOT EXISTS`。
- 時間戳一律 `DEFAULT CURRENT_TIMESTAMP`（**不**用 `strftime(...)`）。
- severity 本階段不使用（無 alerts 表）；`network_samples` 無 status/severity 欄。
- IP 欄：本階段 `network_samples` 不存 per-flow IP（純介面計量）；故無 `src_ip_type` 問題。後續 `network_flows` 才需 discriminator。
- 整數 FK：`network_samples.interface_id` 須 `REFERENCES network_interfaces(id) ON DELETE CASCADE`（samples 隨介面刪除而清理）。
- 結尾可選擇性 `INSERT OR IGNORE INTO schema_migrations(version) VALUES ('012_anomalous_traffic_detection');`（runner 會自動記錄，self-insert 冗餘但無害，沿用 001/005 風格）。

### 3.3 schema（最終以實作 migration 為準；此為規格）

```sql
-- 012_anomalous_traffic_detection.sql (ATD-A 部分)

CREATE TABLE IF NOT EXISTS network_interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    ifindex INTEGER,
    iface_type TEXT,
    is_internal INTEGER NOT NULL DEFAULT 1 CHECK (is_internal IN (0,1)),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS network_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sampled_at TEXT NOT NULL,
    interface_id INTEGER NOT NULL REFERENCES network_interfaces(id) ON DELETE CASCADE,
    sensor_host TEXT NOT NULL,
    bps_in REAL, bps_out REAL,
    pps_in REAL, pps_out REAL,
    tcp_ratio REAL, udp_ratio REAL, icmp_ratio REAL,
    syn_pps REAL, syn_ack_ratio REAL, rst_count INTEGER,
    active_conn INTEGER, new_conn_per_sec REAL, failed_conn_rate REAL,
    i2i_bps REAL, i2e_bps REAL, e2i_bps REAL,
    unique_dst_ip INTEGER, unique_dst_port INTEGER, unique_src_ip INTEGER,
    rule_version TEXT,
    retention_until TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_network_samples_time ON network_samples(sampled_at);
CREATE INDEX IF NOT EXISTS idx_network_samples_iface_time ON network_samples(interface_id, sampled_at);
```

> 註：ATD-A 採樣僅能填部分欄位（bps/pps/connection 類；`unique_*`、`i2i/i2e/e2i` 在無 conntrack/NFLOG 時為 NULL，留待 ATD-B 補全）。這些 NULL 欄位為可接受的中間狀態，API 須容忍 NULL。

---

## 4. Collector skeleton

### 4.1 模組位置

`backend/collectors/network_metrics.py`（沿用既有 `backend/collectors/` 慣例，如 `ssh.py`、`main.py`）。

### 4.2 採樣來源（本階段：零特權）

| 來源 | 欄位 | 權限 | 本階段 |
|---|---|---|---|
| `/proc/net/dev` | per-iface rx/tx bytes/packets | 無需 root | ✅ 主來源（bps/pps） |
| `/proc/net/snmp` | TCP/UDP/ICMP 統計、SYN/ACK/RST | 無需 root | ✅ 協定比例、syn_pps |
| `ss -s` 摘要 | ESTABLISHED 數 | 無需 root | ✅ active_conn |
| `ip -s link` | 介面狀態 | 無需 root | ✅ interface 探測 |
| conntrack 全表 | flow 詳細 | 需 CAP_NET_ADMIN | ❌ 留 ATD-B |
| nftables counters | 規則計數 | 需 CAP_NET_ADMIN | ❌ 留 ATD-B |
| NFLOG | 標頭取樣 | 需 CAP_NET_RAW | ❌ 留 ATD-B |

> **解 H-3/M-權限**：本階段只用 `/proc`、`ss`、`ip` 等**無需 root/CAP** 來源 → 與既有 `secmon-collector.service`（`User=secmon`、`NoNewPrivileges=true`、無 `AmbientCapabilities`）完全相容，**零新特權**。

### 4.3 採樣週期與降級

- 預設 1s（可由 config 設定 `atd_sample_interval_seconds`，範圍 1~60）。
- 差分計算 bps/pps：與前一個 sample 比較（首個 sample 只存絕對計數，bps/pps=NULL）。
- 降級：若單次採樣逾時（如 `/proc` 讀取 > 0.5s），記錄 warning 並略過該輪（不停 loop、不崩潰）。

### 4.4 寫入

- 小批次 transaction（每輪 1 筆/介面，batch commit；與既有 collector「小批次 transaction」原則一致）。
- `sensor_host` 來自 `socket.gethostname()` 或 config。
- `retention_until` = `sampled_at + 設定保留天數`（預設 7 天；解 M-14 後調整）。

### 4.5 IPv4/IPv6

- 本階段 `network_samples` 無 IP 欄 → 無 v4/v6 問題。
- 介面辨識含 IPv6 位址（`ip link`/`ip -6 addr`）但不影響 samples 寫入。
- v6 per-flow 留 ATD-B。

---

## 5. 基本 API（4 端點，全唯讀）

### 5.1 實作位置

沿用既有**單檔 `backend/app.py` + `create_app()` + `@app.<method>`** 慣例（**不**引入 `APIRouter`；現有專案無任何 router）。

### 5.2 端點規格

| 方法 | 路徑 | 角色 | 回應 |
|---|---|---|---|
| GET | `/api/v1/network/overview` | viewer+ | 最新 sample 彙總：`bps_total`、`pps_total`、`active_conn`、`direction`（容忍 NULL）、`protocol_ratio`（容忍 NULL） |
| GET | `/api/v1/network/interfaces` | viewer+ | `{"items":[{id,name,ifindex,iface_type,is_internal,enabled,...}]}`（小型集合，可不分頁或分頁） |
| GET | `/api/v1/network/top-talkers` | viewer+ | ATD-A 階段因無 per-IP 流量 → 回 `{"items":[], "note":"per-IP flows available in ATD-B"}` 或以介面維度回 Top interface；**須明示資料不足而非顯示假 0**（解 §11 UI 反模式） |
| GET | `/api/v1/network/traffic-series` | viewer+ | `start`/`end`/`window` 查詢參數；回 `{"items":[...], "page":N, "page_size":N, "total":N}` |

### 5.3 必須遵循（解 H-5~H-8）

- 路徑 `/api/v1/network/...`（非 `/api/network`）。
- 分頁：`{"items","page","page_size","total"}`，`page`/`page_size` 查詢參數，`MAX_PAGE_SIZE=200`。
- 錯誤：沿用既有 exception handlers（`{"error":{"code","message","request_id"}}`）。
- RBAC：`Annotated[UserOut, Depends(require_read)]`（viewer+）。
- Auth：JWT bearer（沿用 `current_user`）。
- 唯讀端點**無** `require_write_rate`（該 dependency 僅寫入端點用）。
- 時間範圍：強制 `start`/`end`（ISO 8601），最長跨度由 config 限制（避免全表掃描）。
- NULL 容忍：指標可能 NULL（採樣未涵蓋），回應須 `null` 或省略，**不得**偽造 0。

---

## 6. systemd 執行方式（解 M-1/C-6）

- **不新增 unit**。ATD-A Collector 作為既有 `secmon-collector.service` 的一個子任務（在 `backend/collectors/main.py` 的收集迴圈中加入 network_metrics 採樣），或作為 collector 內的獨立 thread/async task。
- 執行身份：`secmon`（既有）。
- **不**新增 `AmbientCapabilities`、**不**改 sudoers。
- `WorkingDirectory`/`ReadWritePaths` 沿用既有（`/var/lib/secmon`、`/var/log/secmon`）。
- 若 Collector 與 API 共用同一 SQLite（既有模式），WAL + `busy_timeout=5000` 已足夠 ATD-A 寫入量（實測後確認，解 M-14）。

> **架構澄清**：主設計文件 §5.1 的「Alert Service」「Response Engine」「Scheduler」**不是** ATD-A 要建立的 daemon；它們是子模組/任務。ATD-A 只動 Collector 與 API。

---

## 7. 測試計畫

### 7.1 單元測試（pytest，沿用 `tests/` 慣例）

- `tests/test_atd_collector.py`：
  - 解析 `/proc/net/dev` fixture → 正確欄位。
  - 差分 bps/pps 計算正確。
  - 首個 sample（無前值）bps/pps=NULL。
  - 採樣逾時 → 略過該輪不崩潰。
  - IPv6 介面辨識。
- `tests/test_atd_api.py`（TestClient + `make_client` fixture）：
  - 4 端點 401 未授權、403（無，因皆 viewer+）、200 授權。
  - 分頁格式正確。
  - `start/end` 強制、超長跨度拒絕。
  - NULL 指標正確回 `null`。
  - overview 容忍無資料（不顯示假 0）。

### 7.2 Migration 測試（解 M-4/C-7）

- `tests/test_migrate.py` 擴充：
  - `test_initial_migration_creates_schema`（既有）：加入斷言 `network_interfaces`、`network_samples` 存在。
  - **新增** `test_migrate_repeat_run`：對同一 DB 套用 `migrate()` 兩次，第二次不報錯、`schema_migrations` 不重複、`PRAGMA quick_check='ok'`、表數不變。
  - **新增** `test_migrate_012_atd_schema`：斷言 `network_samples.interface_id` 的 FK 存在（`PRAGMA foreign_key_list`）、索引存在（`PRAGMA index_list`）。

### 7.3 SQLite integrity

- 每個測試 fixture（`make_client`）已在 migration 後具 `PRAGMA quick_check`；ATD-A 維持。
- 新增 `test_atd_wal_mode`：斷言連線 `journal_mode='wal'`、`foreign_keys=1`、`busy_timeout=5000`。

### 7.4 Collector restart

- `tests/test_atd_collector_restart.py`：
  - 模擬 Collector 寫入 N 筆 → 「重啟」（重新 instantiate collector）→ 續寫不重複、sampled_at 單調。
  - `retention_until` 正確計算。

### 7.5 Host reboot 模擬

- 無法真實 reboot；以「DB 既有資料 + 重新啟動 Collector + API」模擬：
  - 重啟後 overview/traffic-series 能讀到舊資料。
  - 介面若因 reboot 改名（`eth0`→`enp3s0`）：`network_interfaces` 以 `name UNIQUE` 處理，新介面新增、舊介面保留（不刪，避免 cascade 刪 samples）；`enabled` 可標 0。

### 7.6 Rollback（ATD-A 層級）

- ATD-A 無 nftables rollback。
- 「Rollback」在此指：**停用 ATD-A** 的能力 ——
  - config `atd_enabled=False` → Collector 不採樣、API 回 503 或空集合。
  - migration `012` 為純新增（不改既有表）→ 「回退」=停用 Collector + 不查新表；既有 P0~P5 功能完全不受影響。
  - 提供 `scripts/atd_disable.sh`（僅改 config，不動 DB；非本階段強制）。

### 7.7 效能量化（解 M-13/M-14/C-8）

- ATD-A 實作後於隔離環境實測並記錄：
  - samples/s（每介面每秒 1 筆 × 介面數）。
  - 每日磁碟成長（samples 7 天保留下的 DB 大小）。
  - `busy_timeout` 衝突次數（collector 寫 vs api 讀）。
  - 記錄於 `docs/SECMON_ATD_A_PERFORMANCE_BASELINE.md`（實作階段產出，非本計畫）。

---

## 8. 權限需求總表

| 元件 | 身份 | 權限 | 來源 |
|---|---|---|---|
| Collector（network_metrics） | `secmon` | 讀 `/proc/net/*`、執行 `ss`/`ip`（一般使用者可） | 無新特權 |
| API（4 端點） | `secmon`（經 systemd） | 讀 SQLite | 無新特權 |
| Migration | 部署者（一次性） | 套用 `012` SQL | 沿用既有 migrate 流程 |

**零新 sudoers、零新 CAP、零新 systemd unit。**

---

## 9. 驗收檢核表

- [ ] `012_anomalous_traffic_detection.sql` fresh + repeat run 通過。
- [ ] `network_interfaces`、`network_samples` schema 符合 §3.3。
- [ ] FK `network_samples.interface_id REFERENCES network_interfaces(id) ON DELETE CASCADE` 存在。
- [ ] 時間戳用 `CURRENT_TIMESTAMP`（非 `strftime`）。
- [ ] Collector 以 `secmon` user 零特權採樣 `/proc`+`ss`+`ip`。
- [ ] 4 API 端點符合 `/api/v1/network/...`、既有分頁/錯誤/RBAC 慣例。
- [ ] NULL 指標正確處理（不偽造 0）。
- [ ] `test_migrate_repeat_run` 通過。
- [ ] 全部 pytest 通過、`make check` 通過。
- [ ] 效能量化記錄於 `SECMON_ATD_A_PERFORMANCE_BASELINE.md`。
- [ ] 未啟用告警、未觸 nftables、未寫既有 11 表。
- [ ] `audit_logs` 不可竄改性測試仍通過（既有測試不退化）。

---

## 10. 風險與回退

| 風險 | 回退 |
|---|---|
| `012` migration 對既有 DB 造成損害 | 純 `CREATE TABLE IF NOT EXISTS`（新增表）；最壞情況停用 ATD + 新表閒置，不影響既有 |
| Collector 採樣拖慢既有 collector 迴圈 | config `atd_enabled=False` 立即停用；採樣以獨立 task/thread 隔離 |
| API 端點新增造成既有路由衝突 | 路徑 `/api/v1/network/...` 為新命名空間，不與既有衝突；StaticFiles mount 在路由之後（既有模式）不變 |
| SQLite 寫入鎖競爭 | WAL + `busy_timeout=5000`；實測後若不足，降採樣頻率或批次化 |

---

## 11. 不在 ATD-A 處理的後續項目（連結）

| 項目 | 後續階段 |
|---|---|
| `network_flows` + per-IP/Port 流量 + IPv6 per-flow | ATD-B |
| L1 固定門檻偵測 + `detection_rules`/`traffic_alerts` | ATD-B |
| conntrack/nftables counters/NFLOG 來源（需 CAP） | ATD-B（須先解特權） |
| L2 動態基線（MAD=0/冷啟/回退/時區，M-9~M-12） | ATD-C |
| 前台 Dashboard 新頁 | ATD-D |
| 待核准封鎖 + Rollback + emergency allowlist（H-9/M-3/M-6/M-7） | ATD-E |
| `block_source` enum 擴充（`'atd'`） | ATD-E migration |

---

## 12. 狀態欄位

```text
ATD_A_PLAN_STATUS: COMPLETE
ATD_A_IMPLEMENTATION_STATUS: NOT_STARTED
ATD_A_RUNTIME_STATUS: NOT_TESTED
ATD_A_QUALITY_GATE_STATUS: NOT_RUN
```

> 本計畫完成不等於 ATD-A 實作完成或 Release Gate 通過。實作、Runtime、Quality Gate、Release Gate、Formal Acceptance 待後續程序。

---

## 13. 實作期細化（Addendum — 2026-07-20，ATD-A 實作時確認）

實作時經使用者確認，對本計畫做以下三點細化（不改變 ATD-A 整體範圍）：

1. **Collector 掛載**：併入既有 `backend/collectors/main.py` 的 `run_collector_loop`，
   受 `network_metrics_enabled` flag 控制（預設 `False`），有自己的 cadence
   （`network_metrics_interval_seconds`）。**不新增 systemd unit**，沿用既有
   `secmon-collector.service`。對應 C-6。

2. **network_samples 資料形態**：存**累積 counter 原值**（rx_bytes/tx_bytes/...），
   bps/pps 由 API `/api/v1/network/traffic-series` 查詢時以 per-interface 差分計算。
   Counter reset / reboot / wrap → 該區間 rate 為 `null`（不產生負值）。此選擇較
   原 §3.3 的「同時存 bps/pps」簡化 schema 並允許事後重算。

3. **Retention**：**不加 `retention_until` 欄**，靠 `sampled_at` 時間範圍刪除（貼近
   既有 SeMon 慣例——既有表無 per-row retention 欄）。對應原 §3.2 schema 移除
   `retention_until`。

另：`top-talkers` 端點因 ATD-A 無 per-IP flow，改為**介面層排名 + 明確
`scope: "interface"` 標示**（不捏造 IP 排名），較原 §5.4 的「回空 + note」更有用
且仍誠實。

實作完成狀態見 `SECMON_ATD_A_PERFORMANCE_BASELINE.md` 與 ATD-A 實作 commit 序列。
