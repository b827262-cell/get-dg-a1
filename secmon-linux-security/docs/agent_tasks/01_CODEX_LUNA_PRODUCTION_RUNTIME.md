# SecMon P1 正式環境 Runtime Gate — Agent 1 / Codex Luna

## 角色與邊界

你是 SecMon P1 正式主機部署與 Runtime Gate 實作者。

- Required model: `gpt-5.6-luna`
- Required reasoning: `xhigh`
- 你不是最終驗收者，不得自行宣告 P1 Release Gate PASS，也不得關閉 Issue #2。
- 僅在目前 SecMon 工作區及本任務明確指定的正式 SecMon 路徑內工作。
- 所有既有 working-tree 變更均視為使用者資產；不得覆寫、清除、重設或廣泛加入暫存區。
- 不得自行啟動 Agent 2。

## 外部副作用政策

Runner 會匯出以下三個布林值，且預設都為 `false`：

- `SECMON_ALLOW_GIT_PUSH`
- `SECMON_ALLOW_GITHUB_ISSUE_UPDATE`
- `SECMON_ALLOW_HERMES_NOTIFY`

只有值精確等於 `true` 才代表該項外部副作用已獲本次執行授權。值為
`false`、缺失或無法驗證時一律 fail closed。本 Agent 不執行 Git push 或
GitHub Issue 更新；Hermes 只有在 `SECMON_ALLOW_HERMES_NOTIFY=true` 時才可執行，
否則在報告中記錄 `SKIPPED_BY_POLICY`。不得用任務文件中的範例命令推定授權。

## 共同基準

- Branch: `main`
- Baseline HEAD: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- Remote: `origin/main`
- 基準狀態: `0 ahead / 0 behind`
- 正式報告: `docs/P1_AGY_PRODUCTION_RUNTIME_VERIFICATION.md`
- 複驗紀錄: `docs/P1_AGY_REVERIFICATION_REPORT.md`
- 已知 Static Gate: PASS（pytest 115/115；Blocker 0；High 0）
- 尚未通過: Real Telegram Smoke、Production systemd Runtime、3 × 30 秒 E2E Gate
- 目前正式判定: P1 NOT READY、Release Gate NOT PASSED、Issue #2 OPEN

## 必要 Preflight

Runner 若提供 `SECMON_PREFLIGHT_RESULT_FILE`，只可讀取該去敏檔案；不得讀取其他 runner 私密 log。你仍須獨立核對必要條件。

開始任何部署前，必須確認：

1. 位於正確的 SecMon Git 工作區。
2. `git rev-parse HEAD` 是 `080e3fe`，或其後已完整說明且只屬 P1 Runtime 修正的提交。
3. 已記錄本機與 `origin/main` 的差異。
4. `PREFLIGHT_RESULT: PASS`。
5. `/etc/secmon/secmon.env` 已由人類安全建立且非空。
6. Runner 的去敏 Preflight 證據包含
   `P1_HUMAN_START_AUTHORIZATION=GRANTED`；這必須來自技術 Preflight 通過後、
   P1 專用且完全一致的人工 `/start` 輸入。
7. Telegram Chat ID 是 `8350114645`。
8. Bot Token numeric prefix 是 `8860122652`。
9. 輸入 P1 專用 `/start` 前，操作員已人工確認 Telegram 前置條件以及明確
   授權、可用且低風險的外部 SSH 測試端。
10. `sudo` 可在可信終端正常使用；Agent 僅可使用 `sudo -n`，不得接觸密碼。

任一必要條件不成立時，立即停止部署／Runtime 測試並建立去敏的 `BLOCKED`
報告。只有 `SECMON_ALLOW_HERMES_NOTIFY=true` 才執行本階段 Hermes 阻塞通知；
否則記錄 `SKIPPED_BY_POLICY`。最後以 `STAGE_RESULT: BLOCKED` 封存報告。

## 秘密與安全規則

絕對禁止：

- `cat /etc/secmon/secmon.env`
- `printenv`、`env`、`set`、shell tracing
- `echo $SECMON_TELEGRAM_BOT_TOKEN` 或任何等價輸出
- 在命令列參數傳遞 Bot Token
- 將 Token 寫入 Markdown、Git、journal、shell history、process args 或終端回報
- `git add .`、`git add -A`、broad staging、history rewrite
- 提交 `.env`、DB、WAL/SHM、Cursor、journal、dump、cache 或 runtime log
- 掃描非授權主機、大量密碼嘗試、手工插入 SQLite 或 synthetic log 冒充正式 E2E

只允許以不輸出值的方式檢查秘密，例如：

- `sudo -n test -s /etc/secmon/secmon.env`
- `sudo -n grep -q '指定條件' /etc/secmon/secmon.env`
- `sudo -n stat /etc/secmon/secmon.env`

任何輸出與報告均不得包含完整 Token。`SECMON_AUTO_BLOCK_ENABLED=false` 必須全程維持關閉。

## 工作一：確認 Static Gate

在正式部署前，至少重跑並記錄指令、時間與 exit code：

```bash
python -m compileall -q backend database tests scripts
ruff check backend database tests scripts
mypy backend database
pytest
make check
```

要求：

- pytest 為 115/115 或更多，且全部 PASS。
- Blocker = 0。
- High = 0。
- 結果若與正式報告不一致，先調查 code drift；不得直接進入部署。

## 工作二：正式部署

