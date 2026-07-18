# SecMon P2 Multi-Agent Skill and Runner Setup

## Purpose

This report records creation and static validation of the P2 execution
framework only. No P2 product implementation, runtime Gate, Agent, push, PR,
Issue update, merge, or Hermes notification was performed. The framework was
committed locally as `11782c45d9fad5204450311ab34aa2b6582837be` and remains
unpushed while acceptance preparation is reviewed.

## Created artifacts

Global Skills:

- `/home/b822726/.codex/skills/run-secmon-p2-gates/SKILL.md`
- `/home/b822726/.codex/skills/review-secmon-p2-release/SKILL.md`

Project runner:

- [`run_secmon_p2_multi_agent_gate.sh`](../run_secmon_p2_multi_agent_gate.sh)

Task contracts:

- [`docs/agent_tasks/P2_01_CODEX_API_AUTH_IMPLEMENTATION.md`](agent_tasks/P2_01_CODEX_API_AUTH_IMPLEMENTATION.md)
- [`docs/agent_tasks/P2_02_GLM52_SECURITY_REVIEW.md`](agent_tasks/P2_02_GLM52_SECURITY_REVIEW.md)
- [`docs/agent_tasks/P2_03_AGY_API_RUNTIME_VERIFICATION.md`](agent_tasks/P2_03_AGY_API_RUNTIME_VERIFICATION.md)
- [`docs/agent_tasks/P2_04_CODEX_FINAL_RELEASE_AUDIT.md`](agent_tasks/P2_04_CODEX_FINAL_RELEASE_AUDIT.md)

Manual control and privilege documents:

- [`docs/P1_P2_COMBINED_MANUAL_ACCEPTANCE_RUNBOOK.md`](P1_P2_COMBINED_MANUAL_ACCEPTANCE_RUNBOOK.md)
- [`docs/P1_P2_MINIMAL_SUDO_REQUIREMENTS.md`](P1_P2_MINIMAL_SUDO_REQUIREMENTS.md)

Report path contracts referenced by the framework:

- `docs/P2_01_CODEX_API_AUTH_IMPLEMENTATION_REPORT.md`
- `docs/P2_02_GLM52_SECURITY_REVIEW.md`
- `docs/P2_03_AGY_API_RUNTIME_VERIFICATION.md`
- `docs/P2_04_CODEX_FINAL_RELEASE_AUDIT.md`

## Contract validation

- Both Skill files have valid lowercase hyphenated names, descriptions, and
  explicit trigger names in frontmatter.
- `$run-secmon-p2-gates` defines Agent 1 → Agent 2 → Agent 3 serial execution,
  dynamic P1 evidence, DEVELOPMENT_ONLY/RELEASE_ELIGIBLE behavior, exact
  report markers, stop-loss rules, secret hygiene, and no Agent 4 invocation.
- `$review-secmon-p2-release` defines a fresh Codex Agent 4 session, hard
  prerequisites, independent audit coverage, P1 blocking language, and the
  only two final decision markers.
- Runner task constants point to the four exact `docs/agent_tasks/P2_*.md`
  files. The runner validates Task 4 exists but contains no Agent 4 launch
  branch.
- Agent launch contracts are fixed to Codex `gpt-5.6-luna`/`xhigh`/
  `workspace-write`, Claude `glm-5.2` at its maximum available effort, and AGY
  Gemini 3.5 Flash/High.
- P1 execution eligibility is parsed from a committed report blob containing
  exact `P1_FORMAL_ACCEPTANCE=PASS` evidence and the final P1 decision, requires
  report/Tested-HEAD ancestry and reachability from current HEAD, and rejects
  product-code drift through that HEAD. `origin/main` remains separately
  recorded; P2 final release review may impose stronger remote requirements.
- Runner final markers cover Agent 1 BLOCKED/READY, Agent 2 REJECTED/APPROVE,
  and Agent 3 NOT_PASSED/STAGING_RUNTIME_PASS_P1_BLOCKED/P2_RUNTIME_GATE_PASS.
- Hermes is described for future runner/Agent 4 execution only. This setup
  session did not invoke Hermes.

## Technical Preflight and authorization separation

The 2026-07-18 framework update separates technical inspection from manual
execution authorization:

- P1 `--preflight-only` performs technical checks without requesting `/start`,
  starting an Agent, or running a Runtime Gate.
- A complete P1 run stops on a blocked Technical Preflight and requests an
  exact P1-only `/start` only after Technical Preflight passes.
- P2 `--preflight-only` checks local P2 prerequisites even when P1 formal
  acceptance is not PASS. P1 dependency is reported independently rather than
  misclassifying P2 technical readiness.
- A complete P2 run requires committed `P1_FORMAL_ACCEPTANCE=PASS` evidence,
  then requests a new exact P2-only `/start`. P1 authorization is not stored or
  reused.
