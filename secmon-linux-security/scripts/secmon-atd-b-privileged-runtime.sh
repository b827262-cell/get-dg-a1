#!/bin/bash -p
# Fixed-scope ATD-B privileged runtime gate.
#
# This file is intended to be reviewed before it is installed root-owned.  It
# has no user-controlled command, unit, endpoint, table, or shell fragment.
# The nftables objects are deliberately an unhooked counter-only probe chain;
# they cannot become a packet filtering policy.
set -Eeuo pipefail

PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 077
unset BASH_ENV CDPATH ENV

readonly APP_ROOT=/opt/secmon
readonly API_UNIT=secmon-api.service
readonly COLLECTOR_UNIT=secmon-collector.service
readonly API_BASE=http://127.0.0.1:8080
readonly PYTHON=/opt/secmon/.venv/bin/python
readonly NFT=/usr/sbin/nft
readonly TABLE_FAMILY=inet
readonly TABLE_NAME=secmon_atd_b_test
readonly CHAIN_NAME=probe
readonly RULE_COMMENT=secmon-atd-b-test
readonly EVIDENCE_DIR=/tmp/secmon-atd-b-evidence
readonly BEFORE_RULESET=$EVIDENCE_DIR/nft-before.txt
readonly AFTER_RULESET=$EVIDENCE_DIR/nft-after.txt
readonly TABLE_EVIDENCE=$EVIDENCE_DIR/nft-table.txt
readonly HTTP_HEALTH_BEFORE=$EVIDENCE_DIR/http-health-before.txt
readonly HTTP_READY_BEFORE=$EVIDENCE_DIR/http-ready-before.txt
readonly HTTP_HEALTH_AFTER=$EVIDENCE_DIR/http-health-after.txt
readonly HTTP_READY_AFTER=$EVIDENCE_DIR/http-ready-after.txt
readonly SYSTEMD_BEFORE=$EVIDENCE_DIR/systemd-api.unit.txt
readonly SYSTEMD_AFTER=$EVIDENCE_DIR/systemd-collector.unit.txt
readonly SYSTEMD_STATUS=$EVIDENCE_DIR/systemd-status.txt
readonly READINESS_DIAGNOSTICS=$EVIDENCE_DIR/readiness-timeout.txt
readonly IDENTITY_EVIDENCE=$EVIDENCE_DIR/identity.txt
readonly DETECTOR_EVIDENCE=$EVIDENCE_DIR/detector.txt
readonly RULESET_DIFF=$EVIDENCE_DIR/ruleset.diff
readonly BEFORE_RULESET_NORMALIZED=$EVIDENCE_DIR/nft-before.normalized.txt
readonly AFTER_RULESET_NORMALIZED=$EVIDENCE_DIR/nft-after.normalized.txt
readonly RULESET_NORMALIZED_DIFF=$EVIDENCE_DIR/ruleset.normalized.diff
readonly RUNTIME_TMP_PREFIX=/tmp/secmon-atd-b-synthetic.

runtime_tmp=''
cleanup_result=NOT_RUN
cleanup_done=0

remove_runtime_tmp() {
  [[ -z "$runtime_tmp" ]] && return 0
  case "$runtime_tmp" in
    "$RUNTIME_TMP_PREFIX"??????) ;;
    *)
      printf 'REFUSING_UNSAFE_RUNTIME_TMP=%s\n' "$runtime_tmp" >&2
      return 1
      ;;
  esac
  [[ -d "$runtime_tmp" ]] || return 0
  if [[ -f "$runtime_tmp/synthetic.db" ]]; then
    /usr/bin/rm -f -- "$runtime_tmp/synthetic.db"
  fi
  /usr/bin/rmdir -- "$runtime_tmp"
}

abort() {
  printf 'ATD_B_RUNTIME_ABORT=%s\n' "$1" >&2
  exit 1
}

require_root() {
  [[ $(/usr/bin/id -u) -eq 0 ]] || abort ROOT_REQUIRED
}

require_fixed_tools() {
  local tool
  for tool in "$NFT" /usr/bin/curl /usr/bin/diff /usr/bin/systemctl /usr/sbin/runuser; do
    [[ -x "$tool" ]] || abort "MISSING_TOOL_$tool"
  done
  [[ -x "$PYTHON" ]] || abort MISSING_DEPLOYED_PYTHON
  [[ -d "$APP_ROOT/backend" && -d "$APP_ROOT/database/migrations" ]] || abort DEPLOYMENT_LAYOUT_INVALID
}

