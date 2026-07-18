# SecMon P2 — Agent 4 / Codex Independent Final Release Audit

## Fresh-session contract

This task is launched only by an explicit `$review-secmon-p2-release` request in
a new Codex `exec` session. It is not a continuation of Agent 1 and is never
launched by `run_secmon_p2_multi_agent_gate.sh`.

Fixed launch: model `gpt-5.6-luna`, reasoning `xhigh`, sandbox
`workspace-write`. Record actual model evidence. Never use a fallback.

Never read or print the repository root `.env`; never use `env`, `printenv`,
shell `set`, tracing, or secret-bearing arguments. Do not modify product code,
migrations, tests, systemd, runtime state, or Agent 1–3 reports during the
audit. Secret scans must be boolean-only and must not print matches.
Confirm `.env.example` was not mixed into P2 without an approved existing
program dependency and `.envO` remained ignored and unstaged.

## Hard prerequisites

Before deciding, dynamically record `origin/main` HEAD, current branch/HEAD,
P1 last program HEAD and final status, Agent 1–3 actual models and tested
HEADs, report commits, and all code drift. Never treat `080e3fe` as a permanent
baseline.

All of these must be independently evidenced:

- trusted P1 report is tracked and committed, ends exactly
  `FINAL_DECISION: P1_RELEASE_GATE_PASS`, contains an exact Tested Code HEAD,
  and has no code drift through the current trusted `origin/main`; the marker
  and Tested Code HEAD must come from the committed report blob;
- Agent 1 report ends `STAGE_RESULT: READY_FOR_GLM52_REVIEW`;
- Agent 2 report ends `STAGE_RESULT: APPROVE_FOR_AGY`, with
  `BLOCKER_COUNT: 0` and `HIGH_COUNT: 0`, and active model exactly `glm-5.2`;
- Agent 3 report ends `STAGE_RESULT: P2_RUNTIME_GATE_PASS`, with active
  Gemini 3.5 Flash / High evidence;
- reports are tracked, reachable, and correspond to the same tested P2 code;
- current branch is the feature branch and has no unexplained later code drift;
- final audit has zero Blocker and zero High findings.

A missing report, prose-only claim, untracked file, stale HEAD, model mismatch,
or unverifiable command is a failed prerequisite. It cannot be upgraded to
PASS by a successful process exit.

## Audit checklist

Independently inspect and rerun read-only checks for:

- P1 dependency and exact Tested Code HEAD/report commit correspondence;
- Agent 1–3 launcher, model, reasoning, report marker, and evidence integrity;
- Auth library, Argon2id/bcrypt, password/session/token handling, logout,
  cooldown, cookie flags/CSRF, issuer/expiry, and secret sources;
- Viewer/Analyst/Admin RBAC and 401/403/404 behavior;
- all API contracts, filters, strict IDs/IPs, bounded pagination/time ranges,
  parameterized SQL, raw-log limits, error contract, request IDs, OpenAPI,
  CORS, proxy trust, and health leakage;
- immutable migrations, fresh/repeat migration, indexes, foreign keys,
  busy-timeout/WAL concurrency, and Collector transaction/regression behavior;
- API systemd entrypoint, non-root identity, EnvironmentFile, restart policy,
  WorkingDirectory, hardening, explicit write paths, and secret absence;
- staging/production runtime evidence, restart, concurrency, logs, and leak checks;
- tracked/staged secret hygiene and prohibited runtime artifacts;
- P2 scope completeness and explicit P3 boundary: no React Web Console may be
  reported as delivered by this audit.

Mark anything unavailable `NOT VERIFIED`. Do not repair findings in this
session. Classify findings as Blocker/High/Medium/Low and record exact counts.

## Decision and permitted actions

Write only the sanitized report:

`docs/P2_04_CODEX_FINAL_RELEASE_AUDIT.md`

If any hard prerequisite or technical finding fails, end exactly:

```text
FINAL_DECISION: P2_RELEASE_GATE_NOT_PASSED
```

When P1 is the only blocker but all technical P2 evidence is otherwise ready,
state exactly: `P2 technically ready, blocked by P1 dependency`.

Only when every prerequisite is evidenced and Blocker=0/High=0 may the report
end exactly:

```text
FINAL_DECISION: P2_RELEASE_GATE_PASS
```

After that PASS only, and only if the user has authorized the normal release
handoff, stage exact safe paths, show `git diff --cached --name-status`, run a
staged no-content secret scan, create a redacted acceptance commit, push the
feature branch, and create/update a PR or P2 Issue. Never merge main unless
separately requested. Do not close Issue #2 from an ineligible or failed audit.
