# SecMon API systemd deployment

## Discovered runtime contract

The repository and the installed `secmon-collector.service` establish the
following deployment contract:

- ASGI module: `backend.app:app`
- Application root / working directory: `/opt/secmon`
- User and group: `secmon:secmon`
- Environment file: `/etc/secmon/secmon.env`
- Python entry point: `/opt/secmon/.venv/bin/uvicorn`
- Bind address and port: `127.0.0.1:8080`
- Liveness endpoint: `GET /healthz`, expected `{"status":"ok"}`
- Readiness endpoint: `GET /readyz`, expected `{"status":"ready"}`
- Writable paths retained from the collector contract: `/var/lib/secmon`
  and `/var/log/secmon`

The API unit is fixed to these values. It does not contain credentials or
accept runtime service, command, bind-address, or port overrides.

## Application artifact and dependency preparation

The repository has no `uv.lock`, `poetry.lock`, or `requirements*.txt`; its
formal production dependency declaration is `pyproject.toml`, which includes
`uvicorn>=0.30,<1` and the complete FastAPI runtime dependency set. The
collector and API both use `/opt/secmon/.venv`.

The fixed-parameter preparation script is:

`scripts/deploy-secmon-api-runtime.sh`

It has two modes:

```bash
scripts/deploy-secmon-api-runtime.sh --check
scripts/deploy-secmon-api-runtime.sh --install
```

`--check` is read-only. It verifies the fixed `/opt/secmon` artifact,
`/etc/secmon/secmon.env`, `secmon:secmon` ownership of the application and
data directories, the venv Python, the Uvicorn executable, and an import
smoke test for `backend.app:app`. `--install` is an operator-only procedure:
it copies the fixed repository application artifact to `/opt/secmon`, creates
the venv if absent, and installs the complete dependencies from the deployed
`pyproject.toml` with pip. It never writes secrets and never invokes
`systemctl`, starts, restarts, enables, or reloads a service.

Final deployment evidence on 2026-07-21 recorded that
`/opt/secmon/backend/app.py`, `/opt/secmon/.venv/bin/python`, and
`/opt/secmon/.venv/bin/uvicorn` exist. The non-privileged command
`scripts/deploy-secmon-api-runtime.sh --check` completed with
`IMPORT_SMOKE: PASS`, `UVICORN_EXECUTABLE: PASS`, and
`DEPLOYMENT_CHECK: PASS`. No executable or symlink was fabricated.

## Unit

The source unit is:

`systemd/secmon-api.service`

Its fixed start command is:

```text
/opt/secmon/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8080
```

It runs as `secmon:secmon`, uses `NoNewPrivileges=true` and `PrivateTmp=true`,
and has the same `ProtectSystem`, `ProtectHome`, and `ReadWritePaths`
hardening pattern as `secmon-collector.service`.

## Operator-only installation and activation

Run these commands manually on the target host after reviewing the unit and
confirming that `/opt/secmon/.venv/bin/uvicorn` exists and is executable. The
commands below are instructions only; they were not run by this preparation
step.

```bash
cd /home/b822726/project/get-dg-project/secmon-linux-security
APP_ROOT="$PWD/secmon-linux-security"

sudo install -o root -g root -m 0644 \
  "$APP_ROOT/systemd/secmon-api.service" \
  /etc/systemd/system/secmon-api.service
sudo systemd-analyze verify /etc/systemd/system/secmon-api.service
sudo systemctl daemon-reload
sudo systemctl enable secmon-api.service
sudo systemctl start secmon-api.service
```

## Health and non-root verification

```bash
curl -fsS -D- http://127.0.0.1:8080/healthz
curl -fsS -D- http://127.0.0.1:8080/readyz

API_PID="$(systemctl show -p MainPID --value secmon-api.service)"
ps -o user,pid,ppid,args -p "$API_PID"
grep -E '^(Uid|Gid|CapEff|NoNewPrivs):' "/proc/$API_PID/status"
```

Expected identity is `secmon`, with `CapEff: 0000000000000000` and
`NoNewPrivs: 1`.

## Rollback and removal

Before activation, an operator may verify the unit and deployment contract:

```bash
cd /home/b822726/project/get-dg-project/secmon-linux-security
APP_ROOT="$PWD/secmon-linux-security"
bash -n "$APP_ROOT/scripts/deploy-secmon-api-runtime.sh"
"$APP_ROOT/scripts/deploy-secmon-api-runtime.sh" --check
sudo systemd-analyze verify "$APP_ROOT/systemd/secmon-api.service"
```

After reviewing successful check output, the operator-only activation sequence
is:

```bash
sudo install -o root -g root -m 0644 \
  "$APP_ROOT/systemd/secmon-api.service" \
  /etc/systemd/system/secmon-api.service
sudo systemctl daemon-reload
sudo systemctl enable secmon-api.service
sudo systemctl start secmon-api.service
```

Health, identity, and capability verification must then use the commands in
the next section. This preparation did not execute any of these commands.

To stop and disable the API after a failed or completed deployment:

```bash
sudo systemctl disable --now secmon-api.service
sudo rm /etc/systemd/system/secmon-api.service
sudo systemctl daemon-reload
```

Removing the unit does not delete `/var/lib/secmon`, `/var/log/secmon`, or the
environment file. Preserve those paths unless a separate, explicitly
approved data-retention procedure requires otherwise.

## Deployment verification evidence

The repository unit and Runtime Gate agree on the API unit, collector unit,
`127.0.0.1:8080`, `/healthz`, and `/readyz`. The following non-mutating
checks completed on 2026-07-21:

```text
systemd-analyze verify systemd/secmon-api.service: PASS
bash -n scripts/deploy-secmon-api-runtime.sh: PASS
scripts/deploy-secmon-api-runtime.sh --check: PASS
```

The operator-executed Runtime Gate separately recorded that
`secmon-api.service` is active, `/healthz` and `/readyz` return HTTP 200, and
the API process runs as `secmon` with `CapEff: 0000000000000000` and
`NoNewPrivs: 1`.