prepare_evidence_dir() {
  if [[ -e "$EVIDENCE_DIR" || -L "$EVIDENCE_DIR" ]]; then
    [[ -d "$EVIDENCE_DIR" && ! -L "$EVIDENCE_DIR" ]] || abort EVIDENCE_DIRECTORY_INVALID
    [[ $(/usr/bin/stat -c '%u:%g:%a' -- "$EVIDENCE_DIR") == 0:0:700 ]] || abort EVIDENCE_DIRECTORY_INSECURE
  else
    /usr/bin/install -d -o root -g root -m 0700 -- "$EVIDENCE_DIR" || abort EVIDENCE_DIRECTORY_CREATE_FAILED
  fi
}

show_unit_contract() {
  local unit=$1 output=$2
  /usr/bin/systemctl cat "$unit" >"$output" || abort "UNIT_UNAVAILABLE_$unit"
}

require_unit_contracts() {
  show_unit_contract "$API_UNIT" "$SYSTEMD_BEFORE"
  show_unit_contract "$COLLECTOR_UNIT" "$SYSTEMD_AFTER"
  /usr/bin/grep -Fqx 'User=secmon' "$SYSTEMD_BEFORE" || abort API_USER_CONTRACT_MISSING
  /usr/bin/grep -Fqx 'User=secmon' "$SYSTEMD_AFTER" || abort COLLECTOR_USER_CONTRACT_MISSING
  /usr/bin/grep -Fqx 'NoNewPrivileges=true' "$SYSTEMD_BEFORE" || abort API_NNP_CONTRACT_MISSING
  /usr/bin/grep -Fqx 'NoNewPrivileges=true' "$SYSTEMD_AFTER" || abort COLLECTOR_NNP_CONTRACT_MISSING
  /usr/bin/grep -Fqx 'ExecStart=/opt/secmon/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8080' "$SYSTEMD_BEFORE" \
    || abort API_ENDPOINT_CONTRACT_MISSING
  /usr/bin/grep -Fqx 'ExecStart=/opt/secmon/.venv/bin/python -m backend.collectors.main' "$SYSTEMD_AFTER" \
    || abort COLLECTOR_EXEC_CONTRACT_MISSING
}

table_exists() {
  "$NFT" list table "$TABLE_FAMILY" "$TABLE_NAME" >/dev/null 2>&1
}

delete_test_table() {
  if table_exists; then
    "$NFT" delete table "$TABLE_FAMILY" "$TABLE_NAME" >/dev/null 2>&1 || return 1
  fi
  if table_exists; then
    return 1
  fi
  cleanup_result=PASS
  return 0
}

capture_after() {
  "$NFT" list ruleset >"$AFTER_RULESET"
  "$NFT" list tables >"$TABLE_EVIDENCE"
  if table_exists; then
    printf 'NFTABLES_CLEANUP=FAIL\n' >&2
    return 1
  fi
  if /usr/bin/diff -u "$BEFORE_RULESET" "$AFTER_RULESET" >"$RULESET_DIFF"; then
    printf 'RULESET_RAW_DIFF=NONE\n'
  else
    printf 'RULESET_RAW_DIFF=PRESENT\n'
    /usr/bin/sed -E \
      's/counter packets [0-9]+ bytes [0-9]+/counter packets <number> bytes <number>/g' \
      "$BEFORE_RULESET" >"$BEFORE_RULESET_NORMALIZED"
    /usr/bin/sed -E \
      's/counter packets [0-9]+ bytes [0-9]+/counter packets <number> bytes <number>/g' \
      "$AFTER_RULESET" >"$AFTER_RULESET_NORMALIZED"
    if ! /usr/bin/diff -u "$BEFORE_RULESET_NORMALIZED" "$AFTER_RULESET_NORMALIZED" \
      >"$RULESET_NORMALIZED_DIFF"; then
      printf 'RULESET_NORMALIZED_DIFF=FAIL\n' >&2
      printf 'RULESET_DIFF=FAIL\n' >&2
      return 1
    fi
    printf 'RULESET_NORMALIZED_DIFF=PASS\n'
  fi
  printf 'NFTABLES_CLEANUP=%s\n' "$cleanup_result"
  printf 'RULESET_DIFF=PASS\n'
}

