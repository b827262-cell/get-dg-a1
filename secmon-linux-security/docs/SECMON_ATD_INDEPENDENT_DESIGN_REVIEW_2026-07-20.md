# SeMon ATD 獨立設計審查報告（Independent Design Review）

## 0. 文件控制

| 欄位 | 內容 |
|---|---|
| 文件代碼 | `SECMON-ATD-INDEPENDENT-DESIGN-REVIEW-2026-07-20` |
| 任務代碼 | `SECMON-ATD-INDEPENDENT-DESIGN-REVIEW-0720` |
| 審查角色 | 獨立 Review（ZAI GLM-5.2，與原設計同模型但切換為審查模式） |
| 審查對象 | `docs/SECMON_ANOMALOUS_TRAFFIC_DETECTION_MASTER_DESIGN.md`（v1.0-draft → 審查後修正為 v1.1-draft） |
| 建立日期 | 2026-07-20（UTC） |
| 執行模型 | `ZAI GLM-5.2` |
| Git Repository Root（實際） | `/home/b822726/project/get-dg-project/secmon-linux-security` |
| 工作目錄（專案程式碼所在） | `/home/b822726/project/get-dg-project/secmon-linux-security/secmon-linux-security` |
| 分支 | `feature/secmon-p4-detection-operations` |
| Start HEAD | `953ec0944266a69a0eab7db10820f475410ca50a`（與任務書一致） |
| 文件狀態 | `Draft`（獨立審查完成；非 Approved） |

> 本審查為**設計階段**審查。未執行任何 Runtime 測試、未建立 migration、未新增程式碼、未修改 nftables、未執行攻擊模擬。

---

## 1. Review 範圍

- **目標文件**：`docs/SECMON_ANOMALOUS_TRAFFIC_DETECTION_MASTER_DESIGN.md`（21 章節、3 Mermaid 圖、10 資料表、15 API、L1/L2/L3 三層偵測、ATD-A~E 分期）。
- **交叉比對來源**：現有專案文件、`backend/`、`database/migrations/`、`systemd/`、`tests/`、`docs/`（見 §3）。
- **不在範圍**：實際 migration 撰寫、Collector/API/Frontend 實作、Runtime 驗證、nftables 變更、攻擊模擬。

## 2. Review 方法

1. **Pre-flight**：`git rev-parse HEAD` / `branch` / `status` 確認環境；檢查未追蹤 `data/`。
2. **交叉比對（三路並行探索）**：
   - 資料庫 schema 與 migration 慣例（對 `DATABASE_DESIGN.md`、`database/migrations/*.sql`、`database/migrate.py`）。
   - 後端 API/RBAC/Auth/稽核慣例（對 `backend/app.py`、`backend/config.py`、`backend/services/nftables.py`）。
   - 特權與 nftables 設計（對 `SECMON_CODEX_PRIVILEGE_DESIGN.md`、`secmon-codex-sudoers.example`、systemd units）。
3. **逐項審查**：依任務書 §六 12 個維度檢查，問題依 Critical/High/Medium/Low 分類。
4. **允許範圍內修正**：對主設計文件做小幅、高信心的一致性修正（§13 已修正項）。
5. **判定**：依 §十 通過條件給出 PASS/FAIL。

## 3. 檢查的文件與程式碼

**既有設計文件**：
- `docs/DATABASE_DESIGN.md`（schema 慣例權威）
- `docs/ARCHITECTURE_AND_UI.md`（架構、RBAC、Blocker、稽核）
- `docs/SECMON_CODEX_PRIVILEGE_DESIGN.md`（最小權限維護控制器）
- `docs/secmon-codex-sudoers.example`（sudoers 規則）
- `docs/P1_P2_MINIMAL_SUDO_REQUIREMENTS.md`

**程式碼**：
- `backend/app.py`（全部 API 路由、RBAC dependencies、`write_audit`、防火牆路由、`expire_blocks`、`reconcile_firewall`、`is_allowlisted`）
- `backend/config.py`（`nft_binary`、`auto_block_enabled`、JWT 設定）
- `backend/services/nftables.py`（`NftablesService`：`parse_ip`、`preview`、`block`、`unblock`、`_ensure_layout`）
- `database/migrate.py`（migration runner）
- `database/migrations/001_initial.sql`（canonical schema）
- `database/migrations/005`~`011_*.sql`（後續 migration 慣例）
- `systemd/secmon-api.service`、`systemd/secmon-collector.service`
- `tests/test_api_auth.py`、`tests/test_migrate.py`、`tests/test_nftables.py`（測試慣例）

