#!/usr/bin/env bash
set -Eeuo pipefail

# SecMon P2 Agent 1–3 serial framework. This runner never starts Agent 4,
# merges main, closes Issue #2, or declares P2 Release Gate PASS.
# Agent output is kept in private run logs and is never streamed to the terminal.

umask 077

readonly CODEX_MODEL="gpt-5.6-luna"
readonly CLAUDE_MODEL="glm-5.2"
readonly AGY_MODEL="Gemini 3.5 Flash"
readonly AGY_REASONING="High"
readonly AGY_PROFILE="${AGY_MODEL} (${AGY_REASONING})"
readonly HERMES_TARGET="telegram:8350114645"
readonly FEATURE_BRANCH="feature/secmon-p2-api-auth"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${PROJECT_ROOT:-$SCRIPT_DIR}" && pwd -P)"
TASK_DIR="$PROJECT_ROOT/docs/agent_tasks"

TASK_1="$TASK_DIR/P2_01_CODEX_API_AUTH_IMPLEMENTATION.md"
TASK_2="$TASK_DIR/P2_02_GLM52_SECURITY_REVIEW.md"
TASK_3="$TASK_DIR/P2_03_AGY_API_RUNTIME_VERIFICATION.md"
TASK_4="$TASK_DIR/P2_04_CODEX_FINAL_RELEASE_AUDIT.md"

REPORT_1="$PROJECT_ROOT/docs/P2_01_CODEX_API_AUTH_IMPLEMENTATION_REPORT.md"
REPORT_2="$PROJECT_ROOT/docs/P2_02_GLM52_SECURITY_REVIEW.md"
REPORT_3="$PROJECT_ROOT/docs/P2_03_AGY_API_RUNTIME_VERIFICATION.md"
REPORT_4="$PROJECT_ROOT/docs/P2_04_CODEX_FINAL_RELEASE_AUDIT.md"

RUN_ID="$(date +%Y%m%dT%H%M%S%z)"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
RUN_LOG_DIR="${SECMON_RUN_LOG_DIR:-$STATE_HOME/secmon-p2-agent-runs/$RUN_ID}"
CONTEXT_FILE="$RUN_LOG_DIR/00_p2_context.txt"

P1_MODE="DEVELOPMENT_ONLY"
P1_STATUS="NOT_TRUSTED"
P1_FINAL_REPORT="NONE"
P1_LAST_PROGRAM_REPORT="NONE"
P1_REPORT_COMMIT="NONE"
P1_TESTED_CODE_HEAD="NONE"
GIT_TOP=""
GIT_PREFIX=""
PREFLIGHT_ONLY=false
ALLOW_GIT_PUSH="${SECMON_ALLOW_GIT_PUSH:-false}"
ALLOW_GITHUB_ISSUE_UPDATE="${SECMON_ALLOW_GITHUB_ISSUE_UPDATE:-false}"
ALLOW_HERMES_NOTIFY="${SECMON_ALLOW_HERMES_NOTIFY:-false}"

P2_TECHNICAL_PREFLIGHT_STATUS="NOT_RUN"
P2_HUMAN_START_AUTHORIZATION="NOT_REQUESTED"
P2_P1_DEPENDENCY_STATUS="NOT_PASSED"
P2_AGENT_EXECUTION_STATUS="NOT_STARTED"
P2_AGENT_START_COUNT=0
P2_RUNTIME_GATE_STATUS="NOT_RUN"
P2_RELEASE_GATE_STATUS="NOT_PASSED"
P2_EXTERNAL_SIDE_EFFECTS_EXECUTED=0
RUN_RC=0
STOP_STAGE="PREFLIGHT"
STOP_RESULT="P2_FRAMEWORK_BLOCKED"
STOP_REPORT="NONE"
STOP_NEXT="No Agent was started. Inspect the sanitized run context."

usage() {
  printf '%s\n' \
    'Usage: ./run_secmon_p2_multi_agent_gate.sh [--preflight-only]' \
    '' \
    '--preflight-only checks the P2 framework and local technical prerequisites.' \
    'It reports P1 dependency status but never requires P1 PASS, requests' \
    '/start, starts an Agent, runs a Runtime Gate, or sends a notification.' \
    '' \
    'A full run requires committed P1_FORMAL_ACCEPTANCE=PASS evidence and then' \
    'requests a fresh, P2-only exact /start. P1 authorization is never reused.' \
    '' \
    'External side effects default to disabled:' \
    '  SECMON_ALLOW_GIT_PUSH=false' \
    '  SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false' \
    '  SECMON_ALLOW_HERMES_NOTIFY=false'
}

