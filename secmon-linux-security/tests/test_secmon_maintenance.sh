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
if rg -Fq 'ABORT_APPROVED_MANIFEST_OR_DEPLOYED_HASH_MISMATCH' "$runtime"; then
  fail 'runtime helper retains generic manifest/deployed-hash abort'
fi
for gate in MANIFEST_METADATA APPROVED_HEAD RUNTIME_FILE_HASH SYSTEMD_UNIT_HASH MIGRATION_HASH; do
  rg -Fq "${gate}_GATE=PASS" "$runtime" \
    || fail "runtime helper lacks granular ${gate} gate output"
done
for marker in MANIFEST_METADATA_INVALID APPROVED_HEAD_MISMATCH RUNTIME_FILE_HASH_MISMATCH SYSTEMD_UNIT_HASH_MISMATCH MIGRATION_HASH_MISMATCH; do
  rg -Fq "abort $marker" "$runtime" \
    || fail "runtime helper lacks granular abort: $marker"
done
rg -Fq 'APPROVED_RUNTIME_HEAD=21eb7787ce4e8d8cd16ed47e7533aa21d424f643' "$approval_manifest" \
  || fail 'approval manifest has incorrect approved runtime head'
for required_kind in RUNTIME RUNNER MIGRATION UNIT; do
  rg -Fq "$required_kind|" "$approval_manifest" \
    || fail "approval manifest lacks $required_kind records"
done
rg -Fq 'verify_restart_policy || abort RESTART_POLICY_MISMATCH' "$runtime" \
  || fail 'runtime helper lacks RestartUSec policy gate'
pass RUNTIME_POLICY_AND_ROOT_MANIFEST_GATES

if ! /bin/bash -p -c '
  set -Eeuo pipefail
  source "$1"
  ! nrestarts_increased 2212 0
  ! nrestarts_increased 0 0
  nrestarts_increased 0 1
  [[ $(select_runtime_mode active running 1922369) == VERIFY_ONLY ]]
  [[ $(select_runtime_mode inactive dead 0) == RECOVERY ]]
  ! select_runtime_mode failed failed 0 >/dev/null
  ! select_runtime_mode activating auto-restart 0 >/dev/null
' bash "$runtime"; then
  fail 'NRestarts comparison or runtime-mode selection failed'
fi
if ! /usr/bin/awk '
  /if \[\[ "\$mode" == VERIFY_ONLY \]\]; then/ { verify = 1; next }
  verify && /^  else$/ { ended = 1; exit }
  verify && /systemctl (start|stop|restart|reset-failed)/ { invalid = 1 }
  END { exit (verify && ended && !invalid) ? 0 : 1 }
' "$runtime"; then
  fail 'VERIFY_ONLY branch can change service state'
fi
rg -Fq 'nrestarts_increased "$baseline_restarts" "$sample_restarts" && abort NRESTARTS_INCREASED' "$runtime" \
  || fail 'runtime helper does not use greater-than NRestarts comparison'
if rg -Fq '"$sample_restarts" == "$baseline_restarts"' "$runtime"; then
  fail 'runtime helper still treats any NRestarts change as an increase'
fi
pass VERIFY_ONLY_AND_NRESTARTS_GATES

# Exercise the exact validator with a complete, non-root fixture.  The copied
# helper retains parser and hash code unchanged; only root-owned metadata is
# mocked because an unprivileged test cannot create a root:root manifest.
fixture_dir=$(/usr/bin/mktemp -d /tmp/secmon-runtime-validator.XXXXXX)
trap '/bin/rm -rf -- "$fixture_dir"' EXIT
fixture_root="$fixture_dir/opt-secmon"
fixture_manifest="$fixture_dir/runtime-approved.manifest"
fixture_unit="$fixture_dir/secmon-collector.service"
fixture_helper="$fixture_dir/runtime-recovery"
/bin/mkdir -p "$fixture_root/database/migrations"
/bin/sed \
  -e "s|^readonly APPROVAL_MANIFEST=.*|readonly APPROVAL_MANIFEST=$fixture_manifest|" \
  -e "s|^readonly DEPLOYED_ROOT=.*|readonly DEPLOYED_ROOT=$fixture_root|" \
  -e "s|^readonly UNIT_FILE=.*|readonly UNIT_FILE=$fixture_unit|" \
  -e 's/^  manifest_metadata_is_secure "\$mode" || return 1$/  : # fixture metadata is validated separately below/' \
  "$runtime" >"$fixture_helper"