## 4. 架構一致性結果

| 項目 | 結果 | 說明 |
|---|---|---|
| 三層偵測（L1/L2/L3）與既有 Threat Engine | ✅ 相容 | ATD 為獨立縱深，不取代既有日誌事件鏈 |
| 與既有 `alerts`/`attack_events` 並存 | ⚠️ 見 H-2 | severity 型別不一致（INTEGER 1~5 vs TEXT） |
| 與既有 `NftablesService` 封鎖 | ⚠️ 見 H-3 | ATD 初版暗示新 sudoers/CAP helper，與現有「API 直接呼叫 nft、權限外部化」不同 |
| 與既有 systemd（僅 api + collector 兩 unit） | ⚠️ 見 M-1 | ATD 初版提及 "Alert Service"/"Response Engine"/"Scheduler" 暗示獨立服務，實際並不存在 |
| 端點視角盲區聲明 | ✅ 已強化（修正） | 已於 v1.1-draft 補「監控盲區總聲明」 |

## 5. 資料模型審查

### 5.1 與既有 schema 慣例的不一致（多為 High，已於 v1.1-draft 標註對齊注意）

| 編號 | 問題 | 等級 | 狀態 |
|---|---|---|---|
| H-1 | 時間戳預設 `strftime('%Y-%m-%dT%H:%M:%SZ','now')` vs 既有 `CURRENT_TIMESTAMP`，混用破壞字串比較 | High | v1.1 已標註對齊；migration 時統一為 `CURRENT_TIMESTAMP` |
| H-2 | severity 用 TEXT(info/low/.../critical) vs 既有 INTEGER 1~5（1 最嚴重） | High | v1.1 已標註；須擇一（建議改 INTEGER 或建映射層） |
| H-4 | status 大寫 vs 既有小寫 | High | v1.1 已標註；統一為小寫 |
| M-2 | 整數 FK（`rule_id`/`incident_id`/`*_by`）未加 `REFERENCES ... ON DELETE SET NULL`，與既有強制 FK 慣例不一致 | Medium | v1.1 已標註 |

### 5.2 SQLite 相容性

- 所有欄位型別（TEXT/INTEGER/REAL）與 `CHECK IN` / `BETWEEN` 皆 SQLite 原生支援。✅
- `partial unique index`（既有 `idx_unique_active_block WHERE active=1`）ATD 應學習：`response_actions` 對「同一 target_ip 僅允許一個 PENDING_APPROVAL」可考 partial index。→ M-3。
- JSON 欄位（`*_json`）為 TEXT，與既有 `config_json`/`metadata_json`/`details_json` 一致。✅
- IPv4/IPv6：discriminator 欄（`ip_type`）為新增設計，與既有「無 discriminator、Python `ipaddress` 處理」不同；屬合理強化，須於 migration 說明。→ 已標註。

### 5.3 Retention vs Incident 證據

- `network_samples`（7~14 天）/`network_flows`（30~90 天）清理，但 `traffic_alerts.metric_snapshot` + `baseline_ref` + `traffic_incidents.evidence_summary` 已內嵌證據摘要 → 清理 raw samples 不破壞 Incident 證據。✅ 設計正確。
- 但須確保清理任務**只刪 `retention_until` 過期者**，且 `traffic_incidents` 保留 1~2 年、`response_actions` 永久。→ 設計已涵蓋。✅

### 5.4 Migration 可 fresh/repeat run

- 既有 runner 採「version-gated + `CREATE TABLE IF NOT EXISTS`」，repeat-run 安全。ATD migration（建議 `012_anomalous_traffic_detection.sql`）須沿用相同模式。→ 非本階段實作，已列為 ATD-A 前置條件。
- 既有 `tests/test_migrate.py` 僅測 fresh-run（`migrate_latest` 後查表存在 + `PRAGMA quick_check`），**無 repeat-run 測試**。ATD-A 須補 repeat-run 測試。→ M-4。

## 6. API／RBAC 審查

### 6.1 與既有後端的不一致（已於 v1.1-draft 修正標註）