require_boolean_value() {
  local variable_name="$1"
  local value="$2"
  case "$value" in
    true|false) ;;
    *)
      printf 'P2 runner blocked: %s must be exactly true or false\n' \
        "$variable_name" >&2
      return 1
      ;;
  esac
}

print_p2_status() {
  printf 'P2_TECHNICAL_PREFLIGHT_STATUS=%s\n' "$P2_TECHNICAL_PREFLIGHT_STATUS"
  printf 'P2_HUMAN_START_AUTHORIZATION=%s\n' "$P2_HUMAN_START_AUTHORIZATION"
  printf 'P2_P1_DEPENDENCY_STATUS=%s\n' "$P2_P1_DEPENDENCY_STATUS"
  printf 'P2_AGENT_EXECUTION_STATUS=%s\n' "$P2_AGENT_EXECUTION_STATUS"
  printf 'P2_AGENT_START_COUNT=%s\n' "$P2_AGENT_START_COUNT"
  printf 'P2_RUNTIME_GATE_STATUS=%s\n' "$P2_RUNTIME_GATE_STATUS"
  printf 'P2_RELEASE_GATE_STATUS=%s\n' "$P2_RELEASE_GATE_STATUS"
  printf 'P2_EXTERNAL_SIDE_EFFECTS_EXECUTED=%s\n' "$P2_EXTERNAL_SIDE_EFFECTS_EXECUTED"
  printf 'SECMON_ALLOW_GIT_PUSH=%s\n' "$ALLOW_GIT_PUSH"
  printf 'SECMON_ALLOW_GITHUB_ISSUE_UPDATE=%s\n' "$ALLOW_GITHUB_ISSUE_UPDATE"
  printf 'SECMON_ALLOW_HERMES_NOTIFY=%s\n' "$ALLOW_HERMES_NOTIFY"
}

request_p2_start_authorization() {
  local authorization

  if [[ ! -t 0 ]]; then
    return 1
  fi

  printf '%s\n' \
    'P2 formal execution requires a new P2-only authorization.' \
    'The P1 /start cannot authorize P2. Type exactly /start for P2 only:' >&2
  IFS= read -r authorization || return 1
  [[ "$authorization" == '/start' ]]
}

die_before_agents() {
  printf 'P2 runner blocked before Agent launch: %s\n' "$*" >&2
  STOP_RESULT="P2_FRAMEWORK_BLOCKED"
  STOP_NEXT="Repair the framework/preflight condition, then rerun after reviewing the context."
  print_p2_status
  notify_and_exit 20
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die_before_agents "missing command: $1"
}

last_line() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  tail -n 1 -- "$file" | tr -d '\r'
}

git_blob_last_line() {
  local commit="$1"
  local project_relative_path="$2"

  git -C "$GIT_TOP" cat-file blob \
    "$commit:${GIT_PREFIX}${project_relative_path}" 2>/dev/null \
    | tail -n 1 \
    | tr -d '\r'
}

git_blob_tested_code_head() {
  local commit="$1"
  local project_relative_path="$2"

  git -C "$GIT_TOP" cat-file blob \
    "$commit:${GIT_PREFIX}${project_relative_path}" 2>/dev/null \
    | grep -Eio 'tested[[:space:]_-]+code[[:space:]_-]+head[^0-9a-f]*[0-9a-f]{40}' \
    | grep -Eio '[0-9a-f]{40}' \
    | head -n 1
}

first_nonempty_line() {
  local file="$1"
  awk 'NF { print; exit }' "$file"
}

assert_no_secret_pattern() {
  local file="$1"
  local secret_pattern
  [[ -f "$file" ]] || return 0

  # Boolean-only scan: never print a matching line or its surrounding content.
  secret_pattern='([0-9]{8,12}):[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]+PRIVATE KEY-----|((api[_-]?key|access[_-]?token|password|secret)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9_./+=-]{20,})'
  if grep -Eiq -- "$secret_pattern" "$file"; then
    chmod 000 -- "$file" 2>/dev/null || true
    return 1
  fi
  return 0
}

