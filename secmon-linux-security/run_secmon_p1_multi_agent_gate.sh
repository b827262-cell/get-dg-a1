#!/usr/bin/env bash
set -Eeuo pipefail

# SecMon P1 production Runtime Gate: four strictly serial, fail-closed agents.
# The outer runner is the only privileged controller. Technical Preflight does
# not elevate or request /start. After the operator enters the exact P1
# /start in a trusted TTY, the controller runs only fixed, quiet sudo checks
# and writes redacted evidence. Agent 1 receives that evidence read-only by
# contract and never performs privilege escalation.

umask 077

readonly BASELINE_HEAD="080e3fe2659cedc9748383907fc56fe795e73fc2"
readonly APPROVED_HEAD_REFERENCE="f39df7b3b7bab2af2649834ba8194950cef08358"
readonly CODEX_MODEL="gpt-5.6-luna"
readonly CLAUDE_MODEL="glm-5.2"
readonly AGY_MODEL="Gemini 3.5 Flash (High)"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"
TASK_DIR="$PROJECT_ROOT/docs/agent_tasks"

TASK_1="$TASK_DIR/01_CODEX_LUNA_PRODUCTION_RUNTIME.md"
TASK_2="$TASK_DIR/02_GLM52_RUNTIME_SECURITY_REVIEW.md"
TASK_3="$TASK_DIR/03_AGY_PRODUCTION_RUNTIME_REVERIFICATION.md"
TASK_4="$TASK_DIR/04_CODEX_FINAL_RELEASE_ACCEPTANCE.md"

REPORT_1="$PROJECT_ROOT/docs/P1_RUNTIME_01_CODEX_LUNA_EXECUTION.md"
REPORT_2="$PROJECT_ROOT/docs/P1_RUNTIME_02_GLM52_SECURITY_REVIEW.md"
REPORT_3="$PROJECT_ROOT/docs/P1_RUNTIME_03_AGY_REVERIFICATION.md"
REPORT_4="$PROJECT_ROOT/docs/P1_RUNTIME_04_CODEX_FINAL_ACCEPTANCE.md"

RUN_ID="$(date +%Y%m%dT%H%M%S%z)"
DEFAULT_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
RUN_LOG_DIR="${SECMON_RUN_LOG_DIR:-$DEFAULT_STATE_HOME/secmon-agent-runs/$RUN_ID}"
PREFLIGHT_FILE="$RUN_LOG_DIR/00_preflight_result.txt"

PREFLIGHT_ONLY=false
RUN_LOGGED_RC=0
STATIC_GATE_STATUS="NOT_RUN"
PRIVILEGED_CONTROLLER_GATE="NOT_RUN"
CONTROLLER_EVIDENCE_FILE=""
ALLOW_GIT_PUSH="${SECMON_ALLOW_GIT_PUSH:-false}"
ALLOW_GITHUB_ISSUE_UPDATE="${SECMON_ALLOW_GITHUB_ISSUE_UPDATE:-false}"
ALLOW_HERMES_NOTIFY="${SECMON_ALLOW_HERMES_NOTIFY:-false}"

P1_TECHNICAL_PREFLIGHT_STATUS="NOT_RUN"
P1_HUMAN_START_AUTHORIZATION="NOT_REQUESTED"
P1_AGENT_EXECUTION_STATUS="NOT_STARTED"
P1_AGENT_START_COUNT=0
P1_RUNTIME_GATE_STATUS="NOT_RUN"
P1_EXTERNAL_SIDE_EFFECTS_EXECUTED=0

usage() {
  printf '%s\n' \
    'Usage: ./run_secmon_p1_multi_agent_gate.sh [--preflight-only]' \
    '' \
    'A full run always starts at Agent 1 and advances only on the exact final' \
    'marker required by the task book. Existing stage reports must be archived' \
    'before a new run so stale evidence can never advance a gate.' \
    '' \
    '--preflight-only performs technical checks only. It never requests /start,' \
    'starts an Agent, or runs a Runtime Gate.' \
    '' \
    'A full run requests an exact, phase-specific /start only after technical' \
    'preflight passes. Authorization cannot be supplied through an environment' \
    'variable and is never reusable by the P2 runner.' \
    '' \
    'External side effects default to disabled:' \
    '  SECMON_ALLOW_GIT_PUSH=false' \
    '  SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false' \
    '  SECMON_ALLOW_HERMES_NOTIFY=false'
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

require_boolean_value() {
  local variable_name="$1"
  local value="$2"
  case "$value" in
    true|false) ;;
    *) die "$variable_name must be exactly true or false" ;;
  esac
}