on_exit() {
  local rc=$?
  if [[ "$cleanup_done" -eq 1 ]]; then
    exit "$rc"
  fi
  cleanup_done=1
  set +e
  delete_test_table
  if [[ -e "$BEFORE_RULESET" ]]; then
    capture_after >/dev/null 2>&1
  fi
  if [[ -n "$runtime_tmp" ]]; then
    remove_runtime_tmp >/dev/null 2>&1
  fi
  exit "$rc"
}

preflight() {
  require_root
  require_fixed_tools
  prepare_evidence_dir
  require_unit_contracts
  table_exists && abort TEST_TABLE_ALREADY_EXISTS
  "$NFT" list tables >"$TABLE_EVIDENCE" || abort NFT_LIST_TABLES_FAILED
  printf 'PREFLIGHT=PASS\n'
  printf 'TABLE=%s %s\n' "$TABLE_FAMILY" "$TABLE_NAME"
  printf 'API_UNIT=%s\n' "$API_UNIT"
  printf 'COLLECTOR_UNIT=%s\n' "$COLLECTOR_UNIT"
  printf 'HEALTH_ENDPOINTS=%s/healthz,%s/readyz\n' "$API_BASE" "$API_BASE"
}

create_test_objects() {
  "$NFT" add table "$TABLE_FAMILY" "$TABLE_NAME"
  "$NFT" add chain "$TABLE_FAMILY" "$TABLE_NAME" "$CHAIN_NAME"
  "$NFT" add rule "$TABLE_FAMILY" "$TABLE_NAME" "$CHAIN_NAME" counter comment "$RULE_COMMENT"
  "$NFT" list table "$TABLE_FAMILY" "$TABLE_NAME" >"$TABLE_EVIDENCE"
  /usr/bin/grep -Fq "table $TABLE_FAMILY $TABLE_NAME" "$TABLE_EVIDENCE" || abort NFT_TABLE_READBACK_FAILED
  /usr/bin/grep -Fq "chain $CHAIN_NAME" "$TABLE_EVIDENCE" || abort NFT_CHAIN_READBACK_FAILED
  /usr/bin/grep -Fq "$RULE_COMMENT" "$TABLE_EVIDENCE" || abort NFT_RULE_READBACK_FAILED
  printf 'NFTABLES_CREATE=PASS\nNFTABLES_LIST=PASS\n'
}

probe_endpoint() {
  local label=$1 url=$2 expected=$3 output=$4
  "$PYTHON" - "$url" "$expected" "$label" >"$output" 2>&1 <<'PY'
import sys
import urllib.request
from urllib.error import URLError

try:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as response:
        body = response.read().decode()
        print(f"{sys.argv[3]}_HTTP_STATUS={response.status}")
        print(f"{sys.argv[3]}_BODY={body}")
        if response.status != 200 or body != sys.argv[2]:
            raise SystemExit(1)
except (URLError, TimeoutError, OSError) as error:
    print(f"{sys.argv[3]}_ERROR={type(error).__name__}: {error}")
    raise SystemExit(1)
PY
}

health_probe() {
  local health_output=$1 ready_output=$2
  probe_endpoint HEALTHZ "$API_BASE/healthz" '{"status":"ok"}' "$health_output" \
    && probe_endpoint READYZ "$API_BASE/readyz" '{"status":"ready"}' "$ready_output"
}

save_readiness_timeout_diagnostics() {
  : >"$READINESS_DIAGNOSTICS"
  printf '%s\n' '=== systemctl status secmon-api.service ===' >>"$READINESS_DIAGNOSTICS"
  /usr/bin/systemctl status "$API_UNIT" --no-pager >>"$READINESS_DIAGNOSTICS" 2>&1 || true
  printf '%s\n' '=== journalctl -u secmon-api.service ===' >>"$READINESS_DIAGNOSTICS"
  /usr/bin/journalctl -u "$API_UNIT" --no-pager >>"$READINESS_DIAGNOSTICS" 2>&1 || true
  printf '%s\n' '=== service MainPID ===' >>"$READINESS_DIAGNOSTICS"
  /usr/bin/systemctl show "$API_UNIT" -p MainPID --value --no-pager >>"$READINESS_DIAGNOSTICS" 2>&1 || true
  printf '%s\n' '=== socket listening state ===' >>"$READINESS_DIAGNOSTICS"
  /usr/bin/ss -ltnp >>"$READINESS_DIAGNOSTICS" 2>&1 || true
}

