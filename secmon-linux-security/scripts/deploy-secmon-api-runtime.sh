#!/usr/bin/env bash

set -Eeuo pipefail

readonly SOURCE_ROOT="/home/b822726/project/get-dg-project/secmon-linux-security/secmon-linux-security"
readonly APP_ROOT="/opt/secmon"
readonly VENV="${APP_ROOT}/.venv"
readonly PYTHON="${VENV}/bin/python"
readonly UVICORN="${VENV}/bin/uvicorn"
readonly ENV_FILE="/etc/secmon/secmon.env"
readonly SERVICE="secmon-api.service"

usage() {
  printf 'Usage: %s --check|--install\n' "$0"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  return 1
}

check_source() {
  test -f "${SOURCE_ROOT}/pyproject.toml" || fail "source pyproject.toml is missing"
  test -f "${SOURCE_ROOT}/backend/app.py" || fail "source backend/app.py is missing"
  grep -Fq '"uvicorn>=0.30,<1"' "${SOURCE_ROOT}/pyproject.toml" \
    || fail "pyproject.toml does not declare the production uvicorn dependency"
}

check_target() {
  test -d "${APP_ROOT}" || fail "${APP_ROOT} is missing; install requires the fixed target"
  test -f "${APP_ROOT}/pyproject.toml" || fail "deployed pyproject.toml is missing"
  test -f "${APP_ROOT}/backend/app.py" || fail "deployed backend/app.py is missing"
  test -f "${ENV_FILE}" || fail "${ENV_FILE} is missing"
  test "$(stat -c '%U:%G' "${APP_ROOT}")" = 'secmon:secmon' || fail "${APP_ROOT} is not owned by secmon:secmon"
  test "$(stat -c '%U:%G' /var/lib/secmon)" = 'secmon:secmon' || fail "/var/lib/secmon is not owned by secmon:secmon"
  test "$(stat -c '%U:%G' /var/log/secmon)" = 'secmon:secmon' || fail "/var/log/secmon is not owned by secmon:secmon"
  test -x "${PYTHON}" || fail "${PYTHON} is missing or not executable"
  test -x "${UVICORN}" || fail "${UVICORN} is missing or not executable"
}

check_runtime() {
  printf 'IMPORT_SMOKE: '
  (cd "${APP_ROOT}" && PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" -c \
    'import backend.app; assert backend.app.app is not None') \
    && printf 'PASS\n' || { printf 'FAIL\n'; return 1; }
  printf 'UVICORN_EXECUTABLE: '
  "${UVICORN}" --version >/dev/null && printf 'PASS\n' || { printf 'FAIL\n'; return 1; }
}

check() {
  printf 'MODE: check\n'
  check_source
  check_target
  check_runtime
  printf 'DEPLOYMENT_CHECK: PASS\n'
}

install_runtime() {
  test "${EUID}" -eq 0 || fail '--install must be run by an operator as root'
  check_source
  id secmon >/dev/null 2>&1 || fail 'secmon user is missing'
  getent group secmon >/dev/null 2>&1 || fail 'secmon group is missing'
  test -f "${ENV_FILE}" || fail "${ENV_FILE} is missing"

  install -d -o secmon -g secmon -m 0755 "${APP_ROOT}"
  cp -a "${SOURCE_ROOT}/backend" "${SOURCE_ROOT}/database" "${SOURCE_ROOT}/frontend" \
    "${SOURCE_ROOT}/config" "${SOURCE_ROOT}/systemd" "${APP_ROOT}/"
  install -o secmon -g secmon -m 0644 "${SOURCE_ROOT}/pyproject.toml" "${APP_ROOT}/pyproject.toml"
  install -o secmon -g secmon -m 0644 "${SOURCE_ROOT}/Makefile" "${APP_ROOT}/Makefile"
  chown -R secmon:secmon "${APP_ROOT}/backend" "${APP_ROOT}/database" \
    "${APP_ROOT}/frontend" "${APP_ROOT}/config" "${APP_ROOT}/systemd" \
    "${APP_ROOT}/pyproject.toml" "${APP_ROOT}/Makefile"

  if [ ! -x "${PYTHON}" ]; then
    runuser -u secmon -- /usr/bin/python3 -m venv "${VENV}"
  fi
  runuser -u secmon -- "${PYTHON}" -m pip install --upgrade pip
  runuser -u secmon -- "${PYTHON}" -m pip install "${APP_ROOT}"
  chown -R secmon:secmon "${VENV}"
  check_target
  check_runtime
  printf 'DEPLOYMENT_INSTALL: PASS\n'
  printf 'NOTE: %s was not started or reloaded by this script.\n' "${SERVICE}"
}

main() {
  test "$#" -eq 1 || { usage >&2; return 2; }
  case "$1" in
    --check) check ;;
    --install) install_runtime ;;
    *) usage >&2; return 2 ;;
  esac
}

main "$@"
