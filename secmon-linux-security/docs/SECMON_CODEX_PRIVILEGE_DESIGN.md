# SecMon Codex CLI 最小權限維護控制器

## 目的與範圍

此設計以一個固定 dispatcher 取代每次以 `sudo -v` 驗證、從 `/tmp` 執行
腳本、複製檔案到 `/root`，或在每一次維護前以人工 checksum 交接的流程。
管理者只需在審查後人工安裝 root-owned 檔案與精確 sudoers allowlist。Codex
之後只能透過 `sudo -n` 執行四個固定動作，不能取得 shell、任意 `systemctl`、
Python、bash/sh、路徑或參數權限。

本設計不會自行安裝任何檔案，也不會改變 sudoers、service 或正式資料庫。

## 固定介面與期限

唯一允許的呼叫為：

```text
sudo -n /usr/local/sbin/secmon-maintenance status
sudo -n /usr/local/sbin/secmon-maintenance backup-db
sudo -n /usr/local/sbin/secmon-maintenance migrate-db
sudo -n /usr/local/sbin/secmon-maintenance runtime-recovery
```

dispatcher 要求剛好一個子命令，拒絕額外參數、未知子命令、任何路徑與 shell
片段。它使用固定 `PATH`、`umask 077`、絕對路徑、固定 constants，並清除常見
shell 初始化環境變數。它不讀取 `/tmp` 的任何執行腳本，不使用 `eval`，也不讓
使用者環境變數覆寫 service、DB、migration 或 helper 路徑。

固定授權期限為：

```text
AUTHORIZATION_EXPIRES=2027-07-18
```

UTC 日期晚於此日期時，dispatcher 在呼叫 logger、systemctl、helper 或任何其他
root 操作前輸出 `AUTHORIZATION_EXPIRED` 並以非零結束。此期限獨立於 sudo
`timestamp_timeout`。

## 元件與安全邊界

| 安裝路徑 | 原始檔 | 職責 |
| --- | --- | --- |
| `/usr/local/sbin/secmon-maintenance` | `scripts/secmon-maintenance` | root-only 固定 dispatcher 與 `status` |
| `/usr/local/libexec/secmon/backup-db` | `scripts/privileged/backup-db` | inactive gate、SQLite backup、integrity 與 SHA-256 驗證 |
| `/usr/local/libexec/secmon/migrate-db` | `scripts/privileged/migrate-db` | inactive gate、內建 backup、核准 manifest/checksum、migration、integrity、idempotency |
| `/usr/local/libexec/secmon/runtime-recovery` | `scripts/privileged/runtime-recovery` | root-owned manifest/deployed hash gate、migration precondition、Restart policy gate、systemd recovery、60 秒穩定性、去敏 journal 摘要、rollback SQLite capability check |
| `/usr/local/libexec/secmon/runtime-approved.manifest` | `scripts/privileged/runtime-approved.manifest` | 固定核准 runtime head、runtime/unit/migration SHA-256 的純資料 manifest |
| `/etc/sudoers.d/secmon-codex` | `docs/secmon-codex-sudoers.example` | 僅四個無參數 sudo 命令 |

每個 privileged helper 都再次確認 EUID=0 與零個參數；因此即使直接呼叫 helper，
也不接受額外資料或外部路徑。所有 action 的開始、成功與 abort 都以
`secmon-maintenance` tag 記錄到 syslog/journal；journal 檢查只輸出四個錯誤類型的
計數，絕不輸出原文。SQLite 查詢只讀取 integrity、migration version、count 與
table-existence metadata，不會列出資料列。

`runtime-approved.manifest` 是以 `|` 分隔的資料檔，絕不以 `source` 或 `eval`
載入。它固定 `APPROVED_RUNTIME_HEAD=21eb7787ce4e8d8cd16ed47e7533aa21d424f643`，
並記錄 `/opt/secmon` runtime、effective unit、migration runner 與 SQL migration 的
SHA-256。兩個 privileged helper 只讀取安裝後 root-owned 的固定路徑；不會在 root
執行時信任使用者可寫 checkout 或呼叫 Git。Migration manifest 為
`001_initial.sql`、`005_ssh_parser.sql`、`006_log_sources_defaults.sql`、
`007_add_log_source_stats.sql`，部署內容不同時 fail closed。

Runtime recovery 在任何 service start 前，會將 `/opt/secmon` 的 collector runtime
檔案與 `/etc/systemd/system/secmon-collector.service` 分別和 root-owned approval
manifest 中、對應核准 head 的 SHA-256 比對。它也只透過正式 `RestartUSec` property 讀取 restart
延遲；`5s`、`5000ms` 與 `5000000us` 都正規化為 `5000000` microseconds，並要求
`Restart=on-failure`。空值、無法解析或任何不等價的有效值都輸出
`ABORT_RESTART_POLICY_MISMATCH`，不會啟動 service。

## 一次性人工安裝程序

管理者必須在已核准的 checkout 中審查 source、執行 tests 與 `visudo` syntax
check，並以 root 在受控 console 逐一安裝。下列為建議命令，不由本設計自動執行：

```bash
/usr/bin/install -o root -g root -m 0755 scripts/secmon-maintenance /usr/local/sbin/secmon-maintenance
/usr/bin/install -d -o root -g root -m 0750 /usr/local/libexec/secmon
/usr/bin/install -o root -g root -m 0750 scripts/privileged/backup-db /usr/local/libexec/secmon/backup-db
/usr/bin/install -o root -g root -m 0750 scripts/privileged/migrate-db /usr/local/libexec/secmon/migrate-db
/usr/bin/install -o root -g root -m 0750 scripts/privileged/runtime-recovery /usr/local/libexec/secmon/runtime-recovery
/usr/bin/install -o root -g root -m 0640 scripts/privileged/runtime-approved.manifest /usr/local/libexec/secmon/runtime-approved.manifest
/usr/bin/install -o root -g root -m 0440 docs/secmon-codex-sudoers.example /etc/sudoers.d/secmon-codex
/usr/bin/visudo -cf /etc/sudoers.d/secmon-codex
```

安裝前後必須確認 `/usr/local/sbin` 與 `/usr/local/libexec/secmon` 不可由
`b822726` 寫入；sudoers 以 root:root、0440 保存。任何 source、部署檔、unit、
runtime user、migration checksum 或授權期限的變更，都需要重新人工審查與安裝，
不得由 Codex 自行更新。

## 不授權的能力

此 allowlist 不授權 `sudo` shell、任意 command、任意 Python、任意 systemctl、
萬用字元參數、`/tmp` 路徑、service 啟停以外的操作，或讀取環境檔。它也不授權
Telegram、SSH E2E、replay、push、Issue 或 Hermes 動作。runtime recovery 的
service start 僅由已核准的固定 helper 進行，且先完成 migration precondition。

## 續期與撤銷

在 `2027-07-18` 前，管理者應重新審查此設計、實際安裝檔、sudoers allowlist、
deployment manifest 與 audit log，再以新的固定日期發佈新版 controller。要立即
撤銷權限時，由管理者移除 `/etc/sudoers.d/secmon-codex`；Codex 不得自行撤銷或
修改該檔。