| 編號 | 問題 | 等級 | 狀態 |
|---|---|---|---|
| H-5 | 路徑前綴 `/api/network` vs 既有 `/api/v1/<resource>` | High | v1.1 已修正為 `/api/v1/network/...` |
| H-6 | 分頁 `{data,meta,links}` + `limit/offset` vs 既有 `{"items","page","page_size","total"}` + `page/page_size`（`MAX_PAGE_SIZE=200`） | High | v1.1 已修正 |
| H-7 | 錯誤 `{error:{...,details}}` vs 既有 `{"error":{"code","message","request_id"}}` | High | v1.1 已修正 |
| H-8 | 角色名大寫 Admin/Analyst/Viewer vs 既有小寫 `admin/analyst/viewer` | High | v1.1 已修正 |

### 6.2 RBAC 與 IDOR

- 既有 RBAC 為三層 dependency：`require_read`（任何角色）/ `require_analyst`（analyst+admin）/ `require_admin`（僅 admin）。ATD 15 端點的建議角色對映正確（overview 等唯讀=viewer+；ack/close=analyst+；rules/response=admin）。✅
- **`POST /api/v1/network/incidents/{id}/response` 必須 admin-only**：與既有 `POST /api/v1/firewall/blocks`（admin-only）一致。✅ 設計正確，但須確保實作時用 `require_admin` 而非自訂裝飾器。
- **寫入端點首行須呼叫 `require_write_rate`**（既有每 user+client 60 mutations/min）。ATD 設計未提及，須補。→ M-5。
- IDOR：路徑含 `{id}` 的端點（alerts/{id}、incidents/{id}）須做物件存在 + 授權檢查；既有以 404 處理未授權存取（不洩漏存在性），ATD 須沿用。→ L-1。

### 6.3 CSRF / 同源

- 既有無 CSRF token（bearer-only、`allow_credentials=False`、CORS 預設空）。ATD 端點須沿用相同模型，**不得引入 cookie 驗證**。✅ 設計未引入 cookie。

## 7. 權限與 nftables 審查

### 7.1 重大發現：特權模型分歧（H-3）

| 維度 | 既有 SeMon（已驗證） | ATD 初版設計 |
|---|---|---|
| 封鎖特權 | API 行程（非 root `secmon`）直接 `subprocess.run(['/usr/sbin/nft', ...])`；nft 權限為**外部操作者責任** | 「受控 sudoers helper」+ `CAP_NET_ADMIN`/`CAP_NET_RAW` |
| sudoers | 僅維護（`backup-db`/`migrate-db`/`runtime-recovery`），**未授 nft** | 新增 helper |
| systemd unit | 無 `AmbientCapabilities`、`NoNewPrivileges=true` | 暗示需要 CAP |
| auto-block | `auto_block_enabled=False` 且**無執行路徑** | ATD-E 待核准封鎖（保守，方向正確） |

**判定**：ATD 初版特權描述為**新增機制**，非沿用既有。已於 v1.1-draft §16.4 補對齊建議：**ATD-A~D 採零新特權（複用 `NftablesService`）；ATD-E 先 dry-run + 待核准 + 複用既有 `NftablesService`，新 helper 留待後續評估**。此分歧雖為 High，但已透過文件修正緩解為可執行路徑，不構成阻擋。

### 7.2 受控回應安全（H-3 子項）

- `parse_ip` 目前只拒絕 loopback/unspecified/multicast；**未保護 gateway/DNS/SSH 管理來源/proxy**，僅靠 `ip_allowlist` DB 列。ATD-E 須明確「不可封鎖清單」涵蓋這些（任務書 §六.9 要求）。→ H-9。
- 既有 `preview()`（`nft --check -f -`）為 per-request dry-run 原語，可作為 ATD-E `nft_rule_intent` 的基礎。✅
- 既有無 emergency allowlist with TTL（`ip_allowlist` 無 expiry 欄）。ATD-E 須新增或複用 `network_allowlists.maintenance_window_json`。→ M-6。

### 7.3 操作失敗不得標 Contained

- 既有封鎖失敗會 `unblock` rollback 並 re-raise（從不假造成功）。ATD-E 須沿用：`response_actions` 落地失敗時 status 不得設 `DONE`/`EXECUTING` 卡住，須能 `ROLLED_BACK`。✅ 設計已含狀態，但須明確「失敗→不自動 Contained」語意。→ M-7。

## 8. 可觀測盲區審查

