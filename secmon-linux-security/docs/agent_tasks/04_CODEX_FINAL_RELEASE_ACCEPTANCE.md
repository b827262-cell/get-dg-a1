# SecMon P1 正式環境 Runtime Gate — Agent 4 / Codex Final Acceptance

## 啟動條件與工作階段

只有 `docs/P1_RUNTIME_03_AGY_REVERIFICATION.md` 的最後一行精確等於：

`STAGE_RESULT: RUNTIME_GATE_PASS`

才可啟動本階段。

- 必須使用新的 Codex 工作階段，不得延續 Agent 1 session。
- Required model: `gpt-5.6-luna`
- Required reasoning: `xhigh`
- Sandbox: `workspace-write`

Runner 會匯出 `SECMON_ALLOW_GIT_PUSH`、
`SECMON_ALLOW_GITHUB_ISSUE_UPDATE` 與 `SECMON_ALLOW_HERMES_NOTIFY`，預設均為
`false`。只有值精確等於 `true` 才授權對應外部副作用；缺失、`false` 或無法
驗證時必須跳過並記錄 `SKIPPED_BY_POLICY`。本文件中的 push、Issue 與 Hermes
命令只是條件式流程，不構成授權。

## 角色與邊界

你是最終 Release Gate Reviewer，不是 Agent 1 的延續。

禁止修改產品程式、Migration、測試、部署內容、systemd unit、正式設定或 runtime state。只允許：

- 讀取與交叉核對證據
- 重跑必要的唯讀檢查
- 建立 `docs/P1_RUNTIME_04_CODEX_FINAL_ACCEPTANCE.md`
- 在完整 PASS 時，精確加入去敏報告、執行最終秘密掃描、建立 docs-only 驗收 commit、確認遠端未漂移後 push，並更新／關閉正確的 Issue #2

所有既有 working-tree 變更均視為使用者資產。不得 `git add .`、broad staging、reset、checkout、clean、force push 或 rewrite history。任何 GitHub 寫入前，必須確認 repo identity、Issue #2 identity、認證與 remote no-drift。

## 輸入

- Approved baseline: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- Explicitly accepted current HEAD reference: `f39df7b3b7bab2af2649834ba8194950cef08358`
- `080e3fe..HEAD` 的 drift 檢查只將 allowlist 外的 product-code 變更視為
  code drift；`.gitignore`、Runner／framework scripts 與 `docs/**` 不得誤判。
- `docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md`
- `docs/P1_RUNTIME_02_GLM52_SECURITY_REVIEW.md`
- `docs/P1_RUNTIME_03_AGY_REVERIFICATION.md`
- current Git／code／production runtime state
- P1 既有設計、稽核與正式驗證報告

## 必須核對

1. Approved baseline `080e3fe`、明確接受的 `f39df7b` 與目前 Tested Code HEAD。
2. Agent 1、2、3 是否測試同一份程式。
3. docs/framework allowlist commit 是否與 product-code/runtime fix commit
   清楚區分。
4. Static Gate 是否全數 PASS（固定使用
   `PATH="$PWD/.venv/bin:$PATH"`）。
5. Pytest 是否全數通過。
6. Real Telegram：
   - Agent 1 transport PASS
   - Agent 1 人工收訊確認
   - AGY transport PASS
   - AGY 人工收訊確認
7. Production systemd Runtime PASS。
8. Agent 1 第一組 3 × 30 秒 Gate PASS。
9. AGY 第二組 3 × 30 秒 Gate PASS。
10. SQLite event、attacker、source、Cursor 一致。
11. Replay／restart 不重複計數。
12. Telegram 失敗不影響 DB／Cursor／Collector continuity。
13. Token 未出現在 Git、staging、報告、runner log、journal、process args 或 systemd unit。
14. Blocker = 0。
15. High = 0。
16. Medium／Low 已列入 backlog 且不阻擋 P1。
17. Web API、React Dashboard、nftables 自動封鎖等後續功能未被誤列為 P1 已完成或本階段 Blocker。

任何必要證據不足均不得以「大致成功」、「技術測試完成」或部分 PASS 代替 Release PASS。

## 最終報告

寫入：

`docs/P1_RUNTIME_04_CODEX_FINAL_ACCEPTANCE.md`

報告必須明確分開回答：

- 驗證工作是否完成
- 程式 Gate 是否通過
- 正式 Runtime Gate 是否通過
- P1 Release Gate 是否通過
- Issue #2 是否可以關閉

報告本文在 PASS 時必須另含一行：

`P1_FORMAL_ACCEPTANCE=PASS`

NOT PASSED 時則必須包含：

`P1_FORMAL_ACCEPTANCE=FAIL`

並列出 exact tested HEAD、四階段 matrix、去敏證據索引、已完成／後續範圍、severity findings 與最終決策。

## PASS

只有全部必要條件成立，才可：

1. 完成報告本文，並以 `FINAL_DECISION: P1_RELEASE_GATE_PASS` 作為最後一行；封存後不得再修改報告。
2. 對將提交的精確檔案執行最後秘密掃描，且不得輸出秘密內容。
3. 只將去敏報告加入 Git。
4. 建立包含已封存最終報告的 docs-only 驗收 commit。
5. 只有 `SECMON_ALLOW_GIT_PUSH=true` 時，才可在再次確認 remote 無漂移後
   安全 push；否則記錄 `SKIPPED_BY_POLICY`。
6. 只有 `SECMON_ALLOW_GITHUB_ISSUE_UPDATE=true` 時，才可在正確的 Issue #2
   留下完整去敏驗收證據並關閉；否則保持未變更並記錄
   `SKIPPED_BY_POLICY`。

只有 `SECMON_ALLOW_HERMES_NOTIFY=true` 時才可執行 PASS Hermes 通知：

```bash
hermes send --to telegram:8350114645 "✅ TUFA16 SecMon P1 正式驗收通過
Result: P1_RELEASE_GATE_PASS
Git HEAD: <short-head>
Report: docs/P1_RUNTIME_04_CODEX_FINAL_ACCEPTANCE.md
Issue #2: CLOSED"
```

## NOT PASSED

任何必要證據不足時：

- Issue #2 保持原狀；不得在未授權時更新或關閉。
- 不得建立／push 假驗收 commit，不得關閉 Issue。
- 先完成報告本文與 Hermes 通知嘗試，再以 `FINAL_DECISION: P1_RELEASE_GATE_NOT_PASSED` 作為最後一行；封存後不得再修改報告。

只有 `SECMON_ALLOW_HERMES_NOTIFY=true` 時才可執行 NOT PASSED Hermes 通知：

```bash
hermes send --to telegram:8350114645 "⚠️ TUFA16 SecMon P1 最終驗收未通過
Result: P1_RELEASE_GATE_NOT_PASSED
Git HEAD: <short-head>
Report: docs/P1_RUNTIME_04_CODEX_FINAL_ACCEPTANCE.md
Issue #2: OPEN"
```

通知不得包含 Bot Token、環境變數或其他秘密。Hermes 通知失敗不得改變最終
判定。未授權時不得嘗試通知。PASS 報告封存後才執行已明確授權的
Git／Issue／Hermes 動作，且不得為記錄通知結果而改動已封存報告。

報告最後一行只能是以下兩者之一：

- `FINAL_DECISION: P1_RELEASE_GATE_PASS`
- `FINAL_DECISION: P1_RELEASE_GATE_NOT_PASSED`

完成後停止。
