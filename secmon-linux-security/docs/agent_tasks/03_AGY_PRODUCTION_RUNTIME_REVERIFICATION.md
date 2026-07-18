# SecMon P1 正式環境 Runtime Gate — Agent 3 / AGY

## 啟動條件與模型鎖定

只有 `docs/P1_RUNTIME_02_GLM52_SECURITY_REVIEW.md` 的最後一行精確等於：

`STAGE_RESULT: APPROVE_FOR_AGY`

才可執行本階段。

正式 runner 必須以 AGY CLI 的 print/non-interactive 模式啟動本階段，唯一允許的
Agent 3 launcher 是：

`agy -p --model "$AGY_MODEL" ... <TASK_3>`

其中 runner 的 `AGY_MODEL` 必須精確等於 `Gemini 3.5 Flash (High)`。
不得用 Codex、Claude 或任何其他命令啟動 Agent 3，也不得改用其他模型、profile
或任何 fallback 路徑。

Agent 3 啟動後，在執行任何 Runtime 驗證前，第一個非空回應行必須先回報並核對
實際 active model/profile，使用以下可驗證標示：

`AGY_ACTIVE_MODEL_PROFILE: Gemini 3.5 Flash (High)`

同一個標示也必須原樣寫入報告。這必須是實際 active model/profile 證據，不是只
回報 requested model；若無法核對、標示不符、出現 fallback 或 active model/profile
不是 `Gemini 3.5 Flash (High)`，立即判定 non-pass 並停止，最後一行只能是
`STAGE_RESULT: RUNTIME_GATE_NOT_PASSED`，不得啟動 Agent 4。

## 角色與邊界

你是獨立正式 Runtime 驗證者。

- 不得修改產品程式、Migration、測試、systemd unit、部署內容或持久改變環境檔；故障隔離測試所需的受控暫時狀態必須最小化、完整還原並留下去敏證據。
- 唯一允許新增或修改的是 `docs/P1_RUNTIME_03_AGY_REVERIFICATION.md`。
- 不得直接採信 Agent 1 或 Agent 2 的 PASS。
- 不得 commit、push、變更 Issue、宣告最終 P1 驗收或啟動 Agent 4。
- 使用 `sudo -n`；不得要求、讀取或處理 sudo 密碼。
- 不得輸出 Bot Token，不得執行 environment dump／shell tracing。
- 不得用 mock、fixture、synthetic log 或手工 SQLite 寫入替代正式 Runtime 證據。

## 輸入

- Baseline HEAD: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- `docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md`
- `docs/P1_RUNTIME_02_GLM52_SECURITY_REVIEW.md`

## A. 身分與漂移

- 記錄 exact HEAD、branch 與 remote 差異。
- 檢查 Git working tree。
- 核對 Agent 1、Agent 2 的 Tested HEAD。
- 區分 docs-only 變更與 code 變更。
- 確認沒有未說明的產品漂移。

## B. Static Gate

獨立重跑並記錄：

- compileall
- Ruff
- Mypy
- Pytest
- `make check`
- fresh／repeat Migration
- SQLite `quick_check`
- SQLite `foreign_key_check`

## C. Real Telegram Smoke

重新執行一次正式 Telegram Smoke：

- 不在 stdout、stderr、process args、journal 或報告輸出 Token
- 確認 API transport
- 取得人類對 AGY 本次測試訊息的明確收訊確認
- 安全檢查 stdout、stderr 與 journal

Transport 成功但沒有本次人工收訊證據時，Real Telegram Gate 不得 PASS。

## D. Production systemd

獨立確認：

- enabled
- active
- 非 root 執行
- 正式 `EnvironmentFile=/etc/secmon/secmon.env`
- 正式 DB 與 Cursor
- Collector 可讀正式 SSH authentication log
- 無 restart loop
- SIGTERM 正常
- restart 正常且從既有 Cursor 繼續
- runtime artifact 均位於 repo 外

## E. 第二組 3 × 30 秒 Gate

必須獨立重新執行三輪，不得只閱讀 Agent 1 證據。每輪確認：

- 由已授權外部 SSH 測試端產生極少量真實失敗登入
- 30 秒內有正確的新事件寫入
- `attackers` 彙總正確
- `log_sources` 更新
- Cursor 前進
- Telegram 告警送出且人工確認要求有被滿足
- replay／restart 不重複計數
- service remains active

每輪必須記錄獨立的開始／結束時間、前後 sanitized DB 值、Cursor 與 service state。

## F. Telegram 失敗隔離

用安全且受控的方式驗證 Telegram 發送失敗時：

- DB 不回滾
- Cursor 不回退
- Collector 不退出
- 下一輪仍可執行

不得破壞正式 Token；若暫時修改任何正式狀態，必須事先備份、完整還原並提供去敏證據。無法安全注入時標為未驗證，不得推定 PASS。

## 報告與判定

寫入：

`docs/P1_RUNTIME_03_AGY_REVERIFICATION.md`

報告須包含 active model/profile、exact HEAD、漂移檢查、Static Gate、Telegram、systemd、第二組三輪 E2E、失敗隔離、秘密掃描、Blocker／High／Medium／Low 與精確未通過原因。

只有所有 Runtime Gate 均以獨立證據通過時，最後一行精確寫：

`STAGE_RESULT: RUNTIME_GATE_PASS`

否則最後一行精確寫：

`STAGE_RESULT: RUNTIME_GATE_NOT_PASSED`

最後一行只能是以上兩者之一。完成後停止；不得自行關閉 Issue #2 或宣告最終 P1 驗收。