- Git push, GitHub Issue update, and Hermes notification are controlled by
  exact boolean environment values and default to `false`.
- The deployment helper no longer accepts the Telegram credential through a
  command argument and no longer nests `sudo -u` inside a root process.

## Static structure validation

- `skill-creator` `quick_validate.py` was used for both Skill directories.
- Generated `agents/openai.yaml` metadata was updated with matching display,
  short description, and explicit default prompt for each Skill.
- `bash -n run_secmon_p2_multi_agent_gate.sh` passed after shell quoting and
  stage-marker validation.
- The runner's exact task-file references and report-file contracts were
  inspected statically; Task 4 appears only as a required-file contract and no
  Agent 4 launcher exists. No Agent launcher was executed.

The 2026-07-18 separation update was validated with:

- `bash -n run_secmon_p1_multi_agent_gate.sh`: PASS, exit 0.
- `bash -n run_secmon_p2_multi_agent_gate.sh`: PASS, exit 0.
- `bash -n scripts/deploy_helper.sh`: PASS, exit 0.
- `PATH="$PWD/.venv/bin:$PATH" make check`: PASS, including Ruff, mypy on
  16 source files, pytest 115/115, and the frontend TypeScript build.
- `git diff --check`: PASS, exit 0 before staging.
- P1 `--preflight-only` with all external-side-effect flags false: exit 20,
  `P1_TECHNICAL_PREFLIGHT_STATUS=BLOCKED` solely because non-interactive sudo
  was unavailable; human authorization was `NOT_REQUESTED`, Agent count was 0,
  Runtime was `NOT_RUN`, and external side-effect count was 0.
- P2 `--preflight-only` with all external-side-effect flags false: exit 0,
  `P2_TECHNICAL_PREFLIGHT_STATUS=PASS`, P1 dependency `NOT_PASSED`, human
  authorization `NOT_REQUESTED`, Agent count 0, Runtime `NOT_RUN`, Release Gate
  `NOT_PASSED`, and external side-effect count 0.
- The Codex/Claude/AGY process inventory before and after both Preflights was
  unchanged; only the existing controller Codex processes were present.
- Captured Preflight output passed a no-content secret-pattern scan.
- `shellcheck`: SKIPPED because the tool was unavailable.

## Repository and dependency snapshot

At the acceptance-preparation refresh, before its documentation commit, the
repository snapshot was:

- `origin/main` HEAD: `080e3fe2659cedc9748383907fc56fe795e73fc2`
- Git top-level: `/home/b822726/project/get-dg-a1`
- SecMon project prefix: `secmon-linux-security/` (the Runner uses `git -C`
  and the dynamic prefix; it does not assume SecMon is the Git top-level)
- current branch: `main`
- current HEAD: `11782c45d9fad5204450311ab34aa2b6582837be`
- divergence: `main` is 1 commit ahead of `origin/main` and 0 behind
- existing user worktree change: `../.gitignore` (preserved; not reset or cleaned)
- P1 last program HEAD: not accepted as a trusted P1 Release dependency during
  setup; future Runner execution derives and records it from tracked evidence.
- P1 formal final status: **NOT FORMALLY PASSED**. No trusted P1 final
  evidence was used to infer Release Gate PASS; Issue #2 remains OPEN under the
  supplied dependency contract.
- P2 status: **FRAMEWORK CREATED; P2 NOT STARTED**

The Skills and runner do not permanently encode the snapshot above. Future
execution records fresh `origin/main`, branch/HEAD, P1 last program HEAD, P1
final report/commit, Tested Code HEAD, and code-drift evidence.

## Safety assertions

- No Agent 1, Agent 2, Agent 3, or Agent 4 was started.
- No P2 runtime or production systemd Gate was run.
- No product source, migration, test, systemd, frontend, or existing user file
  was modified.
- No `.env` content was read or output. No environment dump or secret-bearing
  scan output was produced.
- The existing `.env.example` remains untracked and unstaged; the framework
  explicitly keeps it outside P2 absent an approved existing dependency.
- Framework commit `11782c4` exists locally; no push, PR, merge, Issue update,
  or Issue closure was performed.
- Hermes was not sent, as required for this child setup session.
- Only exact acceptance-preparation documentation paths are eligible for the
  next local commit. The pre-existing `.env.example`, unrelated helper, and
  historical untracked reports/tasks remain unstaged.

The final lines retain the explicit non-execution state. The setup result stays
the final line for existing machine readers.

P2_IMPLEMENTATION_STATUS: NOT_STARTED
P2_RUNTIME_GATE_STATUS: NOT_RUN
P2_RELEASE_GATE_STATUS: NOT_PASSED
P2_SKILL_SETUP_RESULT: PASS
