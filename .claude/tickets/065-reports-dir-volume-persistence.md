---
id: 065
title: Persist vuln reports on the Railway volume by default
status: todo
depends_on: []
branch: ticket/065-reports-dir-volume-persistence
base_branch: main
test_command: ".venv/bin/pytest tests/test_reports_dir_resolution.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
On prod the Documentation agent writes each VulnReport JSON to the relative `reports/`
directory, which lives on the container's ephemeral filesystem — not the `/data` Railway
volume — so reports drafted during a run are lost on the next redeploy. Worse, the report
WRITER (`forge/run.py::build_autonomous_runner`) and the dashboard READER
(`forge/dashboard.py::make_server`) each independently resolve the directory via
`os.environ.get("FORGE_REPORTS_DIR", "reports")`, so they can silently drift. Introduce a
single `resolve_reports_dir()` helper that both sides call, with a volume-aware default: when
`FORGE_REPORTS_DIR` is unset but a Railway volume is mounted (`RAILWAY_VOLUME_MOUNT_PATH`),
default to `<mount>/reports` so reports persist across deploys without hand-setting an env var;
local dev is unchanged (`reports`).

## Acceptance criteria
- [ ] `forge.config.resolve_reports_dir(env=None)` (env defaults to `os.environ`) returns:
      an explicit non-blank `FORGE_REPORTS_DIR` verbatim (highest precedence); else
      `<RAILWAY_VOLUME_MOUNT_PATH>/reports` when that mount var is set; else `"reports"`.
      A blank/whitespace `FORGE_REPORTS_DIR` is treated as unset (falls through).
- [ ] `build_autonomous_runner` (the WRITER) constructs its `DocumentationAgent` with
      `reports_dir=resolve_reports_dir()` — so a run on a volume-mounted prod writes to
      `<mount>/reports`.
- [ ] `make_server` (the READER) defaults its `reports_dir` to `resolve_reports_dir()` when the
      `reports_dir` argument is None — so the dashboard reads the SAME directory the writer wrote.
      An explicit `reports_dir=` argument still overrides (unchanged).
- [ ] Writer and reader resolve to the identical directory for the same environment (the
      contract that prevents drift).
- [ ] Local/default behavior is unchanged: with neither env var set, both sides resolve to
      `"reports"`. Existing report tests stay green.

## Test plan (orchestrator authors these)
- unit (`tests/test_reports_dir_resolution.py`):
  - resolve precedence: explicit wins over volume; volume → `<mount>/reports`; neither → `reports`;
    blank explicit treated as unset.
  - WRITER wiring: `build_autonomous_runner` under a volume env → its documentation agent's
    `_reports_dir == Path(resolve_reports_dir(env))` (i.e. `<mount>/reports`).
  - READER wiring (e2e): `make_server(reports_dir=None)` under a volume env whose `<mount>/reports`
    holds a report file serves that report on `/api/reports` — proving it resolved to the same dir.
  - contract: writer dir == reader dir for the same env.
