---
id: 029-fix
title: Runnable module entrypoint so `forge serve` deploys on Railway
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [029]
branch: fix/029-deploy-entrypoint
base_branch: main
test_command: ".venv/bin/pytest tests/test_module_entrypoint.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The first Railway deploy of the 029 dashboard crashed on boot: the container ran the Procfile's `web: forge serve` and got `forge: command not found` — the `forge` console script (declared in `pyproject.toml`) is not reliably placed on the runtime `PATH` by the Nixpacks Python build. The portable, build-agnostic fix is to invoke the app as a Python module instead of a console script: add a package entrypoint `forge/__main__.py` that delegates to `forge.run.main`, so `python -m forge serve` works regardless of whether the console script is on `PATH`, and change the `Procfile` to `web: python -m forge serve`. This affects only the process launch — the `forge run`/`forge serve` argument handling is unchanged.

## Acceptance criteria
- [ ] `python -m forge <args>` dispatches to `forge.run.main` (the package is runnable as a module).
- [ ] `python -m forge run` (no target flags) exits `2` with the "specify --category/--suite" guidance — proving the module entrypoint reaches `main` and parses args, WITHOUT needing `ANTHROPIC_API_KEY`/config.
- [ ] The `Procfile` starts the dashboard via the module form (`web: python -m forge serve`), not the bare `forge` console script.
- [ ] No behavior change to existing `run`/`serve` argument parsing; full suite stays green.

## Test plan (orchestrator authors these)
- unit/e2e: `tests/test_module_entrypoint.py` — spawns `sys.executable -m forge run` in a subprocess and asserts exit code `2` + the guidance message (a real, non-blocking end-to-end check of the module entrypoint that would have caught the crash); and asserts the `Procfile` invokes `python -m forge serve`.
