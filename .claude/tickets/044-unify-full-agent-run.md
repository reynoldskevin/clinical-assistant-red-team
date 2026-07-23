---
id: 044
title: Unify the deployed run on one full-agent loop — Orchestrator + Documentation fire in `forge run`; retire AutonomousLoop
status: tests-authored
depends_on: [043]
branch: feature/unify-full-agent-run
base_branch: main
test_command: ".venv/bin/pytest tests/test_run_autonomous.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Only two of the four named agents fire in the deployed run: `forge run` drives the `Runner`, which
uses a fixed category loop (no Orchestrator) and never drafts reports (no Documentation). The full
chain lived in `AutonomousLoop`, but that class is a single-cycle graph reachable only from tests
and missing all run bookkeeping (run_start, versioning, run_id/cost). This ticket evolves the proven
`Runner` into the single production driver: it drives attacks via `orchestrator.next_directive()`,
runs the Documentation report pass, keeps the regression replay (043), and preserves all run
bookkeeping — so all four agents (Orchestrator, Red Team, Judge, Documentation) plus the Regression
harness fire in ONE deployed path. `AutonomousLoop` is retired to eliminate the parallel loop.

## Acceptance criteria
- [ ] `Runner` accepts optional `orchestrator` and `documentation`. A new `run_autonomous()`:
  - opens a versioned run (`run_start` with `version` continuing the `v1.N` sequence + `ts`), and
    stamps `run_id`/`target_version`/`version` on every attack/verdict/finding/cost record it
    produces — identical bookkeeping to `run_suite`;
  - drives the attack phase by looping `orchestrator.next_directive()` until it returns `None`
    (bounded by a safety cap), running Red Team → Judge per returned directive;
  - after the attack phase and BEFORE `run_end`, in order: (a) replays known regression cases via
    `harness.validate()` (events land inside the run window), then (b) runs the Documentation pass
    `generate_reports(store, documentation=…, harness=…)` (drafts distinct VulnReports + creates
    regression cases for this run's new exploits). A failure in either step is isolated (recorded,
    never aborts the run or skips `run_end`);
  - emits `run_end` (version + run_id) in a `finally`.
- [ ] The deployed `main()` constructs an `Orchestrator` (over `Observability` + the eval
  categories) and a `DocumentationAgent`, wires them + the `RegressionHarness` into the `Runner`,
  and `forge run --suite` / `--category` drive `run_autonomous()`. A testable factory
  (`build_autonomous_runner(...)`) assembles the fully-wired Runner so the four-agent wiring is
  unit-verifiable without network.
- [ ] `forge/loop.py` (`AutonomousLoop`) and `tests/test_full_loop.py` are removed; no other module
  imports them.
- [ ] Back-compat: existing `run_suite` / `run_category` behavior and ALL locked dashboard,
  per-run-scoping (043) and regression-panel tests remain green. Full suite green.

## Test plan (orchestrator authors these)
- unit: tests/test_run_autonomous.py —
  - `run_autonomous` loops `next_directive()` until `None` (fake orchestrator) and executes one
    Red Team → Judge cycle per directive;
  - versioning + `run_id`/`target_version` stamping on verdicts/cost; second run increments minor;
  - regression `validate()` fires and its `regression_result` events fall within
    `[run_start, run_end]`, BEFORE the Documentation pass;
  - Documentation pass fires: with a real `DocumentationAgent(reports_dir=tmp)` + real
    `RegressionHarness`, a confirmed exploit yields a report file + a `vuln_report_link` event +
    a `regression_case` event;
  - a raising documentation/harness does not abort the run (`run_end` still emitted);
  - the REAL `Orchestrator` drives and halts (coverage reached) — proving the strategist is wired;
  - `build_autonomous_runner(...)` returns a Runner whose `_orchestrator`, `_documentation`,
    `_regression_harness` are the real agent types (four-agent wiring);
  - `import forge.loop` raises `ModuleNotFoundError` (AutonomousLoop retired).
- regression: full suite (`.venv/bin/pytest -q`) stays green; test_full_loop.py deleted.
