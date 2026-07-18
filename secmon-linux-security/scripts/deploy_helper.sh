#!/usr/bin/env bash
# SecMon 一鍵部署與 Telegram 告警配置輔助指令檔
# 請以 root 權限執行；例如：sudo -- bash scripts/deploy_helper.sh
# Bot Token 只從互動式隱藏輸入讀取，禁止放入命令列參數。

set -Eeuo pipefail

# 檢查是否為 root
if [ "$EUID" -ne 0 ]; then
  echo "❌ 請使用 sudo 或以 root 權限執行此指令檔。"
  exit 1
fi

# 取得 Bot Token；拒絕任何命令列參數，避免秘密出現在 process args/history。
if (($# != 0)); then
  echo "❌ 不接受命令列參數；請以互動式隱藏輸入提供 Bot Token。"
  exit 2
fi
read -r -s -p "請輸入 Telegram Bot Token: " BOT_TOKEN
echo ""
if [ -z "$BOT_TOKEN" ]; then
  echo "❌ 未提供 Bot Token，停止部署。"
  exit 1
fi

CHAT_ID="8350114645"
PROJECT_DIR="/home/b822726/project/get-dg-a1/secmon-linux-security"

echo "============================================="
echo "⚙️  開始部署 SecMon (Security Monitor) 到正式環境"
echo "============================================="

# 1. 建立 secmon 使用者與群組
echo "👤 [1/5] 建立 secmon 使用者與群組..."
if ! getent group secmon >/dev/null; then
  groupadd secmon
fi
if ! getent passwd secmon >/dev/null; then
  useradd -r -g secmon -d /var/lib/secmon -s /sbin/nologin secmon
fi
mkdir -p /var/lib/secmon /var/log/secmon
chown -R secmon:secmon /var/lib/secmon /var/log/secmon
chmod 750 /var/lib/secmon /var/log/secmon

# 2. 建立設定檔與環境變數
echo "📝 [2/5] 建立 /etc/secmon/secmon.env 檔案..."
mkdir -p /etc/secmon
cat << EOF > /etc/secmon/secmon.env
SECMON_APP_NAME=SecMon
SECMON_ENVIRONMENT=production

SECMON_DATABASE_PATH=/var/lib/secmon/secmon.db
SECMON_SSH_LOG_PATH=/var/log/auth.log
SECMON_SSH_CURSOR_PATH=/var/lib/secmon/ssh.cursor
SECMON_COLLECT_INTERVAL_SECONDS=5

SECMON_LOG_LEVEL=INFO
SECMON_AUTO_BLOCK_ENABLED=false

SECMON_TELEGRAM_ENABLED=true
SECMON_TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
SECMON_TELEGRAM_CHAT_ID=${CHAT_ID}
SECMON_TELEGRAM_TIMEOUT_SECONDS=5
SECMON_TELEGRAM_MIN_SEVERITY=3
SECMON_TELEGRAM_COOLDOWN_SECONDS=60
EOF

chown root:root /etc/secmon/secmon.env
chmod 600 /etc/secmon/secmon.env
echo "✅ 環境變數檔權限設定完成。"

# 3. 部署程式碼至 /opt/secmon
echo "📁 [3/5] 複製程式碼至 /opt/secmon..."
mkdir -p /opt/secmon
cp -r ${PROJECT_DIR}/* /opt/secmon/
chown -R secmon:secmon /opt/secmon

# 4. 建立虛擬環境與安裝依賴
echo "🐍 [4/5] 建立 Python 虛擬環境並安裝套件..."
runuser -u secmon -- python3 -m venv /opt/secmon/.venv
runuser -u secmon -- /opt/secmon/.venv/bin/pip install --upgrade pip
runuser -u secmon -- /opt/secmon/.venv/bin/pip install -e /opt/secmon/
echo "✅ Python 環境初始化完成。"

# 5. 註冊 systemd 服務
echo "🔄 [5/5] 配置與重啟 systemd 服務..."
cp /opt/secmon/systemd/secmon-collector.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable secmon-collector.service
systemctl restart secmon-collector.service

echo "============================================="
echo "✅ 部署完成！服務狀態如下："
echo "============================================="
systemctl status secmon-collector.service --no-pager

echo ""
echo "🚀 提示：若要進行 Telegram 連線測試，請執行以下指令："
echo "runuser -u secmon -- bash -lc 'set -a; source /etc/secmon/secmon.env; set +a; cd /opt/secmon; .venv/bin/python -m backend.notifiers.telegram --test'"