print_p1_status() {
  printf 'P1_TECHNICAL_PREFLIGHT_STATUS=%s\n' "$P1_TECHNICAL_PREFLIGHT_STATUS"
  printf 'P1_HUMAN_START_AUTHORIZATION=%s\n' "$P1_HUMAN_START_AUTHORIZATION"
  printf 'P1_AGENT_EXECUTION_STATUS=%s\n' "$P1_AGENT_EXECUTION_STATUS"
  printf 'P1_AGENT_START_COUNT=%s\n' "$P1_AGENT_START_COUNT"
  printf 'P1_RUNTIME_GATE_STATUS=%s\n' "$P1_RUNTIME_GATE_STATUS"
  printf 'P1_EXTERNAL_SIDE_EFFECTS_EXECUTED=%s\n' "$P1_EXTERNAL_SIDE_EFFECTS_EXECUTED"
  printf 'PRIVILEGED_CONTROLLER_GATE=%s\n' "$PRIVILEGED_CONTROLLER_GATE"
  printf 'AGENT_SUDO_REQUIRED=NO\n'
  printf 'APPROVED_BASELINE=%s\n' "$BASELINE_HEAD"
  printf 'STATIC_GATE=%s\n' "$STATIC_GATE_STATUS"
  printf 'SECMON_ALLOW_GIT_PUSH=%s\n' "$ALLOW_GIT_PUSH"
  printf 'SECMON_ALLOW_GITHUB_ISSUE_UPDATE=%s\n' "$ALLOW_GITHUB_ISSUE_UPDATE"
  printf 'SECMON_ALLOW_HERMES_NOTIFY=%s\n' "$ALLOW_HERMES_NOTIFY"
}

request_p1_start_authorization() {
  local authorization

  if [[ ! -t 0 ]]; then
    return 1
  fi

  printf '%s\n' \
    'P1 formal execution requires fresh authorization.' \
    'Before authorizing, verify the Telegram prerequisite and the explicitly' \
    'authorized external SSH test source. Type exactly /start for P1 only:' >&2
  IFS= read -r authorization || return 1
  [[ "$authorization" == '/start' ]]
}

last_line() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  tail -n 1 -- "$file" | tr -d '\r'
}

assert_report_is_new() {
  local file="$1"
  [[ ! -e "$file" ]] || die "Existing stage report must be archived before a new run: $file"
}

assert_no_token() {
  local file="$1"
  [[ -f "$file" ]] || return 0

  # Do not print a matching line. Revoke the private log on detection.
  if grep -Eq '[0-9]{8,12}:[[:alnum:]_-]{20,}' "$file"; then
    chmod 000 "$file" 2>/dev/null || true
    die "Possible Telegram token detected; access revoked for: $file"
  fi
}

run_logged() {
  local log_file="$1"
  shift
  local rc

  install -m 0600 /dev/null "$log_file"
  set +e
  "$@" 2>&1 | tee "$log_file"
  rc=${PIPESTATUS[0]}
  set -e
  assert_no_token "$log_file"
  RUN_LOGGED_RC="$rc"
  return 0
}

require_model_evidence() {
  local log_file="$1"
  local model="$2"
  grep -Fq "model: $model" "$log_file" \
    || die "Stage output did not prove requested model: $model"
}

require_agy_active_model_profile() {
  local evidence_file="$1"
  local expected="$2"
  grep -Fqx "AGY_ACTIVE_MODEL_PROFILE: $expected" "$evidence_file" \
    || die "Agent 3 did not provide exact active model/profile evidence: $expected"
}

require_claude_active_model() {
  local json_log="$1"
  local expected_model="$2"

  python3 - "$json_log" "$expected_model" <<'PY'
import json
import pathlib
import sys

data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = sys.argv[2]
models = set(data.get("modelUsage", {}))
print(f"Agent 2 active model evidence: {sorted(models)}")
if models != {expected}:
    print("Agent 2 active model mismatch; Agent 3 was not started.", file=sys.stderr)
    raise SystemExit(22)
PY
}

require_final_marker() {
  local report="$1"
  local expected="$2"
  local actual

  [[ -f "$report" ]] || die "Missing required report: $report"
  assert_no_token "$report"
  actual="$(last_line "$report")"
  [[ "$actual" == "$expected" ]] \
    || die "Unexpected final marker in $report: ${actual:-<empty>}"
}

append_preflight() {
  printf '%s\n' "$*" >>"$PREFLIGHT_FILE"
}

