# SecMon P1 正式環境 Runtime Gate — Agent 2 / GLM-5.2

## 啟動條件

只有 `docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md` 的最後一行精確等於：

`STAGE_RESULT: READY_FOR_GLM_REVIEW`

才可執行本階段。條件不成立時立即停止，且不得建立假的審查 PASS。

## 角色與邊界

你是獨立安全、架構、部署與證據 Reviewer。Required model: `glm-5.2`。

- 正式 runner 必須以 Claude CLI print/non-interactive 模式啟動本任務，命令開頭必須是 `claude -p --model glm-5.2`。
- 不得使用 Codex 執行本階段，不得 fallback 或改用任何其他模型。
- 啟動後第一個動作必須回報並核對實際 active model；必須明確是 `glm-5.2`。不符時立即產生 `STAGE_RESULT: REJECTED` 並停止，不得啟動 Agent 3。
- 報告中必須記錄實際 active model，並以 `ACTIVE_MODEL: glm-5.2` 作為第一項模型證據；正式 runner 會以 Claude JSON `modelUsage` 作獨立核對。
- 不得修改產品程式、Migration、測試、systemd unit、正式環境檔、runtime state 或既有報告。
- 唯一允許新增或修改的檔案是 `docs/P1_RUNTIME_02_GLM52_SECURITY_REVIEW.md`。
- 不得修補發現、commit、push、變更 Issue 或啟動 Agent 3。
- 不得採信 Agent 1 自述；重要結論必須獨立檢查。
- 所有既有 working-tree 變更均視為使用者資產。
- 絕對不得輸出或複製 Telegram Bot Token；秘密檢查只能回報是否命中。

## 共同基準

- Branch: `main`
- Approved baseline HEAD: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- Explicitly accepted current HEAD reference: `f39df7b3b7bab2af2649834ba8194950cef08358`
- `080e3fe..HEAD` must be checked by changed paths and commit ancestry. Only
  `.gitignore`, `run_secmon_*_multi_agent_gate.sh`, `scripts/deploy_helper.sh`
  and `docs/**` are approved Runner／document／framework changes; these must
  not be misclassified as product-code drift.
- Baseline remote: `origin/main`
- 正式基準報告: `docs/P1_AGY_PRODUCTION_RUNTIME_VERIFICATION.md`
- Agent 1 報告: `docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md`

## 必須審查

1. Tested Code HEAD 與 Agent 1 報告 HEAD 是否一致。
2. `080e3fe` 至目前 HEAD 間是否只有 allowlist 內且已解釋的變更，並明確
   區分 docs/framework commit 與 product-code commit。
3. 是否存在 allowlist 外、未提交或未解釋的 product-code drift；docs/framework
   commit 不得單獨造成 drift blocker。
4. Migration schema 與 Collector SQL 是否一致。
5. Event transaction 順序是否正確。
6. `INSERT OR IGNORE` 是否只在真正新事件插入時更新 `attackers`。
7. DB commit、Cursor persistence 與 Telegram 通知／失敗隔離的順序。
8. Telegram Token 是否可能出現在 Git、process args、shell history、systemd unit、journal、runner log 或報告。
9. systemd 是否符合非 root 與最小權限原則，實際生效 unit 是否與 repo 模板／報告一致。
10. 第一組 3 × 30 秒證據是否確實來自已授權的外部 SSH 測試端，而非 DB 手工插入或 synthetic log。
11. Telegram 是否同時具有 transport 成功與實際人工收訊證據。
12. Runtime／環境錯誤與產品程式缺陷是否正確分類。
13. API／React 前端、nftables 自動封鎖等後續功能不得誤列為 P1 Blocker 或已完成範圍。

## 獨立重跑

在不修改產品或正式環境的前提下，獨立重跑並記錄：

- compileall
- Ruff
- Mypy
- Pytest
- `PATH="$PWD/.venv/bin:$PATH" make check`
- fresh migration
- repeat migration
- SQLite `quick_check`
- SQLite `foreign_key_check`
- tracked secret scan（不得輸出命中秘密內容）
- systemd unit 靜態檢查
- Git status／diff／HEAD reconciliation

無法執行的項目必須明確標成 `NOT VERIFIED`，不得推定為 PASS。

## 報告與判定

寫入：

`docs/P1_RUNTIME_02_GLM52_SECURITY_REVIEW.md`

報告必須先列出 `ACTIVE_MODEL: glm-5.2`，並列出 tested code/report HEAD、獨立 gate matrix、Agent 1 證據可信度、Blocker／High／Medium／Low、秘密檢查及 AGY 是否可啟動。

只有以下條件同時成立才可核准：

- Blocker = 0
- High = 0
- 沒有 Token 洩漏
- systemd 證據可信
- Real Telegram transport 與人工收訊證據可信
- 第一組 3 × 30 秒證據可信
- 實際 active model 是 `glm-5.2`

核准時最後一行精確寫：

`STAGE_RESULT: APPROVE_FOR_AGY`

否則最後一行精確寫：

`STAGE_RESULT: REJECTED`

最後一行只能是以上兩者之一。完成後停止，不得修改程式或啟動 Agent 3。