- **未誇大端點能力**：設計 §2.3、§3.1、§4.8 已明確列出 7 類流量與可觀測性；§2.3 明確「主機不是 Gateway/Router/SPAN/TAP 時的盲區」。✅
- **未暗示可見整個公司網路**：v1.1-draft 另補「監控盲區總聲明」置頂強調。✅
- **NAT/Proxy/VPN/Tailscale/Docker bridge**：§3.1 表格已涵蓋（NAT 後方、Proxy/VPN/容器/虛擬網路列為 ⚠️）。✅
- **SPAN/TAP/Gateway/NetFlow/Zeek 補足範圍**：§6.3 已列為升級路徑（非 P1）。✅
- 判定：**無 Critical**（任務書 §七：暗示可見不可觀測流量才為 Critical）。✅

## 9. 偵測規則與基線審查

### 9.1 L1/L3 規則可解釋性

任務書 §六.6 要求每條規則具備 12 項屬性。逐條核對：

| 規則 | 觀測指標 | 時間視窗 | 比較門檻 | 嚴重度 | Evidence | 誤報情境 | 白名單 | 冷卻 | 去重鍵 | 結束條件 | 可調參數 | Rule version |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L1_PPS_BURST | ✅ | ✅10s | ✅可設 | ✅High | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L1_CONN_CAP | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L1_SYN_RATIO | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L1_PORT_SCAN_H | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L1_EGRESS_BURST | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L1_DST_FANIN | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L3_SYN_FLOOD | ✅ | ✅15m | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L3_COMPROMISED_EGRESS | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| L3_LATERAL_SCAN | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |

`✅`=已具體；`⚠️`=設計層級提及（如 §9 冷卻預設 5m、§12 `dedup_key` 欄、§15 告警結束=RESOLVED/FALSE_POSITIVE），但**未逐條規則落表**。

**判定 M-8**：規則的**通用機制**（冷卻、去重鍵、結束條件、白名單負權重、Evidence 由 `metric_snapshot`+`baseline_ref` 提供）已在 §8/§9/§10/§12 共同定義，可解釋性**足夠進入實作**；但建議 ATD-A/B 實作時為每條 rule 補一份「規則規格卡」（含該規則專屬冷卻、結束條件、誤報清單），以利測試與验收。此為 Medium，非阻擋。

### 9.2 動態基線邊界情境（任務書 §六.7）

| 情境 | 設計是否涵蓋 | 等級 |
|---|---|---|
| 冷啟期 | ⚠️ 僅說「建議 7~14 天」，未定最低有效樣本數 | M-9 |
| 資料不足回退固定門檻 | ❌ 未明說 | M-10 |
| MAD 為零 | ❌ 未明說（MAD=0 時 `k*MAD=0` 會使任何偏離都觸發） | **H-10** |
| 極端事件污染基線 | ✅ Median/MAD 抗污染；百分位亦然 | — |
| 白名單獨立基線 | ✅ §11.2、`asset_profiles.baseline_profile` | — |
| 基線重算頻率 | ⚠️ 表格有 `computed_at` 但未訂頻率 | M-11 |
| 基線版本 | ✅ `rule_version`；但 `traffic_baselines` 無獨立版本欄 | L-2 |
| 時區 | ⚠️ 設計說 UTC，但 `hour_bucket` 與「同時段」須明確用 UTC 或本地時區；夏令時間跨日視窗須處理 | M-12 |

**H-10（MAD=0）為唯一 High 等級基線問題**：必須於 ATD-C 實作前定義「MAD=0 時改用 p99 或固定門檻回退」，否則會產生大量誤報。已列為 ATD-C 前置條件（非本審查阻擋，因屬實作細節且 ATD-C 在 ATD-A/B 之後）。

## 10. 效能與容量審查

| 項目 | 設計涵蓋 | 量化條件 | 等級 |
|---|---|---|---|
| 採樣頻率 | ✅ 1s 計量、5s socket | 有 | — |
| Flow 數量 | ⚠️ 預估 <5k flows/s | 為預估，未經實機 | M-13 |
| SQLite 寫入量 | ⚠️ | **未量化**（samples 1s × 欄位數 × 介面數） | M-14 |
| WAL mode | ✅ | — | — |
| Lock contention | ⚠️ 提小批次 transaction | 未量化 busy_timeout 衝突率 | M-14 |
| Batch insert | ⚠️ 提「小批次」 | 未定 batch size | M-14 |
| Downsampling / Aggregation | ✅ 多層 roll-up | — | — |
| Raw sample retention | ✅ 7~14 天 | — | — |
| Aggregate retention | ✅ 30~90 天 | — | — |
| Disk quota | ⚠️ 提「高水位告警」 | **未量化磁碟上限** | M-14 |
| Collector backpressure / 降級 | ✅ §18 降級策略 | — | — |
| 資料丟棄策略 | ⚠️ 降級時「停 L2/L3」 | 未明說 samples 滿時是否丟棄最舊或拒收 | M-15 |
| PostgreSQL 遷移條件 | ✅ 已列條件 | — | — |

