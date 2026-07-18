# SecMon P1 正式環境 Runtime Gate — Agent 1 / Codex Luna

## 角色與邊界

你是 SecMon P1 正式主機 Runtime Gate 證據驗證者。外層 Runner 才是本階段
唯一的 privileged controller；你不得自行部署、修改 systemd 或執行任何
需要提升權限的命令。

- Required model: `gpt-5.6-luna`
- Required reasoning: `xhigh`
- 你不是最終驗收者，不得自行宣告 P1 Release Gate PASS，也不得關閉 Issue #2。
- 僅在目前 SecMon 工作區及本任務明確指定的正式 SecMon 路徑內工作。
- 所有既有 working-tree 變更均視為使用者資產；不得覆寫、清除、重設或廣泛加入暫存區。
- 不得自行啟動 Agent 2。
- 絕對不得執行 `sudo`、`sudo -S`、`sudo -v`、`sudoedit`、root shell 或任何
  其他 privilege-escalation 命令；不得自行驗證或讀取正式 environment file。
- 不得執行需要 root 權限的 `systemctl`、部署 helper、`install`、`chown` 或
  `chmod`。這些操作若獲准，只能由外層 Runner 在人工 `/start` 後以固定命令完成。

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
- Approved baseline: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- Explicitly accepted current HEAD reference: `f39df7b3b7bab2af2649834ba8194950cef08358`
- `080e3fe..HEAD` 只能包含已核准的 Runner／文件／framework 路徑；
  `.gitignore`、`run_secmon_*_multi_agent_gate.sh`、`scripts/deploy_helper.sh`
  與 `docs/**` 屬於核准範圍，不得誤判為 product-code drift。
- Remote: `origin/main`
- 基準狀態: `0 ahead / 0 behind`
- 正式報告: `docs/P1_AGY_PRODUCTION_RUNTIME_VERIFICATION.md`
- 複驗紀錄: `docs/P1_AGY_REVERIFICATION_REPORT.md`
- 已知 Static Gate: PASS（pytest 115/115；Blocker 0；High 0）
- 尚未通過: Real Telegram Smoke、Production systemd Runtime、3 × 30 秒 E2E Gate
- 目前正式判定: P1 NOT READY、Release Gate NOT PASSED、Issue #2 OPEN

## 必要 Preflight

Runner 會提供兩個去敏檔案：

- `SECMON_PREFLIGHT_RESULT_FILE`
- `SECMON_PRIVILEGED_EVIDENCE_FILE`

只可唯讀核對這兩個檔案；不得讀取其他 Runner 私密 log，也不得修改、刪除、
覆寫、重新產生或替換它們。`SECMON_AGENT_SUDO_REQUIRED` 必須是 `NO`。

開始任何部署前，必須確認：

1. 位於正確的 SecMon Git 工作區。
2. `git rev-parse HEAD` 是明確接受的 `f39df7b`，或其後僅包含
   `080e3fe..HEAD` allowlist 內的 Runner／文件／framework 提交。
3. 已記錄本機與 `origin/main` 的差異。
4. `PREFLIGHT_RESULT: PASS`。
5. `SECMON_PREFLIGHT_RESULT_FILE` 最後包含 `PREFLIGHT_RESULT: PASS`，且
   `STATIC_GATE_RESULT: PASS`。
6. `SECMON_PRIVILEGED_EVIDENCE_FILE` 存在、權限為 `0600`，且只包含去敏的
   PASS／FAIL／NOT_RUN 結果；不可輸出任何環境變數值。
7. Privileged evidence 包含 `MANUAL_P1_START: PASS`、
   `AGENT_SUDO_REQUIRED: NO` 與 `CONTROLLER_GATE_RESULT: PASS`。
8. Runner 的去敏 Preflight 證據包含
   `P1_HUMAN_START_AUTHORIZATION=GRANTED`；這必須來自技術 Preflight 通過後、
   P1 專用且完全一致的人工 `/start` 輸入。
9. Telegram 前置條件及明確授權、可用且低風險的外部 SSH 測試端已由操作員
   在輸入 P1 `/start` 前人工確認；只接受 controller 的布林／metadata 證據。

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

Agent 1 不執行任何正式 environment file 檢查。只可用唯讀方式驗證
`SECMON_PRIVILEGED_EVIDENCE_FILE` 的權限與固定結果標記；完整環境檔內容、
匹配值、Token、Chat ID 與 sudo 密碼均不可讀取或輸出。

任何輸出與報告均不得包含完整 Token。`SECMON_AUTO_BLOCK_ENABLED=false` 必須全程維持關閉。

## 工作一：確認 Static Gate

外層 Runner 已在技術 Preflight 執行並記錄 syntax／Static Gate。Agent 1 必須
先唯讀核對 controller evidence；如需重跑非特權檢查，固定使用專案 venv：

```bash
PATH="$PWD/.venv/bin:$PATH" python -m compileall -q backend database tests scripts
PATH="$PWD/.venv/bin:$PATH" ruff check backend database tests scripts
PATH="$PWD/.venv/bin:$PATH" mypy backend database
PATH="$PWD/.venv/bin:$PATH" pytest
PATH="$PWD/.venv/bin:$PATH" make check
```

要求：

- pytest 為 115/115 或更多，且全部 PASS。
- Blocker = 0。
- High = 0。
- 結果若與正式報告不一致，先調查 code drift；只將 allowlist 外的
  product-code 變更視為 code drift，不得將 docs/framework commit 誤判為 drift。

## 工作二：驗證 controller 產生的正式部署證據

Agent 1 不執行部署。外層 Runner 只在可信 TTY 收到人工 P1 `/start` 後，使用
固定且精確的 controller 命令完成必要的 sudo／systemd 操作，並將去敏結果寫入
`SECMON_PRIVILEGED_EVIDENCE_FILE`（權限 `0600`）。Agent 1 只能唯讀驗證該檔案，
不得自行重跑任何 privileged command。

部署目標：

- 程式: `/opt/secmon`
- 設定: `/etc/secmon/secmon.env`
- DB: `/var/lib/secmon/secmon.db`
- Cursor: `/var/lib/secmon/ssh.cursor`
- 日誌目錄: `/var/log/secmon`
- Service: `secmon-collector.service`
- Runtime user: `secmon`

要求：

1. 只接受 controller 對正式 environment file 的非內容化存在、格式、owner/mode
   與 `SECMON_AUTO_BLOCK_ENABLED=false` 結果。
2. 只接受 controller 對以下固定 systemd 操作的去敏結果：
   `daemon-reload`、`enable secmon-collector.service`、`restart
   secmon-collector.service`、`is-enabled`、`is-active`、`status --no-pager`。
3. 以非特權方式確認正式服務不得以 root 執行。
4. `/opt/secmon` 不得包含 `.git`、`.env`、舊 DB、Cursor、WAL/SHM、cache 或其他 runtime artifact。
5. 確認 unit 實際生效內容包含：
   - `EnvironmentFile=/etc/secmon/secmon.env`
   - `Restart=on-failure`
   - `RestartSec=5s`
   - `NoNewPrivileges=true`
   - `ProtectSystem=strict`
   - `ProtectHome=true`
   - `PrivateTmp=true`
6. 只給 `secmon` 讀取 SSH authentication log 的最小必要權限。
7. `SECMON_AUTO_BLOCK_ENABLED=false` 維持關閉。

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

不得執行 `sudo` 或直接呼叫需要 root 權限的 `systemctl`。唯讀核對外層
controller evidence 後，以非特權觀察與正式服務證據完成本節；若 controller
evidence 缺少任一固定操作，必須回報 `BLOCKED`，不得自行補做。

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