append_controller_evidence() {
  printf '%s\n' "$*" >>"$CONTROLLER_EVIDENCE_FILE"
}

run_static_gate() {
  local static_log="$RUN_LOG_DIR/00_static_gate.log"
  local rc

  install -m 0600 /dev/null "$static_log"
  set +e
  (
    set +e
    cd "$PROJECT_ROOT" || exit 1
    bash -n run_secmon_p1_multi_agent_gate.sh
    p1_bash_rc=$?
    bash -n run_secmon_p2_multi_agent_gate.sh
    p2_bash_rc=$?
    bash -n scripts/deploy_helper.sh
    deploy_bash_rc=$?
    PATH="$PWD/.venv/bin:$PATH" python -m compileall -q backend database tests scripts
    compileall_rc=$?
    PATH="$PWD/.venv/bin:$PATH" make check
    make_check_rc=$?
    printf 'BASH_P1_RC=%s\n' "$p1_bash_rc"
    printf 'BASH_P2_RC=%s\n' "$p2_bash_rc"
    printf 'BASH_DEPLOY_RC=%s\n' "$deploy_bash_rc"
    printf 'COMPILEALL_RC=%s\n' "$compileall_rc"
    printf 'MAKE_CHECK_RC=%s\n' "$make_check_rc"
    if [[ "$p1_bash_rc" -eq 0 && "$p2_bash_rc" -eq 0 \
      && "$deploy_bash_rc" -eq 0 && "$compileall_rc" -eq 0 \
      && "$make_check_rc" -eq 0 ]]; then
      exit 0
    fi
    exit 1
  ) >"$static_log" 2>&1
  rc=$?
  set -e
  assert_no_token "$static_log"

  if [[ "$rc" -eq 0 ]]; then
    STATIC_GATE_STATUS="PASS"
    append_preflight "STATIC_GATE_RESULT: PASS"
    append_preflight "STATIC_GATE_COMMAND: PATH=\"\$PWD/.venv/bin:\$PATH\" make check"
    return 0
  fi

  STATIC_GATE_STATUS="BLOCKED"
  append_preflight "STATIC_GATE_RESULT: BLOCKED"
  append_preflight "STATIC_GATE_LOG: $static_log"
  return 1
}

