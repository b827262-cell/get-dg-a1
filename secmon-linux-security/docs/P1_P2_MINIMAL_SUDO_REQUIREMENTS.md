# SecMon P1/P2 Minimal Sudo Requirements

## Policy

This document inventories sudo usage in the P1/P2 Runners, their directly
referenced Runtime contracts, and `scripts/deploy_helper.sh`. It does not grant
privileges, modify `/etc/sudoers`, or authorize a deployment or Runtime Gate.

Never configure or recommend:

```text
NOPASSWD: ALL
```

The preferred model is a trusted operator using an interactive sudo credential
cache, followed by exact `sudo -n` commands. Agents never receive, request,
read, or process the sudo password. If future unattended automation is needed,
its command-specific policy requires a separate security review outside this
repository change.

This inventory is not a sudoers file. The current acceptance design requires a
trusted operator with an existing approved sudo policy; it does not require any
new `NOPASSWD` grant. Paths shown below must be resolved and reviewed on the
production host before a separate command-specific sudoers policy is proposed.

## Human-only environment preparation

The operator may prepare the production environment file interactively with:

```bash
sudo install -d -o root -g root -m 0755 /etc/secmon
sudo test -e /etc/secmon/secmon.env || \
  sudo install -o root -g root -m 0600 /dev/null /etc/secmon/secmon.env
sudoedit /etc/secmon/secmon.env
sudo chown root:root /etc/secmon/secmon.env
sudo chmod 0600 /etc/secmon/secmon.env
```

These are setup operations performed by a human in a trusted terminal. They are
not Agent commands and are not candidates for unattended `NOPASSWD` access.
`sudoedit` keeps the credential out of command arguments; the populated file
must never enter Git.

## P1 Runner: Technical Preflight

The P1 Runner uses these commands only to establish technical readiness without
printing environment-file contents:

```bash
sudo -n true
sudo -v
sudo -n test -s /etc/secmon/secmon.env
sudo -n grep -Eq '<approved-token-format>' /etc/secmon/secmon.env
sudo -n grep -Eq '<approved-chat-id>' /etc/secmon/secmon.env
sudo -n grep -Eq '^SECMON_TELEGRAM_ENABLED=true$' /etc/secmon/secmon.env
sudo -n grep -Eq '^SECMON_AUTO_BLOCK_ENABLED=false$' /etc/secmon/secmon.env
sudo -n stat -c '%a' /etc/secmon/secmon.env
sudo -n stat -c '%U:%G' /etc/secmon/secmon.env
```

The first command is a non-interactive readiness probe. `sudo -v` is attempted
only in a trusted TTY to cache an operator-entered credential. `test`, `grep`,
and `stat` return boolean/metadata evidence; they must not print secret values.
The redacted placeholders above correspond to fixed checks in the Runner and
are intentionally not secret-bearing sudo-policy examples.

The corresponding privileged executables are `true`, `test`, `grep`, and
`stat`; the target is always `/etc/secmon/secmon.env`. The Runner supplies fixed
arguments and never invokes a privileged shell. Because the fixed Telegram
checks include approved identifiers, this document intentionally describes
their shape without duplicating those values.

Technical Preflight does not call `systemctl` and does not modify a service.

## P1 formal Runtime commands

Only after P1 Technical Preflight passes and the operator enters the exact P1
`/start` may the P1 Runtime contract use:

```bash
sudo -n systemctl daemon-reload
sudo -n systemctl enable secmon-collector.service
sudo -n systemctl restart secmon-collector.service
sudo -n systemctl is-enabled secmon-collector.service
sudo -n systemctl is-active secmon-collector.service
sudo -n systemctl status secmon-collector.service --no-pager
```

The first three commands change system state. The last three are read-only.
They are not executed by `--preflight-only` and were not executed while this
framework was validated.

The Runtime contracts also require journal, DB, Cursor, authentication-log, and
process evidence, but they do not yet define a complete fixed privileged
argument vector for those inspections. No wildcard `journalctl`, SQLite,
filesystem, `runuser`, or shell permission may be inferred from the prose. A
future unattended Runtime policy remains denied until those exact read-only
commands and paths are specified and reviewed. An interactive trusted operator
may perform the approved Runtime procedure under the host's existing sudo
policy without creating a new `NOPASSWD` rule.

Any additional privileged command discovered during a formal run is denied
until it is documented with its exact executable, arguments, target paths, and
reason. Shell wildcards, arbitrary shell execution, package-manager wildcards,
and unrestricted `systemctl` are not minimal privileges.

## P2 Runner

`run_secmon_p2_multi_agent_gate.sh` contains no sudo invocation. P2 Technical
Preflight requires no sudo and may run while P1 dependency status is
`NOT_PASSED`.

P2 production Runtime is a later, separately authorized phase. The current P2
task contract describes systemd evidence but does not grant any sudo command.
Before any future P2 production command is allowed, its exact service name and
full argument vector must be added to this inventory and reviewed. P2 may not
inherit P1 sudo or `/start` authorization.

## Deployment helper

The deployment helper changes users, directories, `/etc/secmon`, `/opt/secmon`,
and systemd, so the entire helper requires a root operator. The only recommended
elevation entrypoint is:

```bash
sudo -- bash scripts/deploy_helper.sh
```

This is an interactive operator entrypoint, not a safe sudoers allowlist entry.
Do not grant `NOPASSWD` access to a mutable repository script or to `bash`; the
operator must review the exact committed helper and deployment inputs before
running it.

The helper rejects command-line arguments so the Telegram credential cannot be
placed in process arguments or shell history. Once running as root it uses
`runuser`, not nested sudo, for these exact privilege drops:

```bash
runuser -u secmon -- python3 -m venv /opt/secmon/.venv
runuser -u secmon -- /opt/secmon/.venv/bin/pip install --upgrade pip
runuser -u secmon -- /opt/secmon/.venv/bin/pip install -e /opt/secmon/
runuser -u secmon -- bash -lc 'set -a; source /etc/secmon/secmon.env; set +a; cd /opt/secmon; .venv/bin/python -m backend.notifiers.telegram --test'
```

The final command is printed as a later manual smoke-test instruction; it is not
automatically executed by the helper. The helper itself was not executed during
framework validation.

## Explicit prohibitions

- Do not modify `/etc/sudoers` or `/etc/sudoers.d` from this project.
- Do not grant `NOPASSWD: ALL`, unrestricted shells, or wildcard systemctl.
- Do not grant `NOPASSWD` access to `bash scripts/deploy_helper.sh` or any other
  user-writable script.
- Do not pass a password, token, API key, or cookie in command arguments.
- Do not reuse a P1 credential/authorization decision as P2 authorization.
- Do not use sudo to bypass a failed Technical Preflight.
- Do not execute deployment or Runtime commands during static framework
  validation.