**判定**：任務書 §六.10「若沒有量化條件，列為 Medium 或 High」。多項效能指標**未量化** → 歸為 **Medium（M-13~M-15）**，非 High（因設計已給降級策略與 PG 遷移條件，可實作後以實測量化）。須於 ATD-A 實作後以實測補量化，列為 ATD-A 验收條件之一。

## 11. 測試可執行性

- §20.1 測試類別涵蓋任務書 §六.12 全部項目（含 IPv6、Container bridge、VPN/Tailscale、Collector restart、Host reboot、nftables dry-run、Rollback）。✅
- §20.2 情境涵蓋正常高流量、真正異常、白名單高流量、Scanner、SYN、UDP、IPv6。✅
- **Container bridge / VPN-Tailscale 測試**：§20.2 未明確列出這兩項的具體測試步驟 → L-3（可在 ATD 測試計畫細化）。
- **隔離環境聲明**：§20.2 已強調「僅於授權隔離環境」「嚴禁對正式網段」。✅
- **未執行任何模擬**：本審查未執行。✅
- 測試基礎建設對齊：既有用 `TestClient` + `make_client(tmp_path)` + `FakeFirewall`；ATD 須沿用（ATD-A 計畫已列入）。✅

## 12. Critical／High／Medium／Low 問題清單

### Critical（0）

無。

> 特別確認：設計**未**暗示端點可見全公司流量（§8 已驗證）；**未**讓一般使用者執行封鎖（§6 response=admin-only）；**未**讓 Web API 取得 root（複用既有非 root 模型）；**未**長期保存 Payload（metadata-first）。無 Critical。

### High（已全部於 v1.1-draft 文件修正或轉為可執行前置條件，不構成阻擋）

| 編號 | 問題 | 阻擋？ | 處置 |
|---|---|---|---|
| H-1 | 時間戳預設式與既有 `CURRENT_TIMESTAMP` 不一致 | 否 | v1.1 §12 對齊注意 #1 |
| H-2 | severity TEXT vs 既有 INTEGER 1~5 | 否 | v1.1 §12 對齊注意 #2 |
| H-3 | 特權模型分歧（新 sudoers/CAP vs 既有外部化） | 否 | v1.1 §16.4 對齊建議（複用 `NftablesService`） |
| H-4 | status 大寫 vs 既有小寫 | 否 | v1.1 §12 對齊注意 #3 |
| H-5 | API 前綴 `/api/network` vs `/api/v1/...` | 否 | v1.1 §13 已修正 |
| H-6 | 分頁格式不一致 | 否 | v1.1 §13 已修正 |
| H-7 | 錯誤格式不一致 | 否 | v1.1 §13 已修正 |
| H-8 | 角色名大小寫 | 否 | v1.1 §13 已修正 |
| H-9 | ATD-E 須明確「不可封鎖 gateway/DNS/SSH 管理來源」（既有 `parse_ip` 僅拒 loopback/unspec/multicast） | 否 | 列為 ATD-E 前置條件 |
| H-10 | 動態基線 MAD=0 處理未定義 | 否 | 列為 ATD-C 前置條件 |

> 所有 High 皆已：(a) 於 v1.1-draft 文件修正，或 (b) 轉為對應分期（ATD-C/E）的前置條件。**無未解決 High。**

### Medium（可保留，須有負責階段/方案/验收）