/bin/chmod 0700 "$fixture_helper"

if ! /bin/bash -p -c '
  set -Eeuo pipefail
  source "$1"
  for relative_path in "${RUNTIME_SOURCE_FILES[@]}"; do
    /bin/mkdir -p -- "$(/usr/bin/dirname -- "$DEPLOYED_ROOT/$relative_path")"
    printf "fixture:%s\\n" "$relative_path" >"$DEPLOYED_ROOT/$relative_path"
  done
  printf "fixture:runner\\n" >"$DEPLOYED_ROOT/$RUNNER_PATH"
  for migration in "${APPROVED_MIGRATIONS[@]}"; do
    printf "fixture:%s\\n" "$migration" >"$DEPLOYED_ROOT/database/migrations/$migration"
  done
  printf "fixture:unit\\n" >"$UNIT_FILE"
  {
    printf "APPROVED_RUNTIME_HEAD=%s\\n" "$APPROVED_RUNTIME_HEAD"
    for relative_path in "${RUNTIME_SOURCE_FILES[@]}"; do
      printf "RUNTIME|%s|%s\\n" "$relative_path" "$(/usr/bin/sha256sum "$DEPLOYED_ROOT/$relative_path" | /usr/bin/cut -d " " -f 1)"
    done
    printf "RUNNER|%s|%s\\n" "$RUNNER_PATH" "$(/usr/bin/sha256sum "$DEPLOYED_ROOT/$RUNNER_PATH" | /usr/bin/cut -d " " -f 1)"
    for migration in "${APPROVED_MIGRATIONS[@]}"; do
      printf "MIGRATION|%s|%s\\n" "$migration" "$(/usr/bin/sha256sum "$DEPLOYED_ROOT/database/migrations/$migration" | /usr/bin/cut -d " " -f 1)"
    done
    printf "UNIT|systemd/secmon-collector.service|%s\\n" "$(/usr/bin/sha256sum "$UNIT_FILE" | /usr/bin/cut -d " " -f 1)"
  } >"$APPROVAL_MANIFEST"
  verify_approved_deployed_hashes
' bash "$fixture_helper" >"$fixture_dir/pass.out"; then
  fail 'complete PASS fixture was rejected by validator'
fi
for gate in MANIFEST_METADATA APPROVED_HEAD RUNTIME_FILE_HASH SYSTEMD_UNIT_HASH MIGRATION_HASH; do
  rg -Fq "${gate}_GATE=PASS" "$fixture_dir/pass.out" \
    || fail "complete fixture omitted ${gate} pass marker"
done

# Each altered fixture must stop at its own gate.  Restore from a fresh PASS
# fixture before the next case to prevent one mutation masking another.
/bin/sed -i 's/^APPROVED_RUNTIME_HEAD=.*/APPROVED_RUNTIME_HEAD=0000000000000000000000000000000000000000/' "$fixture_manifest"
set +e
head_output=$(/bin/bash -p -c 'source "$1"; verify_approved_deployed_hashes' bash "$fixture_helper" 2>&1)
head_rc=$?
set -e
[[ $head_rc -ne 0 && "$head_output" == *ABORT_APPROVED_HEAD_MISMATCH* ]] \
  || fail 'approved-head mutation was accepted'
/bin/sed -i 's/^APPROVED_RUNTIME_HEAD=.*/APPROVED_RUNTIME_HEAD=21eb7787ce4e8d8cd16ed47e7533aa21d424f643/' "$fixture_manifest"

printf 'tampered runtime\n' >"$fixture_root/backend/config.py"
set +e
runtime_output=$(/bin/bash -p -c 'source "$1"; verify_approved_deployed_hashes' bash "$fixture_helper" 2>&1)
runtime_rc=$?
set -e
[[ $runtime_rc -ne 0 && "$runtime_output" == *ABORT_RUNTIME_FILE_HASH_MISMATCH* ]] \
  || fail 'runtime-file hash mutation was accepted'