send_notification() {
  local hermes_rc
  local short_head branch host now message

  if [[ "$ALLOW_HERMES_NOTIFY" != "true" ]]; then
    if [[ -f "$CONTEXT_FILE" ]]; then
      printf '%s\n' 'Hermes notification: SKIPPED_BY_POLICY' >>"$CONTEXT_FILE"
    fi
    printf '%s\n' 'Hermes notification: SKIPPED_BY_POLICY' >&2
    return 0
  fi

  short_head="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || printf '%s' UNKNOWN)"
  branch="$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || printf '%s' DETACHED)"
  host="$(hostname 2>/dev/null || printf '%s' UNKNOWN)"
  now="$(date --iso-8601=seconds)"
  message="$(printf '%s\n' \
    'Project: SecMon P2' \
    "Host: $host" \
    "Time: $now" \
    "Git short HEAD: $short_head" \
    "Current branch: ${branch:-DETACHED}" \
    "Agent stopped at: $STOP_STAGE" \
    "Gate result: $STOP_RESULT" \
    "Report path: $STOP_REPORT" \
    "P1 dependency status: $P1_STATUS ($P1_MODE)" \
    "Next action: $STOP_NEXT")"

  if command -v hermes >/dev/null 2>&1; then
    set +e
    hermes send --to "$HERMES_TARGET" "$message" >/dev/null 2>&1
    hermes_rc=$?
    set -e
    P2_EXTERNAL_SIDE_EFFECTS_EXECUTED=$((P2_EXTERNAL_SIDE_EFFECTS_EXECUTED + 1))
  else
    hermes_rc=127
  fi
  if [[ -f "$CONTEXT_FILE" ]]; then
    printf 'Hermes notification exit code: %s\n' "$hermes_rc" >>"$CONTEXT_FILE"
  fi
  printf 'Hermes notification exit code: %s\n' "$hermes_rc" >&2
}

notify_and_exit() {
  local exit_code="$1"
  send_notification
  exit "$exit_code"
}

record_p1_evidence() {
  local report report_commit tested_code_head report_time
  local newest_program_time=-1

  P1_STATUS="NOT_TRUSTED"
  P1_MODE="DEVELOPMENT_ONLY"
  P1_FINAL_REPORT="NONE"
  P1_LAST_PROGRAM_REPORT="NONE"
  P1_REPORT_COMMIT="NONE"
  P1_TESTED_CODE_HEAD="NONE"

  # Use committed blobs only. Uncommitted edits to a tracked report can never
  # upgrade P1 dependency status.
  while IFS= read -r report; do
    [[ -n "$report" ]] || continue
    report_commit="$(git -C "$PROJECT_ROOT" log -1 --format=%H -- "$report" 2>/dev/null || true)"
    [[ -n "$report_commit" ]] || continue
    git -C "$GIT_TOP" cat-file -e \
      "$report_commit:${GIT_PREFIX}${report}" 2>/dev/null || continue
    tested_code_head="$(git_blob_tested_code_head "$report_commit" "$report" || true)"
    [[ -n "$tested_code_head" ]] || continue
    git -C "$PROJECT_ROOT" cat-file -e "$tested_code_head^{commit}" 2>/dev/null || continue
    report_time="$(git -C "$PROJECT_ROOT" show -s --format=%ct "$report_commit" 2>/dev/null || printf '%s' 0)"
    if [[ "$report_time" =~ ^[0-9]+$ ]] && (( report_time > newest_program_time )); then
      newest_program_time="$report_time"
      P1_LAST_PROGRAM_REPORT="$report"
      P1_TESTED_CODE_HEAD="$tested_code_head"
      P1_REPORT_COMMIT="$report_commit"
    fi
  done < <(git -C "$PROJECT_ROOT" ls-files 'docs/P1*.md')

  while IFS= read -r report; do
    [[ -n "$report" ]] || continue
    report_commit="$(git -C "$PROJECT_ROOT" log -1 --format=%H -- "$report" 2>/dev/null || true)"
    [[ -n "$report_commit" ]] || continue
    git -C "$PROJECT_ROOT" cat-file -e "$report_commit^{commit}" 2>/dev/null || continue
    git -C "$GIT_TOP" cat-file -e \
      "$report_commit:${GIT_PREFIX}${report}" 2>/dev/null || continue
    [[ "$(git_blob_last_line "$report_commit" "$report" 2>/dev/null || true)" == \
      'FINAL_DECISION: P1_RELEASE_GATE_PASS' ]] || continue
    git -C "$GIT_TOP" cat-file blob \
      "$report_commit:${GIT_PREFIX}${report}" 2>/dev/null \
      | grep -Fqx 'P1_FORMAL_ACCEPTANCE=PASS' || continue
    tested_code_head="$(git_blob_tested_code_head "$report_commit" "$report" || true)"
    [[ -n "$tested_code_head" ]] || continue
    git -C "$PROJECT_ROOT" cat-file -e "$tested_code_head^{commit}" 2>/dev/null || continue
    git -C "$PROJECT_ROOT" merge-base --is-ancestor "$report_commit" HEAD 2>/dev/null || continue
    git -C "$PROJECT_ROOT" merge-base --is-ancestor "$tested_code_head" "$report_commit" 2>/dev/null || continue
    git -C "$PROJECT_ROOT" diff --quiet "$tested_code_head" "$report_commit" -- \
      backend database systemd tests pyproject.toml Makefile frontend config scripts 2>/dev/null || continue
    git -C "$PROJECT_ROOT" diff --quiet "$report_commit" HEAD -- \
      backend database systemd tests pyproject.toml Makefile frontend config scripts 2>/dev/null || continue

    P1_STATUS="PASS"
    P1_MODE="RELEASE_ELIGIBLE"
    P1_FINAL_REPORT="$report"
    P1_LAST_PROGRAM_REPORT="$report"
    P1_REPORT_COMMIT="$report_commit"
    P1_TESTED_CODE_HEAD="$tested_code_head"
    break
  done < <(git -C "$PROJECT_ROOT" ls-files 'docs/P1*.md')
}