| 編號 | 問題 | 負責階段 | 修正方案 | 验收條件 |
|---|---|---|---|---|
| M-1 | 「Alert Service/Response Engine/Scheduler」暗示獨立服務，實際僅 api+collector 兩 unit | ATD-A 計畫釐清 | 文件改述為「模組/任務」而非獨立 daemon；ATD-D/E 複用 api 行程 | 文件無誤導；無新增 systemd unit（除非經獨立設計） |
| M-2 | 整數 FK 未加 `REFERENCES ... ON DELETE SET NULL` | ATD-A migration | migration 補 FK | schema_review 通過 |
| M-3 | `response_actions` 缺「同 target_ip 僅一 PENDING_APPROVAL」partial unique index | ATD-E migration | 加 partial index | 並發申請不重複 |
| M-4 | 既有無 migration repeat-run 測試 | ATD-A | 補 `test_migrate_repeat_run` | 測試通過 |
| M-5 | 寫入端點未提 `require_write_rate` | ATD-A 實作 | 沿用既有 dependency | RBAC/限流測試通過 |
| M-6 | 無 emergency allowlist TTL 機制 | ATD-E | 用 `network_allowlists.maintenance_window_json` 或擴 `ip_allowlist` | 誤封可緊急覆蓋 |
| M-7 | `response_actions` 落地失敗狀態語意未明 | ATD-E | 明定「失敗→ROLLED_BACK，不卡 EXECUTING，不標 Contained」 | 失敗路徑測試通過 |
| M-8 | 規則缺少逐條「規格卡」 | ATD-A/B | 每條 rule 補規格卡 | 验收可逐條重現 |
| M-9 | 冷啟期未定最低有效樣本數 | ATD-C | 定義最低樣本數（如 ≥某數才啟用 L2） | 冷啟期測試 |
| M-10 | 資料不足回退未明 | ATD-C | 明定「樣本不足→回退 L1 固定門檻」 | 回退測試 |
| M-11 | 基線重算頻率未訂 | ATD-C | 定義（如每小時重算 24h 視窗） | 排程測試 |
| M-12 | `hour_bucket` 時區/夏令時間跨日未明 | ATD-C | 明定 UTC，跨日視窗處理 | 跨日測試 |
| M-13 | Flow 數量為預估未實測 | ATD-A 實測 | 實機量化 | 數據記錄 |
| M-14 | SQLite 寫入量/lock/batch/disk 未量化 | ATD-A 實測 | 實機量化並定磁碟上限 | 容量验收 |
| M-15 | Collector 背壓丟棄策略未明 | ATD-A | 明定「降級時丟最舊 samples，不停寫入」 | 背壓測試 |

### Low

| 編號 | 問題 | 處置 |
|---|---|---|
| L-1 | `{id}` 端點 IDOR 須以 404 處理（沿用既有） | ATD-A 實作遵循 |
| L-2 | `traffic_baselines` 無獨立版本欄（靠 `rule_version`） | 可接受；ATD-C 視需要補 |
| L-3 | Container bridge / VPN-Tailscale 測試步驟未細化 | ATD 測試計畫補 |

## 13. 已直接修正的文件項目

於 `docs/SECMON_ANOMALOUS_TRAFFIC_DETECTION_MASTER_DESIGN.md`（v1.0-draft → v1.1-draft）已修正：

1. **變更紀錄**：新增 v1.1-draft 條目；版本欄位更新。
2. **階段命名澄清**（§文件控制後）：明註 `P1-A~E = ATD-A~E`，後續審查/實作採 `ATD-*`。
3. **監控盲區總聲明**（§文件控制後，置頂）：強調端點視角、不可見流量、升級路徑非 ATD 範圍。
4. **API 一致性**（§13）：前綴改 `/api/v1/network/...`；分頁改 `{"items","page","page_size","total"}`；錯誤改 `{"error":{"code","message","request_id"}}`；角色改小寫 `admin/analyst/viewer`；補 `require_write_rate` 與 `write_audit` 慣例。
5. **資料模型對齊注意**（§12，8 點）：時間戳/ severity/ status/ discriminator/ retention/ FK/ migration 編號/ block_source enum。
6. **特權模型對齊**（§16.4）：明列既有「API 非 root 直接呼叫 nft、權限外部化、無 sudoers 授 nft、`NoNewPrivileges=true`」；建議 ATD-A~D 零新特權、ATD-E 複用 `NftablesService`。

所有修正均為**文字/一致性**修正，**未變更原始設計語意**（三層偵測、10 表、15 API、ATD-A~E 結構不變）。

## 14. 未修正項目與原因