run_preflight() {
  local -a blockers=()
  local head branch top ahead behind project_prefix commit path

  install -d -m 0700 "$RUN_LOG_DIR"
  install -m 0600 /dev/null "$PREFLIGHT_FILE"
  append_preflight "SecMon P1 sanitized production preflight"
  append_preflight "Time: $(date --iso-8601=seconds)"
  append_preflight "Host: $(hostname)"

  if ! top="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null)"; then
    blockers+=("PROJECT_ROOT is not inside a Git worktree")
    top="UNAVAILABLE"
  fi
  append_preflight "Git top: $top"

  if head="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null)"; then
    append_preflight "HEAD: $head"
  else
    head="UNAVAILABLE"
    blockers+=("HEAD is unavailable")
  fi

  if branch="$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null)"; then
    append_preflight "Branch: ${branch:-DETACHED}"
    [[ "$branch" == "main" ]] || blockers+=("current branch is not main")
  else
    blockers+=("current branch is unavailable")
  fi

  if git -C "$PROJECT_ROOT" cat-file -e "$BASELINE_HEAD^{commit}" 2>/dev/null; then
    if [[ "$head" != "UNAVAILABLE" ]] \
      && ! git -C "$PROJECT_ROOT" merge-base --is-ancestor "$BASELINE_HEAD" "$head"; then
      blockers+=("baseline 080e3fe is not an ancestor of HEAD")
    else
      append_preflight "APPROVED_BASELINE: $BASELINE_HEAD"
      append_preflight "APPROVED_HEAD_REFERENCE: $APPROVED_HEAD_REFERENCE"
      if [[ "$head" == "$APPROVED_HEAD_REFERENCE" ]]; then
        append_preflight "HEAD_POLICY: explicit approved HEAD f39df7b"
      elif git -C "$PROJECT_ROOT" merge-base --is-ancestor \
        "$APPROVED_HEAD_REFERENCE" "$head" 2>/dev/null; then
        append_preflight "HEAD_POLICY: approved HEAD descendant"
      else
        blockers+=("HEAD is neither approved f39df7b nor its descendant")
      fi

      project_prefix="$(git -C "$PROJECT_ROOT" rev-parse --show-prefix 2>/dev/null || true)"
      while IFS= read -r commit; do
        while IFS= read -r path; do
          case "$path" in
            .gitignore|\
            "${project_prefix}"docs/*|\
            "${project_prefix}"run_secmon_p1_multi_agent_gate.sh|\
            "${project_prefix}"run_secmon_p2_multi_agent_gate.sh|\
            "${project_prefix}"scripts/deploy_helper.sh)
              ;;
            '')
              ;;
            *)
              blockers+=("unapproved baseline-range drift: $path")
              ;;
          esac
        done < <(
          git -C "$top" diff-tree --root --no-commit-id --name-only -r "$commit" 2>/dev/null
        )
      done < <(git -C "$PROJECT_ROOT" rev-list --reverse "$BASELINE_HEAD..$head" 2>/dev/null)
      append_preflight "BASELINE_RANGE: $BASELINE_HEAD..$head"
      append_preflight "BASELINE_RANGE_POLICY: approved Runner/docs/framework paths only"
    fi
  else
    blockers+=("baseline commit 080e3fe is unavailable")
  fi

  if git -C "$PROJECT_ROOT" show-ref --verify --quiet refs/remotes/origin/main; then
    read -r behind ahead < <(
      git -C "$PROJECT_ROOT" rev-list --left-right --count origin/main...HEAD
    )
    append_preflight "origin/main divergence: behind=$behind ahead=$ahead"
  else
    blockers+=("origin/main ref is unavailable")
  fi

  git -C "$PROJECT_ROOT" status --short >"$RUN_LOG_DIR/00_git_status.txt" 2>/dev/null \
    || blockers+=("Git working-tree status could not be recorded")
  chmod 0600 "$RUN_LOG_DIR/00_git_status.txt" 2>/dev/null || true

  if ! run_static_gate; then
    blockers+=("Static Gate did not pass")
  fi
  append_preflight "PRIVILEGED_CONTROLLER_GATE: DEFERRED_UNTIL_P1_START"
  append_preflight "AGENT_SUDO_REQUIRED: NO"

  if ((${#blockers[@]} == 0)); then
    append_preflight "PREFLIGHT_RESULT: PASS"
    return 0
  fi

  append_preflight "Blocker count: ${#blockers[@]}"
  for blocker in "${blockers[@]}"; do
    append_preflight "BLOCKER: $blocker"
  done
  append_preflight "PREFLIGHT_RESULT: BLOCKED"
  return 20
}

run_privileged_controller() {
  local -a blockers=()
  local env_ready=true env_mode env_owner

  CONTROLLER_EVIDENCE_FILE="$RUN_LOG_DIR/01_controller_privileged_evidence.txt"
  install -m 0600 /dev/null "$CONTROLLER_EVIDENCE_FILE"
  append_controller_evidence "SecMon P1 redacted privileged controller evidence"
  append_controller_evidence "CONTROLLER_ROLE: OUTER_RUNNER"
  append_controller_evidence "SOURCE_ENV_CONTENT_READ: NO"
  append_controller_evidence "SOURCE_ENV_CONTENT_OUTPUT: NO"
  append_controller_evidence "AGENT_SUDO_REQUIRED: NO"
  append_controller_evidence "EVIDENCE_MODE: 0600"

  if [[ -t 0 ]]; then
    append_controller_evidence "CONTROLLER_TRUSTED_TTY: PASS"
  else
    append_controller_evidence "CONTROLLER_TRUSTED_TTY: FAIL"
    blockers+=("privileged controller requires a trusted TTY")
  fi
  append_controller_evidence "MANUAL_P1_START: PASS"

  printf '%s\n' 'P1 controller privilege handoff: sudo may prompt only in this trusted TTY.' >&2
  if sudo -v; then
    append_controller_evidence "SUDO_CREDENTIAL_CACHE: PASS"
  else
    append_controller_evidence "SUDO_CREDENTIAL_CACHE: FAIL"
    blockers+=("trusted operator sudo credential was not established")
  fi

  if ((${#blockers[@]} == 0)); then
    if controller_check "SUDO_NONINTERACTIVE_REUSE" sudo -n true; then :; else
      blockers+=("controller could not reuse sudo non-interactively")
    fi
    if controller_check "ENV_FILE_PRESENT" sudo -n test -s /etc/secmon/secmon.env; then :; else
      env_ready=false
      blockers+=("production environment file is missing or empty")
    fi
  else
    append_controller_evidence "SUDO_NONINTERACTIVE_REUSE: NOT_RUN"
    append_controller_evidence "ENV_FILE_PRESENT: NOT_RUN"
    env_ready=false
  fi

  if [[ "$env_ready" == true ]]; then
    controller_check "ENV_TOKEN_FORMAT" sudo -n grep -Eq \
      '^SECMON_TELEGRAM_BOT_TOKEN=8860122652:[[:alnum:]_-]{20,}$' \
      /etc/secmon/secmon.env || blockers+=("environment token format check failed")
    controller_check "ENV_CHAT_ID_FORMAT" sudo -n grep -Eq \
      '^SECMON_TELEGRAM_CHAT_ID=8350114645$' /etc/secmon/secmon.env \
      || blockers+=("environment Chat ID check failed")
    controller_check "ENV_TELEGRAM_ENABLED" sudo -n grep -Eq \
      '^SECMON_TELEGRAM_ENABLED=true$' /etc/secmon/secmon.env \
      || blockers+=("Telegram notifier is not enabled")
    controller_check "ENV_AUTO_BLOCK_DISABLED" sudo -n grep -Eq \
      '^SECMON_AUTO_BLOCK_ENABLED=false$' /etc/secmon/secmon.env \
      || blockers+=("automatic blocking is not explicitly disabled")

    env_mode="$(sudo -n stat -c '%a' /etc/secmon/secmon.env 2>/dev/null || true)"
    env_owner="$(sudo -n stat -c '%U:%G' /etc/secmon/secmon.env 2>/dev/null || true)"
    if [[ "$env_owner" == root:root ]]; then
      append_controller_evidence "ENV_FILE_OWNER: PASS"
    else
      append_controller_evidence "ENV_FILE_OWNER: FAIL"
      blockers+=("environment file owner is not root:root")
    fi
    if [[ "$env_mode" == 600 ]]; then
      append_controller_evidence "ENV_FILE_MODE: PASS"
    else
      append_controller_evidence "ENV_FILE_MODE: FAIL"
      blockers+=("environment file mode is not 0600")
    fi
  else
    append_controller_evidence "ENV_TOKEN_FORMAT: NOT_RUN"
    append_controller_evidence "ENV_CHAT_ID_FORMAT: NOT_RUN"
    append_controller_evidence "ENV_TELEGRAM_ENABLED: NOT_RUN"
    append_controller_evidence "ENV_AUTO_BLOCK_DISABLED: NOT_RUN"
    append_controller_evidence "ENV_FILE_OWNER: NOT_RUN"
    append_controller_evidence "ENV_FILE_MODE: NOT_RUN"
  fi

  if [[ "$env_ready" == true && ${#blockers[@]} -eq 0 ]]; then
    controller_check "SYSTEMD_DAEMON_RELOAD" sudo -n systemctl daemon-reload \
      || blockers+=("systemd daemon-reload failed")
    if [[ ${#blockers[@]} -eq 0 ]]; then
      controller_check "SYSTEMD_ENABLED" sudo -n systemctl enable secmon-collector.service \
        || blockers+=("systemd enable failed")
      controller_check "SYSTEMD_RESTART" sudo -n systemctl restart secmon-collector.service \
        || blockers+=("systemd restart failed")
      controller_check "SYSTEMD_IS_ENABLED" sudo -n systemctl is-enabled \
        secmon-collector.service || blockers+=("systemd is-enabled failed")
      controller_check "SYSTEMD_IS_ACTIVE" sudo -n systemctl is-active \
        secmon-collector.service || blockers+=("systemd is-active failed")
      controller_check "SYSTEMD_STATUS" sudo -n systemctl status \
        secmon-collector.service --no-pager || blockers+=("systemd status failed")
    else
      append_controller_evidence "SYSTEMD_ENABLED: NOT_RUN"
      append_controller_evidence "SYSTEMD_RESTART: NOT_RUN"
      append_controller_evidence "SYSTEMD_IS_ENABLED: NOT_RUN"
      append_controller_evidence "SYSTEMD_IS_ACTIVE: NOT_RUN"
      append_controller_evidence "SYSTEMD_STATUS: NOT_RUN"
    fi
  else
    append_controller_evidence "SYSTEMD_DAEMON_RELOAD: NOT_RUN"
    append_controller_evidence "SYSTEMD_ENABLED: NOT_RUN"
    append_controller_evidence "SYSTEMD_RESTART: NOT_RUN"
    append_controller_evidence "SYSTEMD_IS_ENABLED: NOT_RUN"
    append_controller_evidence "SYSTEMD_IS_ACTIVE: NOT_RUN"
    append_controller_evidence "SYSTEMD_STATUS: NOT_RUN"
  fi

  if sudo -k >/dev/null 2>&1; then
    append_controller_evidence "SUDO_CREDENTIAL_CACHE_AFTER_CONTROLLER: CLEARED"
  else
    append_controller_evidence "SUDO_CREDENTIAL_CACHE_AFTER_CONTROLLER: UNKNOWN"
    blockers+=("controller could not clear its sudo credential cache")
  fi

  if ((${#blockers[@]} == 0)); then
    append_controller_evidence "CONTROLLER_GATE_RESULT: PASS"
    PRIVILEGED_CONTROLLER_GATE="PASS"
    chmod 0600 "$CONTROLLER_EVIDENCE_FILE"
    assert_no_token "$CONTROLLER_EVIDENCE_FILE"
    return 0
  fi

  append_controller_evidence "BLOCKER_COUNT: ${#blockers[@]}"
  for blocker in "${blockers[@]}"; do
    append_controller_evidence "BLOCKER: $blocker"
  done
  append_controller_evidence "CONTROLLER_GATE_RESULT: BLOCKED"
  PRIVILEGED_CONTROLLER_GATE="BLOCKED"
  chmod 0600 "$CONTROLLER_EVIDENCE_FILE"
  assert_no_token "$CONTROLLER_EVIDENCE_FILE"
  return 20
}

controller_check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    append_controller_evidence "$label: PASS"
    return 0
  fi
  append_controller_evidence "$label: FAIL"
  return 1
}

while (($#)); do
  case "$1" in
    --preflight-only)
      PREFLIGHT_ONLY=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "Unknown argument: $1"
      ;;
  esac
  shift
done

for task_file in "$TASK_1" "$TASK_2" "$TASK_3" "$TASK_4"; do
  [[ -f "$task_file" ]] || die "Missing task prompt: $task_file"
done

require_boolean_value SECMON_ALLOW_GIT_PUSH "$ALLOW_GIT_PUSH"
require_boolean_value SECMON_ALLOW_GITHUB_ISSUE_UPDATE "$ALLOW_GITHUB_ISSUE_UPDATE"
require_boolean_value SECMON_ALLOW_HERMES_NOTIFY "$ALLOW_HERMES_NOTIFY"
export SECMON_ALLOW_GIT_PUSH="$ALLOW_GIT_PUSH"
export SECMON_ALLOW_GITHUB_ISSUE_UPDATE="$ALLOW_GITHUB_ISSUE_UPDATE"
export SECMON_ALLOW_HERMES_NOTIFY="$ALLOW_HERMES_NOTIFY"

for command_name in git codex claude agy sudo grep stat tee python3 hostname make bash; do
  need_cmd "$command_name"
done
if [[ "$ALLOW_HERMES_NOTIFY" == "true" ]]; then
  need_cmd hermes
fi

cd "$PROJECT_ROOT"

printf '%s\n' '=== SecMon P1 production Runtime Gate preflight ==='
set +e
run_preflight
PREFLIGHT_RC=$?
set -e
assert_no_token "$PREFLIGHT_FILE"

if [[ $PREFLIGHT_RC -eq 0 ]]; then
  P1_TECHNICAL_PREFLIGHT_STATUS="PASS"
  printf 'PREFLIGHT_RESULT: PASS\n'
else
  P1_TECHNICAL_PREFLIGHT_STATUS="BLOCKED"
  printf 'PREFLIGHT_RESULT: BLOCKED\n' >&2
  printf 'Sanitized details: %s\n' "$PREFLIGHT_FILE" >&2
fi

if [[ "$PREFLIGHT_ONLY" == "true" ]]; then
  print_p1_status
  exit "$PREFLIGHT_RC"
fi

if [[ $PREFLIGHT_RC -ne 0 ]]; then
  print_p1_status
  exit "$PREFLIGHT_RC"
fi

if ! request_p1_start_authorization; then
  P1_HUMAN_START_AUTHORIZATION="DENIED"
  print_p1_status
  printf '%s\n' 'P1 authorization denied; no Agent was started.' >&2
  exit 21
fi

P1_HUMAN_START_AUTHORIZATION="GRANTED"
append_preflight "P1_HUMAN_START_AUTHORIZATION=GRANTED"

set +e
run_privileged_controller
CONTROLLER_RC=$?
set -e
assert_no_token "$CONTROLLER_EVIDENCE_FILE"
append_preflight "PRIVILEGED_CONTROLLER_EVIDENCE_FILE: $CONTROLLER_EVIDENCE_FILE"
append_preflight "PRIVILEGED_CONTROLLER_GATE: $PRIVILEGED_CONTROLLER_GATE"

if [[ $CONTROLLER_RC -ne 0 ]]; then
  P1_RUNTIME_GATE_STATUS="BLOCKED"
  print_p1_status
  printf 'P1 controller blocked; no Agent was started. Evidence: %s\n' \
    "$CONTROLLER_EVIDENCE_FILE" >&2
  exit "$CONTROLLER_RC"
fi

export SECMON_PRIVILEGED_EVIDENCE_FILE="$CONTROLLER_EVIDENCE_FILE"
export SECMON_AGENT_SUDO_REQUIRED="NO"
P1_AGENT_EXECUTION_STATUS="STARTED"
P1_AGENT_START_COUNT=1
P1_RUNTIME_GATE_STATUS="RUNNING"

assert_report_is_new "$REPORT_1"
export SECMON_PREFLIGHT_RESULT_FILE="$PREFLIGHT_FILE"

printf '%s\n' '=== Agent 1: Codex Luna production deployment/runtime ==='
run_logged "$RUN_LOG_DIR/01_codex_luna.log" \
  codex exec \
    -C "$PROJECT_ROOT" \
    --ephemeral \
    -m "$CODEX_MODEL" \
    -c 'model_reasoning_effort="xhigh"' \
    -c 'approval_policy="never"' \
    -s danger-full-access \
    - <"$TASK_1"
STAGE_1_RC="$RUN_LOGGED_RC"

[[ -f "$REPORT_1" ]] || die "Agent 1 did not create its report (exit $STAGE_1_RC)"
assert_no_token "$REPORT_1"
STAGE_1_RESULT="$(last_line "$REPORT_1")"

case "$STAGE_1_RESULT" in
  'STAGE_RESULT: BLOCKED')
    printf '%s\n' 'Agent 1 result: BLOCKED. Serial execution stopped; Agent 2 was not started.'
    exit 20
    ;;
  'STAGE_RESULT: READY_FOR_GLM_REVIEW')
    [[ $PREFLIGHT_RC -eq 0 ]] \
      || die "Agent 1 claimed READY despite a blocked runner preflight"
    [[ $STAGE_1_RC -eq 0 ]] \
      || die "Agent 1 claimed READY but codex exited $STAGE_1_RC"
    require_model_evidence "$RUN_LOG_DIR/01_codex_luna.log" "$CODEX_MODEL"
    ;;
  *)
    die "Agent 1 report has an invalid final marker: ${STAGE_1_RESULT:-<empty>}"
    ;;
esac

assert_report_is_new "$REPORT_2"
need_cmd claude
require_final_marker "$REPORT_1" 'STAGE_RESULT: READY_FOR_GLM_REVIEW'

printf '%s\n' '=== Agent 2: GLM-5.2 independent runtime/security review ==='
CLAUDE_JSON_LOG="$RUN_LOG_DIR/02_glm52_review.json"
CLAUDE_STDERR_LOG="$RUN_LOG_DIR/02_glm52_review.stderr.log"
install -m 0600 /dev/null "$CLAUDE_JSON_LOG"
install -m 0600 /dev/null "$CLAUDE_STDERR_LOG"
set +e
claude -p --model glm-5.2 \
    "$(<"$TASK_2")" \
    --no-session-persistence \
    --output-format json \
    --allowedTools 'Read,Glob,Grep,Bash,Write' \
    2> >(tee "$CLAUDE_STDERR_LOG" >&2) \
    | tee "$CLAUDE_JSON_LOG"
STAGE_2_RC=${PIPESTATUS[0]}
set -e
assert_no_token "$CLAUDE_JSON_LOG"
assert_no_token "$CLAUDE_STDERR_LOG"

if ! require_claude_active_model "$CLAUDE_JSON_LOG" "$CLAUDE_MODEL"; then
  printf '%s\n' 'STAGE_RESULT: REJECTED' >&2
  printf '%s\n' 'Agent 2 result: REJECTED. Active model was not GLM-5.2; Agent 3 was not started.' >&2
  exit 22
fi

[[ -f "$REPORT_2" ]] || die "Agent 2 did not create its report (exit $STAGE_2_RC)"
assert_no_token "$REPORT_2"
STAGE_2_RESULT="$(last_line "$REPORT_2")"

case "$STAGE_2_RESULT" in
  'STAGE_RESULT: REJECTED')
    printf '%s\n' 'Agent 2 result: REJECTED. Serial execution stopped; Agent 3 was not started.'
    exit 21
    ;;
  'STAGE_RESULT: APPROVE_FOR_AGY')
    [[ $STAGE_2_RC -eq 0 ]] \
      || die "Agent 2 claimed APPROVE but claude exited $STAGE_2_RC"
    ;;
  *)
    die "Agent 2 report has an invalid final marker: ${STAGE_2_RESULT:-<empty>}"
    ;;
esac

assert_report_is_new "$REPORT_3"
need_cmd agy
require_final_marker "$REPORT_2" 'STAGE_RESULT: APPROVE_FOR_AGY'

printf '%s\n' '=== Agent 3: AGY production runtime reverification ==='
[[ "$AGY_MODEL" == 'Gemini 3.5 Flash (High)' ]] \
  || die "Agent 3 model/profile is not the required Gemini 3.5 Flash (High)"
agy models | grep -Fqx "$AGY_MODEL" \
  || die "Required AGY model/profile is unavailable: $AGY_MODEL"

AGY_INTERNAL_LOG="$RUN_LOG_DIR/03_agy_internal.log"
run_logged "$RUN_LOG_DIR/03_agy_reverification.log" \
  agy -p \
    --model "$AGY_MODEL" \
    --mode accept-edits \
    --print-timeout 90m \
    --log-file "$AGY_INTERNAL_LOG" \
    "$(<"$TASK_3")"
STAGE_3_RC="$RUN_LOGGED_RC"
require_agy_active_model_profile "$RUN_LOG_DIR/03_agy_reverification.log" "$AGY_MODEL"
assert_no_token "$AGY_INTERNAL_LOG"

if [[ -f "$AGY_INTERNAL_LOG" ]] \
  && grep -Eiq 'not in local config|defaulting to|not logged into Antigravity|fallback' "$AGY_INTERNAL_LOG"; then
  die "AGY resolver reported missing authentication or model fallback"
fi

[[ -f "$REPORT_3" ]] || die "Agent 3 did not create its report (exit $STAGE_3_RC)"
assert_no_token "$REPORT_3"
require_agy_active_model_profile "$REPORT_3" "$AGY_MODEL"
STAGE_3_RESULT="$(last_line "$REPORT_3")"

case "$STAGE_3_RESULT" in
  'STAGE_RESULT: RUNTIME_GATE_NOT_PASSED')
    printf '%s\n' 'Agent 3 result: RUNTIME_GATE_NOT_PASSED. Serial execution stopped; Agent 4 was not started.'
    exit 22
    ;;
  'STAGE_RESULT: RUNTIME_GATE_PASS')
    [[ $STAGE_3_RC -eq 0 ]] \
      || die "Agent 3 claimed PASS but agy exited $STAGE_3_RC"
    ;;
  *)
    die "Agent 3 report has an invalid final marker: ${STAGE_3_RESULT:-<empty>}"
    ;;
esac

assert_report_is_new "$REPORT_4"
require_final_marker "$REPORT_3" 'STAGE_RESULT: RUNTIME_GATE_PASS'

printf '%s\n' '=== Agent 4: fresh Codex final release acceptance ==='
GIT_TOP="$(git rev-parse --show-toplevel)"
run_logged "$RUN_LOG_DIR/04_codex_final_acceptance.log" \
  codex exec \
    -C "$PROJECT_ROOT" \
    --add-dir "$GIT_TOP/.git" \
    --ephemeral \
    -m "$CODEX_MODEL" \
    -c 'model_reasoning_effort="xhigh"' \
    -c 'approval_policy="never"' \
    -c 'sandbox_workspace_write.network_access=true' \
    -s workspace-write \
    - <"$TASK_4"
STAGE_4_RC="$RUN_LOGGED_RC"

[[ -f "$REPORT_4" ]] || die "Agent 4 did not create its report (exit $STAGE_4_RC)"
assert_no_token "$REPORT_4"
STAGE_4_RESULT="$(last_line "$REPORT_4")"

case "$STAGE_4_RESULT" in
  'FINAL_DECISION: P1_RELEASE_GATE_NOT_PASSED')
    printf '%s\n' 'Agent 4 decision: P1_RELEASE_GATE_NOT_PASSED. Issue #2 must remain OPEN.'
    exit 30
    ;;
  'FINAL_DECISION: P1_RELEASE_GATE_PASS')
    [[ $STAGE_4_RC -eq 0 ]] \
      || die "Agent 4 claimed PASS but codex exited $STAGE_4_RC"
    require_model_evidence "$RUN_LOG_DIR/04_codex_final_acceptance.log" "$CODEX_MODEL"
    printf '%s\n' 'FINAL_DECISION: P1_RELEASE_GATE_PASS'
    exit 0
    ;;
  *)
    die "Agent 4 report has an invalid final marker: ${STAGE_4_RESULT:-<empty>}"
    ;;
esac