run_technical_preflight() {
  local -a blockers=()
  local required_cmd task_file report_file

  for required_cmd in git python3 hostname codex claude agy; do
    command -v "$required_cmd" >/dev/null 2>&1 \
      || blockers+=("missing command: $required_cmd")
  done

  GIT_TOP="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
  GIT_PREFIX="$(git -C "$PROJECT_ROOT" rev-parse --show-prefix 2>/dev/null || true)"
  if [[ -z "$GIT_TOP" ]]; then
    blockers+=("PROJECT_ROOT is not inside a Git worktree")
  elif [[ "$GIT_TOP" != "$PROJECT_ROOT" ]]; then
    case "$PROJECT_ROOT/" in
      "$GIT_TOP"/*) ;;
      *) blockers+=("PROJECT_ROOT is outside the confirmed Git worktree") ;;
    esac
  fi

  for task_file in "$TASK_1" "$TASK_2" "$TASK_3" "$TASK_4"; do
    [[ -f "$task_file" ]] || blockers+=("missing formal task file: $task_file")
  done

  for report_file in "$REPORT_1" "$REPORT_2" "$REPORT_3"; do
    [[ ! -e "$report_file" ]] \
      || blockers+=("stale stage report must be archived: $report_file")
  done

  if [[ -n "$GIT_TOP" ]]; then
    record_p1_evidence
  fi
  if [[ "$P1_STATUS" == "PASS" ]]; then
    P2_P1_DEPENDENCY_STATUS="PASS"
  else
    P2_P1_DEPENDENCY_STATUS="NOT_PASSED"
  fi

  if ((${#blockers[@]} == 0)); then
    P2_TECHNICAL_PREFLIGHT_STATUS="PASS"
    return 0
  fi

  P2_TECHNICAL_PREFLIGHT_STATUS="BLOCKED"
  printf 'P2 technical preflight blocker count: %s\n' "${#blockers[@]}" >&2
  for required_cmd in "${blockers[@]}"; do
    printf 'P2_TECHNICAL_BLOCKER=%s\n' "$required_cmd" >&2
  done
  return 20
}

write_context() {
  local origin_main current_head current_branch index_state worktree_state

  origin_main="$(git -C "$PROJECT_ROOT" rev-parse refs/remotes/origin/main 2>/dev/null || printf '%s' UNAVAILABLE)"
  current_head="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || printf '%s' UNAVAILABLE)"
  current_branch="$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || printf '%s' DETACHED)"
  if git -C "$PROJECT_ROOT" diff --cached --quiet; then
    index_state="EMPTY"
  else
    index_state="HAS_USER_STAGED_CHANGES"
  fi
  worktree_state="$(git -C "$PROJECT_ROOT" status --porcelain=v1 --untracked-files=no 2>/dev/null || true)"

  install -d -m 0700 -- "$RUN_LOG_DIR"
  install -m 0600 /dev/null "$CONTEXT_FILE"
  {
    printf '%s\n' 'SecMon P2 runner sanitized context'
    printf 'Time: %s\n' "$(date --iso-8601=seconds)"
    printf 'Host: %s\n' "$(hostname 2>/dev/null || printf '%s' UNKNOWN)"
    printf 'Project root: %s\n' "$PROJECT_ROOT"
    printf 'origin/main HEAD: %s\n' "$origin_main"
    printf 'Current branch: %s\n' "${current_branch:-DETACHED}"
    printf 'Current HEAD: %s\n' "$current_head"
    printf 'Index state: %s\n' "$index_state"
    printf 'Tracked worktree changes (untracked names suppressed):\n%s\n' "$worktree_state"
    printf 'P1 final report: %s\n' "$P1_FINAL_REPORT"
    printf 'P1 last program report: %s\n' "$P1_LAST_PROGRAM_REPORT"
    printf 'P1 report commit: %s\n' "$P1_REPORT_COMMIT"
    printf 'P1 last program/tested code HEAD: %s\n' "$P1_TESTED_CODE_HEAD"
    printf 'P1 final status: %s\n' "$P1_STATUS"
    printf 'P2 mode: %s\n' "$P1_MODE"
    printf 'P2 technical preflight: %s\n' "$P2_TECHNICAL_PREFLIGHT_STATUS"
    printf 'P2 human start authorization: %s\n' "$P2_HUMAN_START_AUTHORIZATION"
    printf 'P2 P1 dependency status: %s\n' "$P2_P1_DEPENDENCY_STATUS"
    printf 'Allow Git push: %s\n' "$ALLOW_GIT_PUSH"
    printf 'Allow GitHub Issue update: %s\n' "$ALLOW_GITHUB_ISSUE_UPDATE"
    printf 'Allow Hermes notification: %s\n' "$ALLOW_HERMES_NOTIFY"
    printf '%s\n' 'No environment-file contents were read by the runner.'
  } >"$CONTEXT_FILE"
  chmod 0600 -- "$CONTEXT_FILE"
  assert_no_secret_pattern "$CONTEXT_FILE" \
    || die_before_agents "secret pattern detected in sanitized context"
}

run_stage() {
  local log_file="$1"
  shift

  install -m 0600 /dev/null "$log_file"
  set +e
  "$@" >"$log_file" 2>&1
  RUN_RC=$?
  set -e
  if ! assert_no_secret_pattern "$log_file"; then
    STOP_RESULT="P2_SECRET_GATE_BLOCKED"
    STOP_NEXT="Review the private log through an approved incident process; do not print it."
    notify_and_exit 24
  fi
}

require_report_marker() {
  local report="$1"
  local expected="$2"
  local actual

  [[ -f "$report" ]] || {
    STOP_RESULT="P2_REPORT_MISSING"
    STOP_NEXT="Do not advance; inspect the private Agent log and repair the task contract."
    notify_and_exit 23
  }
  assert_no_secret_pattern "$report" || {
    STOP_RESULT="P2_SECRET_GATE_BLOCKED"
    STOP_NEXT="Do not advance; quarantine the report without printing its contents."
    notify_and_exit 24
  }
  actual="$(last_line "$report" || true)"
  [[ "$actual" == "$expected" ]] || {
    STOP_RESULT="P2_INVALID_STAGE_MARKER"
    STOP_NEXT="Do not advance; the exact required final report marker is absent."
    notify_and_exit 23
  }
}

run_agent_1() {
  codex exec \
    -C "$PROJECT_ROOT" \
    --ephemeral \
    -m "$CODEX_MODEL" \
    -c 'model_reasoning_effort="xhigh"' \
    -c 'approval_policy="never"' \
    -s workspace-write \
    - <"$TASK_1"
}

run_agent_2() {
  claude -p --model "$CLAUDE_MODEL" \
    "$(<"$TASK_2")" \
    --effort max \
    --no-session-persistence \
    --output-format json \
    --allowedTools 'Read,Glob,Grep,Bash,Write'
}

run_agent_3() {
  # The installed AGY profile expresses the requested Gemini 3.5 Flash / High
  # combination; the task/report must still print both human-readable values.
  agy -p \
    --model "$AGY_PROFILE" \
    --mode accept-edits \
    --print-timeout 90m \
    "$(<"$TASK_3")"
}

verify_claude_model() {
  local json_log="$1"
  python3 - "$json_log" "$CLAUDE_MODEL" <<'PY'
import json
import pathlib
import sys

try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    models = set(data.get("modelUsage", {}))
except (OSError, ValueError, TypeError):
    raise SystemExit(1)

raise SystemExit(0 if models == {sys.argv[2]} else 1)
PY
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
      printf 'P2 runner blocked: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

if ! require_boolean_value SECMON_ALLOW_GIT_PUSH "$ALLOW_GIT_PUSH" \
  || ! require_boolean_value \
    SECMON_ALLOW_GITHUB_ISSUE_UPDATE "$ALLOW_GITHUB_ISSUE_UPDATE" \
  || ! require_boolean_value SECMON_ALLOW_HERMES_NOTIFY "$ALLOW_HERMES_NOTIFY"; then
  P2_TECHNICAL_PREFLIGHT_STATUS="BLOCKED"
  print_p2_status
  exit 20
fi
export SECMON_ALLOW_GIT_PUSH="$ALLOW_GIT_PUSH"
export SECMON_ALLOW_GITHUB_ISSUE_UPDATE="$ALLOW_GITHUB_ISSUE_UPDATE"
export SECMON_ALLOW_HERMES_NOTIFY="$ALLOW_HERMES_NOTIFY"

set +e
run_technical_preflight
P2_PREFLIGHT_RC=$?
set -e
print_p2_status

if [[ "$PREFLIGHT_ONLY" == "true" ]]; then
  exit "$P2_PREFLIGHT_RC"
fi

if [[ $P2_PREFLIGHT_RC -ne 0 ]]; then
  exit "$P2_PREFLIGHT_RC"
fi

cd "$PROJECT_ROOT"
install -d -m 0700 -- "$RUN_LOG_DIR"
if ! git -C "$PROJECT_ROOT" fetch --quiet --prune origin >/dev/null 2>&1; then
  die_before_agents "origin fetch failed; no Agent was started"
fi

record_p1_evidence
if [[ "$P1_STATUS" == "PASS" ]]; then
  P2_P1_DEPENDENCY_STATUS="PASS"
else
  P2_P1_DEPENDENCY_STATUS="NOT_PASSED"
  printf '%s\n' 'P2 full execution blocked: P1_FORMAL_ACCEPTANCE is not PASS.' >&2
  print_p2_status
  exit 21
fi

if ! request_p2_start_authorization; then
  P2_HUMAN_START_AUTHORIZATION="DENIED"
  printf '%s\n' 'P2 authorization denied; no Agent was started.' >&2
  print_p2_status
  exit 22
fi

P2_HUMAN_START_AUTHORIZATION="GRANTED"
P2_AGENT_EXECUTION_STATUS="STARTED"
P2_AGENT_START_COUNT=1
P2_RUNTIME_GATE_STATUS="RUNNING"
write_context

printf 'SecMon P2 mode: %s\n' "$P1_MODE"
printf 'P1 final status: %s\n' "$P1_STATUS"
printf 'Sanitized context: %s\n' "$CONTEXT_FILE"
printf '%s\n' 'Agent output is private; only sanitized gate results will be shown.'

STOP_STAGE="Agent 1 — Codex P2 implementation"
STOP_RESULT="P2_AGENT_1_BLOCKED"
STOP_REPORT="$REPORT_1"
STOP_NEXT="Agent 2 was not started. Review Agent 1 report and private run log."
run_stage "$RUN_LOG_DIR/01_codex_p2.log" run_agent_1
if [[ -f "$REPORT_1" && "$(last_line "$REPORT_1" || true)" == 'STAGE_RESULT: BLOCKED' ]]; then
  STOP_RESULT="P2_AGENT_1_BLOCKED"
  STOP_NEXT="Agent 1 reported BLOCKED; Agent 2 was not started."
  notify_and_exit 20
fi
require_report_marker "$REPORT_1" 'STAGE_RESULT: READY_FOR_GLM52_REVIEW'
grep -Fqx 'ACTIVE_MODEL: gpt-5.6-luna' "$REPORT_1" || {
  STOP_RESULT="P2_AGENT_1_MODEL_EVIDENCE_MISSING"
  STOP_NEXT="Agent 2 was not started because Agent 1 did not record the fixed active model."
  notify_and_exit 20
}
grep -Fqx 'REASONING_EFFORT: xhigh' "$REPORT_1" || {
  STOP_RESULT="P2_AGENT_1_REASONING_EVIDENCE_MISSING"
  STOP_NEXT="Agent 2 was not started because Agent 1 did not record xhigh reasoning evidence."
  notify_and_exit 20
}
if [[ "$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || true)" != "$FEATURE_BRANCH" ]]; then
  STOP_RESULT="P2_WRONG_FEATURE_BRANCH"
  STOP_NEXT="Agent 2 was not started because P2 implementation is not on feature/secmon-p2-api-auth."
  notify_and_exit 20
fi
if [[ "$RUN_RC" -ne 0 ]]; then
  STOP_RESULT="P2_AGENT_1_BLOCKED"
  STOP_NEXT="Agent 1 claimed readiness but exited non-zero; Agent 2 was not started."
  notify_and_exit 20
fi

STOP_STAGE="Agent 2 — GLM-5.2 independent security review"
STOP_RESULT="P2_AGENT_2_REJECTED"
STOP_REPORT="$REPORT_2"
STOP_NEXT="Agent 3 was not started. Review the independent security report."
run_stage "$RUN_LOG_DIR/02_glm52_security_review.json" run_agent_2
if ! verify_claude_model "$RUN_LOG_DIR/02_glm52_security_review.json"; then
  STOP_RESULT="P2_AGENT_2_MODEL_MISMATCH"
  STOP_NEXT="Actual active model was not exactly glm-5.2; no fallback is permitted."
  notify_and_exit 21
fi
if [[ -f "$REPORT_2" && "$(last_line "$REPORT_2" || true)" == 'STAGE_RESULT: REJECTED' ]]; then
  STOP_RESULT="P2_AGENT_2_REJECTED"
  STOP_NEXT="Agent 2 reported REJECTED; Agent 3 was not started."
  notify_and_exit 21
fi
require_report_marker "$REPORT_2" 'STAGE_RESULT: APPROVE_FOR_AGY'
grep -Fqx 'ACTIVE_MODEL: glm-5.2' "$REPORT_2" || {
  STOP_RESULT="P2_AGENT_2_MODEL_EVIDENCE_MISSING"
  STOP_NEXT="Agent 3 was not started because the report lacks exact model evidence."
  notify_and_exit 21
}
grep -Fqx 'BLOCKER_COUNT: 0' "$REPORT_2" || {
  STOP_RESULT="P2_AGENT_2_BLOCKER_PRESENT"
  STOP_NEXT="Agent 3 was not started because the review did not prove zero Blockers."
  notify_and_exit 21
}
grep -Fqx 'HIGH_COUNT: 0' "$REPORT_2" || {
  STOP_RESULT="P2_AGENT_2_HIGH_PRESENT"
  STOP_NEXT="Agent 3 was not started because the review did not prove zero High findings."
  notify_and_exit 21
}
if [[ "$RUN_RC" -ne 0 ]]; then
  STOP_RESULT="P2_AGENT_2_REJECTED"
  STOP_NEXT="Agent 2 claimed approval but exited non-zero; Agent 3 was not started."
  notify_and_exit 21
fi

STOP_STAGE="Agent 3 — AGY API runtime verification"
STOP_RESULT="P2_RUNTIME_GATE_NOT_PASSED"
STOP_REPORT="$REPORT_3"
STOP_NEXT="Review the runtime report; Agent 4 was not started."
run_stage "$RUN_LOG_DIR/03_agy_api_runtime.log" run_agent_3
[[ "$(first_nonempty_line "$RUN_LOG_DIR/03_agy_api_runtime.log")" == \
  "AGY_ACTIVE_MODEL: $AGY_MODEL" ]] || {
  STOP_RESULT="P2_AGENT_3_MODEL_MISMATCH"
  STOP_NEXT="AGY did not prove Gemini 3.5 Flash as the first response line; no fallback is permitted."
  notify_and_exit 22
}
assert_no_secret_pattern "$REPORT_3" || {
  STOP_RESULT="P2_SECRET_GATE_BLOCKED"
  STOP_NEXT="Quarantine the runtime report without printing its contents; Agent 4 was not started."
  notify_and_exit 24
}
grep -Fqx 'AGY_ACTIVE_MODEL: Gemini 3.5 Flash' "$REPORT_3" || {
  STOP_RESULT="P2_AGENT_3_MODEL_EVIDENCE_MISSING"
  STOP_NEXT="The runtime report lacks exact Gemini 3.5 Flash evidence; Agent 4 was not started."
  notify_and_exit 22
}
grep -Fqx 'AGY_REASONING: High' "$REPORT_3" || {
  STOP_RESULT="P2_AGENT_3_REASONING_EVIDENCE_MISSING"
  STOP_NEXT="The runtime report lacks exact High reasoning evidence; Agent 4 was not started."
  notify_and_exit 22
}
STAGE_3_RESULT="$(last_line "$REPORT_3" 2>/dev/null || true)"
case "$STAGE_3_RESULT" in
  'STAGE_RESULT: P2_RUNTIME_GATE_NOT_PASSED')
    STOP_RESULT="P2_RUNTIME_GATE_NOT_PASSED"
    STOP_NEXT="Agent 3 did not pass the runtime gate; Agent 4 was not started."
    notify_and_exit 22
    ;;
  'STAGE_RESULT: STAGING_RUNTIME_PASS_P1_BLOCKED')
    require_report_marker "$REPORT_3" 'STAGE_RESULT: STAGING_RUNTIME_PASS_P1_BLOCKED'
    [[ "$P1_MODE" == "DEVELOPMENT_ONLY" ]] || {
      STOP_RESULT="P2_INVALID_P1_MODE_EVIDENCE"
      STOP_NEXT="The staging marker conflicts with RELEASE_ELIGIBLE P1 evidence; Agent 4 was not started."
      notify_and_exit 22
    }
    [[ "$RUN_RC" -eq 0 ]] || {
      STOP_RESULT="P2_RUNTIME_GATE_NOT_PASSED"
      STOP_NEXT="Agent 3 claimed staging pass but exited non-zero; Agent 4 was not started."
      notify_and_exit 22
    }
    STOP_RESULT="STAGING_RUNTIME_PASS_P1_BLOCKED"
    STOP_NEXT="P2 is technically ready only for staging; obtain formal P1 Release Gate PASS before Agent 4."
    notify_and_exit 0
    ;;
  'STAGE_RESULT: P2_RUNTIME_GATE_PASS')
    require_report_marker "$REPORT_3" 'STAGE_RESULT: P2_RUNTIME_GATE_PASS'
    [[ "$P1_MODE" == "RELEASE_ELIGIBLE" ]] || {
      STOP_RESULT="STAGING_RUNTIME_PASS_P1_BLOCKED"
      STOP_NEXT="Agent 3 claimed a production pass without trusted P1 evidence; Agent 4 was not started."
      notify_and_exit 22
    }
    [[ "$RUN_RC" -eq 0 ]] || {
      STOP_RESULT="P2_RUNTIME_GATE_NOT_PASSED"
      STOP_NEXT="Agent 3 claimed a production pass but exited non-zero; Agent 4 was not started."
      notify_and_exit 22
    }
    STOP_RESULT="P2_RUNTIME_GATE_PASS"
    STOP_NEXT='Human must explicitly invoke $review-secmon-p2-release in a new Codex session.'
    notify_and_exit 0
    ;;
  *)
    STOP_RESULT="P2_INVALID_STAGE_MARKER"
    STOP_NEXT="Agent 3 report marker was not one of the three allowed outcomes; Agent 4 was not started."
    notify_and_exit 22
    ;;
esac
