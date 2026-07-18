# SecMon P1/P2 Combined Manual Acceptance Runbook

## Scope

This runbook separates safe technical inspection from human-authorized Agent
and Runtime execution. Technical Preflight never requests `/start`, launches an
Agent, runs a Runtime Gate, changes system services, sends Hermes, pushes Git,
or updates a GitHub Issue.

The default external-side-effect policy is:

```text
SECMON_ALLOW_GIT_PUSH=false
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false
SECMON_ALLOW_HERMES_NOTIFY=false
```

Only an exact `true` enables the corresponding action. Missing, malformed, or
`false` values do not grant authorization.

## 1. Run P1 Technical Preflight

From the SecMon project root:

```bash
SECMON_ALLOW_GIT_PUSH=false \
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false \
SECMON_ALLOW_HERMES_NOTIFY=false \
./run_secmon_p1_multi_agent_gate.sh --preflight-only </dev/null
```

This command performs Git, command, sudo-readiness, and production environment
metadata/configuration checks. It does not ask for `/start`. Review these exact
status fields:

```text
P1_TECHNICAL_PREFLIGHT_STATUS=PASS|BLOCKED
P1_HUMAN_START_AUTHORIZATION=NOT_REQUESTED
P1_AGENT_EXECUTION_STATUS=NOT_STARTED
P1_AGENT_START_COUNT=0
P1_RUNTIME_GATE_STATUS=NOT_RUN
P1_EXTERNAL_SIDE_EFFECTS_EXECUTED=0
```

A blocked result is a technical/environment finding, not a request to bypass
sudo or manufacture Runtime evidence.

## 2. Run P2 Technical Preflight

P2 Technical Preflight is allowed before P1 formal acceptance:

```bash
SECMON_ALLOW_GIT_PUSH=false \
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false \
SECMON_ALLOW_HERMES_NOTIFY=false \
./run_secmon_p2_multi_agent_gate.sh --preflight-only </dev/null
```

Review:

```text
P2_TECHNICAL_PREFLIGHT_STATUS=PASS|BLOCKED
P2_HUMAN_START_AUTHORIZATION=NOT_REQUESTED
P2_P1_DEPENDENCY_STATUS=PASS|NOT_PASSED
P2_AGENT_EXECUTION_STATUS=NOT_STARTED
P2_AGENT_START_COUNT=0
P2_RUNTIME_GATE_STATUS=NOT_RUN
P2_RELEASE_GATE_STATUS=NOT_PASSED
P2_EXTERNAL_SIDE_EFFECTS_EXECUTED=0
```

`P2_P1_DEPENDENCY_STATUS=NOT_PASSED` does not invalidate a successful P2
technical inspection. It does prevent a complete P2 run.

## 3. Prepare `/etc/secmon/secmon.env`

This is a human-only production-host step. Do not copy an actual password,
Telegram token, Chat ID, or future P2 authentication secret into Git, a shell
argument, terminal output, or this runbook. Create the file without truncating
an existing configuration, edit it through `sudoedit`, and restore the required
metadata:

```bash
sudo install -d -o root -g root -m 0755 /etc/secmon
sudo test -e /etc/secmon/secmon.env || \
  sudo install -o root -g root -m 0600 /dev/null /etc/secmon/secmon.env
sudoedit /etc/secmon/secmon.env
sudo chown root:root /etc/secmon/secmon.env
sudo chmod 0600 /etc/secmon/secmon.env
```

Use the following as a documentation-only shape. Both `__SET_WITH_SUDOEDIT__`
values are deliberately invalid and must be replaced in the production file by
the trusted operator. Never save the populated version in the repository.

```dotenv
SECMON_APP_NAME=SecMon
SECMON_ENVIRONMENT=production
SECMON_DATABASE_PATH=/var/lib/secmon/secmon.db
SECMON_SSH_LOG_PATH=/var/log/auth.log
SECMON_SSH_CURSOR_PATH=/var/lib/secmon/ssh.cursor
SECMON_COLLECT_INTERVAL_SECONDS=5
SECMON_API_HOST=127.0.0.1
SECMON_API_PORT=8000
SECMON_LOG_LEVEL=INFO
SECMON_TRUSTED_PROXY_CIDRS=[]
SECMON_AUTO_BLOCK_ENABLED=false
SECMON_TELEGRAM_ENABLED=true
SECMON_TELEGRAM_BOT_TOKEN=__SET_WITH_SUDOEDIT__
SECMON_TELEGRAM_CHAT_ID=__SET_WITH_SUDOEDIT__
SECMON_TELEGRAM_TIMEOUT_SECONDS=5
SECMON_TELEGRAM_MIN_SEVERITY=3
SECMON_TELEGRAM_COOLDOWN_SECONDS=60
```

