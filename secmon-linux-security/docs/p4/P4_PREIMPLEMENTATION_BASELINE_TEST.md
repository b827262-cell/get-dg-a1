# P4 Preimplementation Baseline Test

- Branch: `feature/secmon-p4-detection-operations`
- HEAD: `df9995329d987b646c1ab89cca65096dfc762de4`
- Result: **P4_PREIMPLEMENTATION_BASELINE_PASS**

## Commands and results

| Check | Command | Result |
| --- | --- | --- |
| Worktree identity | `git status --short`; `git rev-parse HEAD` | Clean before P4 documentation; authorized HEAD confirmed. |
| Lint | `make check` (using the existing project development virtual environment) | `ruff check backend database tests`: PASS. |
| Typecheck | `make check` | `mypy backend database`: PASS, 20 source files. |
| Backend tests | `make check` | `pytest`: PASS, 133 tests. |
| Frontend test | `npm test` in `frontend` | PASS, 2 tests. |
| Frontend typecheck | `npm run typecheck` in `frontend` | PASS. |
| Frontend build | `make check`; `npm run build` in `frontend` | PASS. |
| Fresh migration | `python database/migrate.py --database /tmp/secmon-p4-baseline-df999532.db` | PASS. |
| Repeat migration | Same command a second time | PASS. |
| SQLite quick check | `PRAGMA quick_check` | `ok`. |
| SQLite integrity check | `PRAGMA integrity_check` | `ok`. |
| SQLite FK check | `PRAGMA foreign_key_check` | no rows. |

## Environment note

The first bare `make check` could not find a usable `ruff` command and frontend dependencies were not installed in the new worktree. This was an environment/dependency setup condition, not a source failure. Re-running with the existing project development virtual environment and `npm ci` in this isolated worktree produced the passing results above.
