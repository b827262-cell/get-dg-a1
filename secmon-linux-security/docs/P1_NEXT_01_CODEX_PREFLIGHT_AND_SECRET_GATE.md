# SecMon P1 — Technical Preflight and Secret Gate

## Execution boundary

- Date: `2026-07-18` (`Asia/Taipei`)
- Workflow: controller-side audit using the `run-secmon-p1-gates` security
  policy
- Agent launcher/model/reasoning: `NOT STARTED` by explicit user policy
- Agent start count: `0`
- Scope: staged-document review, secret hygiene, Static Gate, and formal
  `--preflight-only` execution
- No product source, production environment file, systemd unit, service,
  Runtime state, GitHub Issue, remote branch, or external notification was
  changed.

## Repository and worktree

- Git root: `/home/b822726/project/get-dg-a1`
- SecMon project: `secmon-linux-security/`
- Branch: `main`
- Inspected repository HEAD: `11782c45d9fad5204450311ab34aa2b6582837be`
- `origin/main`: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- Ahead / behind before the preparation commit: `1 / 0`
- Initial staged paths: the three P1/P2 acceptance-preparation documents only
- Intended additional path: the exact `.gitignore` addition for `.envO`
- Root `.env`: untracked, ignored, mode `0600`; contents were not read, printed,
  copied, summarized, or scanned
- `.envO`: absent and covered by the pending exact ignore rule
- Root `.env.example`: untracked and excluded from this task
- Existing tracked `secmon-linux-security/.env.example`: not modified
- `/etc/secmon/secmon.env`: absent by metadata-only inspection; no production
  environment-file content was read
- Unrelated untracked scripts, historical reports, and superseded task files
  remain unstaged and unmodified

## Staged-document review

All three initially staged documents are specific to the requested P1/P2
acceptance preparation:

- `docs/P1_P2_COMBINED_MANUAL_ACCEPTANCE_RUNBOOK.md`
- `docs/P1_P2_MINIMAL_SUDO_REQUIREMENTS.md`
- `docs/P2_MULTI_AGENT_SKILL_AND_RUNNER_SETUP.md`

The review removed an unrelated old session anecdote, corrected stale
pre-commit/index claims, documented the current local framework commit, added a
placeholder-only production env shape, and recorded boolean/metadata-only
checks. No credential value is present in the example.

## Sudo boundary

- No `NOPASSWD: ALL` or new sudoers policy is proposed.
- P1 Technical Preflight uses only sudo readiness plus fixed `test`, `grep`, and
  `stat` checks against `/etc/secmon/secmon.env` without printing values.
- The P1 Runtime task contract names six exact `systemctl` commands; none ran in
  this stage.
- The root deployment helper is an interactive human operation and must not be
  granted as a `NOPASSWD` mutable-script or shell entry.
- The P2 Runner invokes no sudo command. Undefined future production inspection
  commands remain unauthorized rather than receiving wildcard access.

## Syntax and Static Gate

```text
bash -n run_secmon_p1_multi_agent_gate.sh: PASS (exit 0)
bash -n run_secmon_p2_multi_agent_gate.sh: PASS (exit 0)
bash -n scripts/deploy_helper.sh: PASS (exit 0)
PATH="$PWD/.venv/bin:$PATH" make check: PASS (exit 0)
```

Static Gate details:

- Ruff: PASS
- mypy: PASS, 16 source files
- pytest: PASS, 115/115
- frontend TypeScript build: PASS

## Formal P1 Technical Preflight

Executed with stdin closed and all external-side-effect flags forced to
`false`:

```text
./run_secmon_p1_multi_agent_gate.sh --preflight-only </dev/null
```

Result: exit `20`.

```text
P1_TECHNICAL_PREFLIGHT_STATUS=BLOCKED
P1_HUMAN_START_AUTHORIZATION=NOT_REQUESTED
P1_AGENT_EXECUTION_STATUS=NOT_STARTED
P1_AGENT_START_COUNT=0
P1_RUNTIME_GATE_STATUS=NOT_RUN
P1_EXTERNAL_SIDE_EFFECTS_EXECUTED=0
SECMON_ALLOW_GIT_PUSH=false
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false
SECMON_ALLOW_HERMES_NOTIFY=false
```

Exact Runner blocker:

```text
non-interactive sudo is unavailable
```

The Runner stopped at sudo readiness and therefore did not claim that the
absent production env passed validation. The environment-file absence is a
separate metadata-confirmed human prerequisite that will become the next
Runner check after sudo readiness succeeds.

## P2 Technical Preflight cross-check

P2 `--preflight-only </dev/null` returned exit `0` with technical status
`PASS`, P1 dependency `NOT_PASSED`, human authorization `NOT_REQUESTED`, Agent
count `0`, Runtime `NOT_RUN`, Release Gate `NOT_PASSED`, and all three external
side-effect flags `false`. The Codex/Claude/AGY process inventory was unchanged
across both Preflights. The captured Preflight outputs passed a no-content
secret-pattern scan.

## Human remediation and next check

In a trusted interactive production-host terminal, the operator must first
cache an approved sudo credential and verify non-interactive reuse:

```bash
sudo -v
sudo -n true
```

Then create or edit the production env without truncating an existing file and
without putting secrets in arguments or Git:

```bash
sudo install -d -o root -g root -m 0755 /etc/secmon
sudo test -e /etc/secmon/secmon.env || \
  sudo install -o root -g root -m 0600 /dev/null /etc/secmon/secmon.env
sudoedit /etc/secmon/secmon.env
sudo chown root:root /etc/secmon/secmon.env
sudo chmod 0600 /etc/secmon/secmon.env
```

Populate the approved Telegram values only inside `sudoedit`, keep
`SECMON_AUTO_BLOCK_ENABLED=false`, perform the non-printing checks documented in
`docs/P1_P2_COMBINED_MANUAL_ACCEPTANCE_RUNBOOK.md`, and rerun:

```bash
SECMON_ALLOW_GIT_PUSH=false \
SECMON_ALLOW_GITHUB_ISSUE_UPDATE=false \
SECMON_ALLOW_HERMES_NOTIFY=false \
./run_secmon_p1_multi_agent_gate.sh --preflight-only </dev/null
```

P1 remains `NOT READY`; no `/start` was requested, Agent 2–4 were not started,
formal acceptance remains `NOT_PASSED`, and P2 must not start.

STAGE_RESULT: PREFLIGHT_BLOCKED