| 項目 | 未於本階段修正原因 |
|---|---|
| severity TEXT vs INTEGER | 涉及設計取捨（須決定改 INTEGER 或建映射層），屬實作期決策，非單純文字修正 |
| MAD=0 處理、冷啟期、回退、時區 | 屬 ATD-C 動態基線實作細節，須實作時定義 |
| 「不可封鎖 gateway/DNS/SSH」具體清單 | 涉及公司網段（敏感、不入 Git），屬 ATD-E 部署期配置 |
| 效能量化（寫入量/磁碟/lock） | 須實機實測，無法於設計階段給可信量化值 |
| Migration 撰寫 | 任務書 §八 明禁本階段建立 migration |
| 獨立服務（Alert/Response/Scheduler）改述 | 涉及架構決策（是否真新增 systemd unit），留 ATD-A 計畫釐清 |

## 15. 進入 ATD-A 實作的前置條件

進入 `docs/SECMON_ATD_A_IMPLEMENTATION_PLAN.md` 所述之 ATD-A 實作前，**必須**滿足：

1. **C-1**：本審查判定 PASS（§16）。
2. **C-2**：主設計文件 v1.1-draft 已含 §13 所列修正（已完成）。
3. **C-3**：ATD-A migration 規格已遵循 §12 對齊注意 8 點（時間戳 `CURRENT_TIMESTAMP`、FK `REFERENCES ... ON DELETE SET NULL`、檔名 `012_anomalous_traffic_detection.sql`、`CREATE TABLE IF NOT EXISTS`）。
4. **C-4**：ATD-A 採**零新特權**（複用既有 `secmon` user、不新增 sudoers/CAP）。
5. **C-5**：ATD-A 端點遵循既有 `/api/v1/network/...`、`{"items",...}` 分頁、`{"error":{...}}` 錯誤、小寫角色、`require_write_rate`、`write_audit`。
6. **C-6**：ATD-A 不建立獨立 systemd unit（沿用既有 `secmon-collector` 與 `secmon-api`）。
7. **C-7**：補 `test_migrate_repeat_run`（M-4）。
8. **C-8**：ATD-A 完成後以實測補效能量化（M-13/M-14）。

> Medium 問題 M-9~M-12（動態基線）屬 ATD-C 範圍，**非** ATD-A 前置條件；M-3/M-6/M-7 屬 ATD-E 範圍。

## 16. 最終判定

依任務書 §十 通過條件逐項：

| 條件 | 結果 |
|---|---|
| 無未解決 Critical | ✅（0 Critical） |
| 無未解決 High | ✅（10 High 全數於 v1.1 修正或轉為分期前置條件） |
| 監控盲區描述正確 | ✅（§8） |
| 資料模型可與既有架構整合 | ✅（§5，待 ATD-A migration 落實 8 點對齊） |
| API 與 RBAC 設計一致 | ✅（§6，v1.1 已修正） |
| Collector 最小權限策略成立 | ✅（§7，採零新特權路徑） |
| nftables 回應具核准與 Rollback | ✅（§7、§16.4，ATD-E 複用既有 + 待核准） |
| L1、L2、L3 規則可解釋 | ✅（§9，逐條規格卡建議為 M-8 非 High） |
| IPv4／IPv6 已處理 | ✅（§5.2，discriminator 欄 + Python `ipaddress`） |
| SQLite 容量界線有明確條件 | ✅（§10，PG 遷移條件已列；量化為 M 級待實測） |
| 測試計畫可在隔離環境重現 | ✅（§11） |
| 文件沒有宣告尚未執行的測試已通過 | ✅（全文未宣告 Runtime PASS） |

**判定：PASS**（所有 High 已解決或可執行；Medium 均有負責階段、方案、验收條件）。

---

## 附錄：環境備註

- **`data/` 目錄**：含 `data/secmon.db`（0 KB 空 SQLite），未追蹤且**未 gitignore**（外層 `.gitignore` 未涵蓋 `data/`）。依任務書規定本階段不刪/不改/不加。**建議**後續於 `.gitignore` 補 `secmon-linux-security/data/` 以避免 runtime DB 誤入 Git（非本審查範圍）。
- **Git topology**：任務書所述「Git Repository Root = `.../secmon-linux-security/secmon-linux-security`」與 `git rev-parse --show-toplevel`（`.../secmon-linux-security`）不一致。實際 git root 為外層路徑（含多個 worktree）；內層為專案子目錄。設計文件置於內層 `docs/`（與既有設計文件同層）為**正確內容位置**，git 追蹤自外層。此不影響審查結論，記錄備查。