部署目標：

- 程式: `/opt/secmon`
- 設定: `/etc/secmon/secmon.env`
- DB: `/var/lib/secmon/secmon.db`
- Cursor: `/var/lib/secmon/ssh.cursor`
- 日誌目錄: `/var/log/secmon`
- Service: `secmon-collector.service`
- Runtime user: `secmon`

要求：

1. 建立或確認 `secmon` system user。
2. 正式服務不得以 root 執行。
3. `/opt/secmon` 不得包含 `.git`、`.env`、舊 DB、Cursor、WAL/SHM、cache 或其他 runtime artifact。
4. 建立 `.venv` 並安裝正式依賴。
5. 安裝 `secmon-collector.service`。
6. 確認 unit 實際生效內容包含：
   - `EnvironmentFile=/etc/secmon/secmon.env`
   - `Restart=on-failure`
   - `RestartSec=5s`
   - `NoNewPrivileges=true`
   - `ProtectSystem=strict`
   - `ProtectHome=true`
   - `PrivateTmp=true`
7. 只給 `secmon` 讀取 SSH authentication log 的最小必要權限。
8. `SECMON_AUTO_BLOCK_ENABLED=false` 維持關閉。

若正式主機沒有 collector 可讀的真實 SSH authentication log，不得以 journald 摘錄、synthetic log 或測試 fixture 冒充 Gate 證據；必須修正正式日誌來源或回報 BLOCKED。

## 工作三：Real Telegram Smoke

透過正式 systemd 環境，或另一個不在 process args／stdout 暴露 Token 的安全方式，執行正式 notifier 測試，例如：

```bash
python -m backend.notifiers.telegram --test
```

必須記錄：

- 測試時間與 hostname
- Exit code
- Telegram API transport 結果
- stdout／stderr 是否安全
- journal 是否出現 Token
- 人類是否明確確認實際收到本次訊息

只有 HTTP/API 成功但沒有人類收訊確認時，不得將完整 Telegram Gate 判定為 PASS，也不得輸出 `READY_FOR_GLM_REVIEW`。

## 工作四：Production systemd Runtime

執行並驗證：

```bash
sudo -n systemctl daemon-reload
sudo -n systemctl enable secmon-collector.service
sudo -n systemctl restart secmon-collector.service
sudo -n systemctl is-enabled secmon-collector.service
sudo -n systemctl is-active secmon-collector.service
sudo -n systemctl status secmon-collector.service --no-pager
```

至少確認：

- 非 root 執行
- 沒有 restart loop
- 能讀取正式 authentication log
- 能寫入正式 DB、WAL/SHM 與 Cursor
- SQLite WAL 正常
- SIGTERM 能乾淨停止
- Restart 後從既有 Cursor 繼續
- 所有 runtime 路徑均在 Git 工作區外

## 工作五：第一組 3 × 30 秒 E2E Gate

只能使用已授權的外部 SSH 測試端。每輪必須有獨立證據：

1. 記錄開始時間。
2. 記錄開始前的 `attack_events` count、`attackers` count、目標 IP `total_events`、`log_sources.events_today`、`log_sources.last_event_at`、Cursor position、service state。
3. 從外部測試端對 TUFA16 做極少量失敗 SSH 登入。
4. 最多等待 30 秒。
5. 確認：
   - `attack_events` 新增唯一事件
   - `src_ip`、username、`attack_type` 正確
   - `attackers` 彙總增加
   - `log_sources` 更新
   - Cursor 前進
   - Collector 持續 active
   - Telegram 告警送出
6. 驗證重播或重啟不會重複計數。

不得掃描其他主機、對未授權 IP 測試、大量嘗試密碼、手工寫 DB，或用 synthetic log／fixture 冒充正式 auth log Gate。

## 報告與 Hermes 通知

報告寫入：

`docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md`

報告須包含：tested HEAD、remote 差異、Preflight、Static Gate、部署內容、實際生效 unit、秘密檢查、Telegram transport 與人類收訊、systemd runtime、三輪 E2E、replay、發現分級與精確下一步。不得寫入秘密。

先完成報告本文並決定結果。僅當 `SECMON_ALLOW_HERMES_NOTIFY=true` 時執行
Hermes 並記錄 exit code；否則記錄 `Hermes: SKIPPED_BY_POLICY`。完成後才寫
唯一的最後一行。

成功通知：

```bash
hermes send --to telegram:8350114645 "✅ TUFA16 SecMon Agent 1 完成
Result: READY_FOR_GLM_REVIEW
Host: <hostname>
Git HEAD: <short-head>
Report: docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md
Next: GLM-5.2 獨立審查"
```

阻塞通知：

```bash
hermes send --to telegram:8350114645 "⚠️ TUFA16 SecMon Agent 1 阻塞
Result: BLOCKED
Host: <hostname>
Report: docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md
Action: 請查看 Runtime Blocker"
```

以上通知命令只是已授權時的格式範例，不構成授權。Hermes 失敗不得改變
Runtime Gate 結果，但必須記錄 exit code；不得在通知中包含 Token、環境變數
或其他秘密。

只有所有必要證據都明確通過時，報告最後一行寫：

`STAGE_RESULT: READY_FOR_GLM_REVIEW`

否則最後一行寫：

`STAGE_RESULT: BLOCKED`

最後一行只能是以上兩者之一。完成後停止，不得啟動 Agent 2。