Check presence, metadata, and required non-secret settings without printing the
file or any matched value:

```bash
sudo -n test -s /etc/secmon/secmon.env
test "$(sudo -n stat -c '%U:%G' /etc/secmon/secmon.env)" = root:root
test "$(sudo -n stat -c '%a' /etc/secmon/secmon.env)" = 600
sudo -n grep -Eq '^SECMON_ENVIRONMENT=production$' /etc/secmon/secmon.env
sudo -n grep -Eq '^SECMON_AUTO_BLOCK_ENABLED=false$' /etc/secmon/secmon.env
sudo -n grep -Eq '^SECMON_TELEGRAM_ENABLED=true$' /etc/secmon/secmon.env
sudo -n grep -Eq '^SECMON_TELEGRAM_BOT_TOKEN=[^[:space:]]+$' /etc/secmon/secmon.env
sudo -n grep -Eq '^SECMON_TELEGRAM_CHAT_ID=[^[:space:]]+$' /etc/secmon/secmon.env
```

The P1 Runner performs stricter boolean-only checks for the approved Telegram
identifier and token format. Do not use `cat`, an environment dump, shell
tracing, or a command that prints the matching line as a substitute. P2 may add
new authentication settings only after its implementation contract defines
them; do not invent or pre-populate future P2 secrets during P1 preparation.

## 4. Human review before P1

Do not start P1 unless all technical blockers have been resolved and a trusted
operator has manually confirmed:

- the intended repository, branch, HEAD, and staged state;
- the production environment file exists with approved ownership/mode and
  automatic blocking disabled;
- sudo is available through a trusted interactive credential cache;
- the Telegram prerequisite has been completed without exposing credentials;
- the external SSH test source is explicitly authorized and appropriately
  limited;
- the P1 reports from a previous attempt have been safely archived;
- external side effects remain disabled unless separately authorized.

## 5. Authorize and execute P1

Run the P1 Runner in a trusted interactive terminal:

```bash
SECMON_ALLOW_GIT_PUSH=false \
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false \
SECMON_ALLOW_HERMES_NOTIFY=false \
./run_secmon_p1_multi_agent_gate.sh
```

The Runner repeats Technical Preflight first. Only after it passes does the
Runner request a phase-specific authorization. Type exactly:

```text
/start
```

Any other input, EOF, non-interactive stdin, or missing TTY is denied. No Agent
may start on denial. This `/start` authorizes P1 only.

## 6. Confirm committed P1 acceptance evidence

P2 complete execution is allowed only after the P1 final report is tracked and
committed, the committed blob contains:

```text
P1_FORMAL_ACCEPTANCE=PASS
```

and its final line is:

```text
FINAL_DECISION: P1_RELEASE_GATE_PASS
```

The P2 Runner derives this state from committed evidence and checks the Tested
Code HEAD and product-code drift. An environment variable, untracked report,
working-tree edit, prose-only claim, or P1 process exit code cannot replace the
committed acceptance evidence.

## 7. Re-authorize and execute P2

After P1 formal PASS, run the P2 Runner in a trusted interactive terminal:

```bash
SECMON_ALLOW_GIT_PUSH=false \
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false \
SECMON_ALLOW_HERMES_NOTIFY=false \
./run_secmon_p2_multi_agent_gate.sh
```

The Runner repeats P2 Technical Preflight, rechecks committed P1 evidence, and
then requests a new P2-only authorization. Type exactly:

```text
/start
```

The prior P1 `/start` is never stored, inherited, or accepted as P2
authorization. One `/start` cannot authorize both phases.

## 8. Stop rules

- Stop on any Technical Preflight blocker, invalid exact input, stale report,
  missing command, model mismatch, report mismatch, or Runtime failure.
- Never use `git add .`, `git add -A`, or `git commit -am`.
- Never use mocks, synthetic logs, hand-inserted database rows, or a successful
  process exit as formal Runtime evidence.
- Keep `SECMON_AUTO_BLOCK_ENABLED=false` throughout acceptance.
- Technical Preflight alone never makes P1 or P2 Release-ready.
- P2 Release Gate remains `NOT_PASSED` until its separately authorized Agent
  and independent final-review requirements are actually completed.
