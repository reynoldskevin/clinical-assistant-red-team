---
id: 046
title: Scope the Orchestrator to the current run so each run covers all six ≥10 (fix empty-run bug)
status: tests-authored
depends_on: [044, 045]
branch: feature/scope-orchestrator-to-run
base_branch: main
test_command: ".venv/bin/pytest tests/test_orchestrator_run_scope.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Production bug: on any run after the first, `run_autonomous` records no attacks/verdicts and the
dashboard shows zeros. Root cause: the Orchestrator assesses coverage/budget/findings against the
CUMULATIVE store, but the dashboard scopes stats per run. Once prior runs have put every category
over `coverage_target`, `next_directive()` returns `None` immediately, so the new run does nothing.
Fix: `run_autonomous` scopes the Orchestrator's observability to the CURRENT run window (events since
this run's `run_start`; findings/costs stamped with this `run_id`), so each run re-drives coverage
from zero and covers all six categories ≥10. The per-run run-scoping logic is extracted from the
dashboard into a shared `forge/scoping.py` so both use one implementation.

## Acceptance criteria
- [ ] New `forge/scoping.py` exposes `current_run(events)` and `RunScopedStore(store, *, start_id,
      end_id)` — a read-only store view: `get_events()` limited to the id window `[start_id, end_id]`
      (open-ended when `end_id is None`), and `list_findings(**filters)` / `get_costs()` limited to
      rows whose `run_id == start_id` (findings still honor the passed filters, e.g. `status="open"`).
- [ ] `forge/dashboard.py` uses `forge.scoping.current_run` / `RunScopedStore` (its local
      `_current_run` / `_RunScopedStore` are removed or delegate) with identical behavior — all
      existing dashboard tests stay green.
- [ ] `Runner.run_autonomous()` scopes the Orchestrator to the current run: after appending
      `run_start`, it points the orchestrator's observability at an `Observability` over
      `RunScopedStore(store, start_id=<this run_id>, end_id=None)`, so coverage/budget/findings
      reflect only THIS run. A run whose store already contains a complete prior run still drives
      every category to ≥ `coverage_target` attempts in the new run.
- [ ] Back-compat: 044/045 behavior (floor-first, ≥10 each, regression replay, documentation) and
      all locked dashboard/per-run/regression tests stay green. Full suite green.

## Test plan (orchestrator authors these)
- unit: tests/test_orchestrator_run_scope.py —
  - `RunScopedStore` windows events by id and scopes findings/costs by `run_id`, and
    `list_findings(status="open")` applies BOTH the run_id scope and the status filter;
  - a store with a COMPLETE prior run (all six categories covered) + a fresh `run_start`: an
    Orchestrator over `RunScopedStore` for the new run returns a directive (not `None`);
  - end-to-end regression for the bug: `run_autonomous` on a store that already has a full prior
    run drives every one of the six categories to ≥10 attempts stamped with the NEW run's version;
  - `forge.scoping.current_run` returns the latest run's `(start_id, end_id, version)`.
- regression: dashboard per-run tests + full suite stay green.
