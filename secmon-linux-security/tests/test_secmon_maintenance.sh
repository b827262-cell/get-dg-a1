#!/bin/bash
# Static and fail-closed interface tests.  They never invoke a privileged helper.
set -Eeuo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
controller="$repo_root/scripts/secmon-maintenance"
backup="$repo_root/scripts/privileged/backup-db"
migrate="$repo_root/scripts/privileged/migrate-db"
runtime="$repo_root/scripts/privileged/runtime-recovery"
approval_manifest="$repo_root/scripts/privileged/runtime-approved.manifest"
sudoers_example="$repo_root/docs/secmon-codex-sudoers.example"

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }
expect_failure() {
  set +e
  "$@" >/dev/null 2>&1
  local rc=$?
  set -e
  [[ $rc -ne 0 ]] || fail "expected failure: $*"
}

for file in "$controller" "$backup" "$migrate" "$runtime" "$approval_manifest" "$sudoers_example"; do
  [[ -f "$file" ]] || fail "missing required design file: $file"
done

for script in "$controller" "$backup" "$migrate" "$runtime"; do
  /bin/bash -n "$script" || fail "bash syntax failed: $script"
done
pass SHELL_BASH_N

# Source only the dispatcher function definitions; main is guarded for tests.
# shellcheck disable=SC1090
source "$controller"
for command_name in status backup-db migrate-db runtime-recovery; do
  validate_subcommand "$command_name" || fail "valid subcommand rejected: $command_name"
done
expect_failure validate_subcommand unknown
pass LEGAL_SUBCOMMANDS

authorization_is_current 2027-07-18 || fail 'expiry boundary rejected'
expect_failure authorization_is_current 2027-07-19
expiry_output=$(authorization_gate 2027-07-19 2>&1 || true)
[[ "$expiry_output" == AUTHORIZATION_EXPIRED ]] || fail 'expiry marker missing'
pass EXPIRY_GATE

# Load the runtime helper in a separate shell to avoid its fixed readonly
# constants colliding with the dispatcher constants sourced above.
if ! /bin/bash -p -c '
  set -Eeuo pipefail
  source "$1"
  for restart_value in 5s 5000ms 5000000us; do
    [[ $(normalize_duration_usec "$restart_value") == 5000000 ]] || exit 1
  done
  ! normalize_duration_usec "" >/dev/null
  ! normalize_duration_usec invalid >/dev/null
' bash "$runtime"; then
  fail 'RestartUSec normalization failed'
fi
if rg -n 'RestartSec' "$runtime" >/dev/null; then
  fail 'runtime helper reads deprecated RestartSec property'
fi
rg -Fq 'show --value -p "$1" "$SERVICE"' "$runtime" \
  || fail 'runtime helper does not use formal systemctl show property syntax'
if rg -n '/usr/bin/git|git[[:space:]]+-C|git show' "$runtime" >/dev/null; then
  fail 'runtime helper trusts Git at privileged runtime'
fi
rg -Fq 'readonly APPROVAL_MANIFEST=/usr/local/libexec/secmon/runtime-approved.manifest' "$runtime" \
  || fail 'runtime helper lacks fixed root-owned approval manifest path'
rg -Fq 'verify_approved_deployed_hashes || abort APPROVED_MANIFEST_OR_DEPLOYED_HASH_MISMATCH' "$runtime" \
  || fail 'runtime helper lacks approved manifest/deployed-hash gate'
rg -Fq 'APPROVED_RUNTIME_HEAD=21eb7787ce4e8d8cd16ed47e7533aa21d424f643' "$approval_manifest" \
  || fail 'approval manifest has incorrect approved runtime head'
for required_kind in RUNTIME RUNNER MIGRATION UNIT; do
  rg -Fq "$required_kind|" "$approval_manifest" \
    || fail "approval manifest lacks $required_kind records"
done
rg -Fq 'verify_restart_policy || abort RESTART_POLICY_MISMATCH' "$runtime" \
  || fail 'runtime helper lacks RestartUSec policy gate'
pass RUNTIME_POLICY_AND_ROOT_MANIFEST_GATES

expect_failure "$controller" unknown
expect_failure "$controller" status extra
expect_failure "$controller" /tmp/untrusted-script
injection_marker=$(/usr/bin/mktemp -u /tmp/secmon-maintenance-injection.XXXXXX)
[[ ! -e "$injection_marker" ]] || fail 'unable to allocate absent injection sentinel'
expect_failure "$controller" "status; /usr/bin/touch $injection_marker"
[[ ! -e "$injection_marker" ]] || fail 'command injection executed'
pass ARGUMENT_AND_INJECTION_REJECTION

if [[ $(/usr/bin/id -u) -ne 0 ]]; then
  nonroot_output=$("$controller" status 2>&1 || true)
  [[ "$nonroot_output" == ROOT_REQUIRED ]] || fail 'non-root direct execution was not rejected'
  pass NONROOT_REJECTION
else
  printf 'SKIP: NONROOT_REJECTION (test runner is root)\n'
fi

if rg -n 'eval|source[[:space:]]|/tmp' "$controller" "$backup" "$migrate" "$runtime" >/dev/null; then
  fail 'controller or helper permits eval, source, or /tmp execution'
fi
if ! /usr/bin/awk '
  /require_service_inactive/ { seen = 1 }
  /"\$BACKUP_HELPER"/ && !seen { exit 1 }
  END { exit seen ? 0 : 1 }
' "$migrate"; then
  fail 'migrate-db does not enforce inactive-service gate before backup/migration'
fi
pass INACTIVE_SERVICE_AND_TMP_GATES

if [[ -x /usr/bin/visudo ]]; then
  /usr/bin/visudo -cf "$sudoers_example" >/dev/null || fail 'sudoers syntax invalid'
  pass SUDOERS_SYNTAX
else
  printf 'SKIP: SUDOERS_SYNTAX (visudo not installed)\n'
fi

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck "$controller" "$backup" "$migrate" "$runtime" "$BASH_SOURCE" \
    || fail 'shellcheck failed'
  pass SHELLCHECK
else
  printf 'SKIP: SHELLCHECK (not installed)\n'
fi

printf 'TEST_RESULT=PASS\n'