wait_for_readiness() {
  local attempt=0
  : >"$HTTP_HEALTH_AFTER"
  : >"$HTTP_READY_AFTER"
  while (( attempt < 30 )); do
    attempt=$((attempt + 1))
    if probe_endpoint HEALTHZ "$API_BASE/healthz" '{"status":"ok"}' "$HTTP_HEALTH_AFTER" \
      && probe_endpoint READYZ "$API_BASE/readyz" '{"status":"ready"}' "$HTTP_READY_AFTER"; then
      printf 'READINESS_POLLING=PASS\nREADINESS_ATTEMPTS=%d\n' "$attempt"
      printf 'HTTP_HEALTH_AFTER=PASS\nHTTP_READY_AFTER=PASS\n'
      return 0
    fi
    if (( attempt < 30 )); then
      /usr/bin/sleep 1
    fi
  done
  save_readiness_timeout_diagnostics
  printf 'READINESS_POLLING=FAIL\nREADINESS_ATTEMPTS=%d\n' "$attempt" >&2
  printf 'HTTP_HEALTH_AFTER=FAIL\nHTTP_READY_AFTER=FAIL\n' >&2
  return 1
}

record_process_identity() {
  local unit=$1 label=$2 pid uid cap
  pid=$(/usr/bin/systemctl show "$unit" -p MainPID --value --no-pager)
  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || abort "${label}_PID_INVALID"
  uid=$(/usr/bin/awk '/^Uid:/ {print $2}' "/proc/$pid/status")
  cap=$(/usr/bin/awk '/^CapEff:/ {print $2}' "/proc/$pid/status")
  printf '%s_UNIT=%s\n%s_PID=%s\n%s_UID=%s\n%s_CAPEFF=%s\n' \
    "$label" "$unit" "$label" "$pid" "$label" "$uid" "$label" "$cap" >>"$IDENTITY_EVIDENCE"
  [[ "$uid" == 958 ]] || abort "${label}_UID_NOT_SECMON"
  [[ "$cap" == 0000000000000000 ]] || abort "${label}_CAPEFF_NOT_ZERO"
}