# Rebuild the fixture once, then independently corrupt a migration and unit.
/bin/rm -rf -- "$fixture_root" "$fixture_manifest" "$fixture_unit"
if ! /bin/bash -p -c '
  set -Eeuo pipefail
  source "$1"
  /bin/mkdir -p "$DEPLOYED_ROOT/database/migrations"
  for relative_path in "${RUNTIME_SOURCE_FILES[@]}"; do /bin/mkdir -p "$(/usr/bin/dirname "$DEPLOYED_ROOT/$relative_path")"; printf x >"$DEPLOYED_ROOT/$relative_path"; done
  printf x >"$DEPLOYED_ROOT/$RUNNER_PATH"
  for migration in "${APPROVED_MIGRATIONS[@]}"; do printf x >"$DEPLOYED_ROOT/database/migrations/$migration"; done
  printf x >"$UNIT_FILE"
  { printf "APPROVED_RUNTIME_HEAD=%s\\n" "$APPROVED_RUNTIME_HEAD"; for relative_path in "${RUNTIME_SOURCE_FILES[@]}"; do printf "RUNTIME|%s|%s\\n" "$relative_path" "$(/usr/bin/sha256sum "$DEPLOYED_ROOT/$relative_path" | /usr/bin/cut -d " " -f 1)"; done; printf "RUNNER|%s|%s\\n" "$RUNNER_PATH" "$(/usr/bin/sha256sum "$DEPLOYED_ROOT/$RUNNER_PATH" | /usr/bin/cut -d " " -f 1)"; for migration in "${APPROVED_MIGRATIONS[@]}"; do printf "MIGRATION|%s|%s\\n" "$migration" "$(/usr/bin/sha256sum "$DEPLOYED_ROOT/database/migrations/$migration" | /usr/bin/cut -d " " -f 1)"; done; printf "UNIT|systemd/secmon-collector.service|%s\\n" "$(/usr/bin/sha256sum "$UNIT_FILE" | /usr/bin/cut -d " " -f 1)"; } >"$APPROVAL_MANIFEST"
' bash "$fixture_helper"; then
  fail 'unable to rebuild validator fixture'
fi
printf 'tampered migration\n' >"$fixture_root/database/migrations/005_ssh_parser.sql"
set +e
migration_output=$(/bin/bash -p -c 'source "$1"; verify_approved_deployed_hashes' bash "$fixture_helper" 2>&1)
migration_rc=$?
set -e
[[ $migration_rc -ne 0 && "$migration_output" == *ABORT_MIGRATION_HASH_MISMATCH* ]] \
  || fail 'migration hash mutation was accepted'

printf x >"$fixture_root/database/migrations/005_ssh_parser.sql"
# Its manifest still contains the old digest, so rebuild just the PASS fixture
# before checking an independently tampered unit.
/bin/sed -i 's/^MIGRATION|005_ssh_parser.sql|.*/MIGRATION|005_ssh_parser.sql|'"$(/usr/bin/sha256sum "$fixture_root/database/migrations/005_ssh_parser.sql" | /usr/bin/cut -d ' ' -f 1)"'/' "$fixture_manifest"
printf 'tampered unit\n' >"$fixture_unit"
set +e
unit_output=$(/bin/bash -p -c 'source "$1"; verify_approved_deployed_hashes' bash "$fixture_helper" 2>&1)
unit_rc=$?
set -e
[[ $unit_rc -ne 0 && "$unit_output" == *ABORT_SYSTEMD_UNIT_HASH_MISMATCH* ]] \
  || fail 'unit hash mutation was accepted'

if ! /bin/bash -p -c 'source "$1"; manifest_metadata_is_secure 0:0:640 && ! manifest_metadata_is_secure 0:0:660' bash "$runtime"; then
  fail 'manifest writable-mode rejection failed'
fi
verify_line=$(/usr/bin/grep -n '^  verify_approved_deployed_hashes$' "$runtime" | /usr/bin/cut -d : -f 1)
start_line=$(/usr/bin/grep -n 'systemctl start' "$runtime" | /usr/bin/head -n 1 | /usr/bin/cut -d : -f 1)
[[ -n "$verify_line" && -n "$start_line" && "$verify_line" -lt "$start_line" ]] \
  || fail 'systemctl start is not after all validator gates'
pass RUNTIME_HASH_VALIDATOR_FIXTURES

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