synthetic_detector_gate() {
  runtime_tmp=$(/usr/bin/mktemp -d "${RUNTIME_TMP_PREFIX}XXXXXX")
  /usr/bin/chown secmon:secmon "$runtime_tmp"
  /usr/bin/chmod 0700 "$runtime_tmp"
  /usr/sbin/runuser -u secmon -- /usr/bin/env PYTHONPATH="$APP_ROOT" \
  "$PYTHON" - "$runtime_tmp" >"$DETECTOR_EVIDENCE" <<'PY'
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.services.traffic_detector import CounterSample, DetectorConfig, InterfaceDetector, persist_detection
from database.migrate import migrate

root = Path(sys.argv[1])
database = root / "synthetic.db"
migrate(database, Path("/opt/secmon/database/migrations"))

def sample(second: int, rx: int) -> CounterSample:
    return CounterSample(1, "synthetic0", datetime(2026, 7, 20, tzinfo=UTC) + timedelta(seconds=second), rx, 0, rx // 10, 0, 1)

config = DetectorConfig(fixed_rate_threshold=100, warmup_samples=2, rolling_window=4,
                        consecutive_anomalies=2, consecutive_normals=2, cooldown_seconds=0)
detector = InterfaceDetector(config)
states = []
with sqlite3.connect(database) as connection:
    connection.execute("INSERT INTO network_interfaces(id,name,ifindex) VALUES (1,'synthetic0',1)")
    for current in (sample(0, 0), sample(1, 10), sample(2, 20), sample(3, 120),
                    sample(4, 220), sample(5, 230), sample(6, 240), sample(7, 250)):
        result = detector.process(current)
        states.append(result.state)
        persist_detection(connection, current, result)
    row = connection.execute("SELECT state,count,resolved_at FROM traffic_alerts WHERE event_key='interface:1:atd-b'").fetchone()
    unresolved = connection.execute("SELECT COUNT(*) FROM traffic_alerts WHERE state != 'RESOLVED'").fetchone()[0]
    events = connection.execute("SELECT COUNT(*) FROM traffic_alerts WHERE event_key='interface:1:atd-b'").fetchone()[0]
    connection.execute("CREATE TABLE rollback_probe(value TEXT)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO rollback_probe(value) VALUES ('synthetic')")
    connection.rollback()
    rolled_back = connection.execute("SELECT COUNT(*) FROM rollback_probe").fetchone()[0]

if states != ['NORMAL', 'NORMAL', 'NORMAL', 'WATCH', 'ALERT', 'RECOVERING', 'RESOLVED', 'NORMAL']:
    raise SystemExit("detector state sequence mismatch")
if row != ('RESOLVED', 2, row[2]) or row[2] is None or unresolved != 0 or events != 1 or rolled_back != 0:
    raise SystemExit("detector persistence consistency mismatch")

restarted = InterfaceDetector(config)
restart_states = [restarted.process(sample(0, 0)).state, restarted.process(sample(1, 10)).state]
if restart_states != ['NORMAL', 'NORMAL']:
    raise SystemExit("restart warm-up mismatch")
print("BASELINE_REBUILD=PASS")
print("DETECTOR_AFTER_RESTART=PASS")
print("SYNTHETIC_ANOMALY=PASS")
print("RECOVERY=PASS")
print("UNRESOLVED_EVENT_CONSISTENCY=PASS")
print("ROLLBACK=PASS")
PY
  remove_runtime_tmp
  runtime_tmp=''
  /usr/bin/grep -Fqx 'BASELINE_REBUILD=PASS' "$DETECTOR_EVIDENCE" || abort BASELINE_REBUILD_FAILED
  /usr/bin/grep -Fqx 'UNRESOLVED_EVENT_CONSISTENCY=PASS' "$DETECTOR_EVIDENCE" || abort UNRESOLVED_EVENT_CONSISTENCY_FAILED
}

run_gate() {
  require_root
  preflight
  trap on_exit EXIT INT TERM
  "$NFT" list ruleset >"$BEFORE_RULESET" || abort NFT_RULESET_BACKUP_FAILED
  "$NFT" list tables >"$TABLE_EVIDENCE" || abort NFT_LIST_TABLES_FAILED
  create_test_objects
  health_probe "$HTTP_HEALTH_BEFORE" "$HTTP_READY_BEFORE"
  printf 'HTTP_BEFORE=PASS\n'
  /usr/bin/systemctl restart "$API_UNIT"
  /usr/bin/systemctl is-active --quiet "$API_UNIT"
  /usr/bin/systemctl status "$API_UNIT" --no-pager >>"$SYSTEMD_STATUS"
  printf 'HTTP_RESTART_COMMAND=PASS\n'
  wait_for_readiness || abort API_READINESS_TIMEOUT
  record_process_identity "$API_UNIT" API
  /usr/bin/systemctl restart "$COLLECTOR_UNIT"
  /usr/bin/systemctl is-active --quiet "$COLLECTOR_UNIT"
  /usr/bin/systemctl status "$COLLECTOR_UNIT" --no-pager >>"$SYSTEMD_STATUS"
  printf 'COLLECTOR_AFTER_RESTART=PASS\n'
  record_process_identity "$COLLECTOR_UNIT" COLLECTOR
  synthetic_detector_gate
  printf 'APPLICATION_USER=secmon\nCAP_EFF=0000000000000000\n'
  delete_test_table || abort NFTABLES_DELETE_FAILED
  printf 'NFTABLES_DELETE=PASS\n'
  capture_after
  printf 'ATD_B_PRIVILEGED_RUNTIME_STATUS=PASS\n'
}

cleanup_only() {
  require_root
  if delete_test_table; then
    printf 'NFTABLES_DELETE=PASS\nNFTABLES_CLEANUP=PASS\n'
  else
    printf 'NFTABLES_DELETE=FAIL\nNFTABLES_CLEANUP=FAIL\n' >&2
    return 1
  fi
}

main() {
  [[ $# -eq 1 ]] || abort USAGE
  case "$1" in
    --preflight) preflight ;;
    --run) run_gate ;;
    --cleanup) cleanup_only ;;
    *) abort USAGE ;;
  esac
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
