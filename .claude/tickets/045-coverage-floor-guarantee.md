---
id: 045
title: Guarantee the 6-category coverage floor (≥10 attempts each) in the autonomous run
status: ready-for-merge
depends_on: [044]
branch: feature/coverage-floor-guarantee
base_branch: feature/unify-full-agent-run   # stacked on 044 (needs build_autonomous_runner/run_autonomous)
test_command: ".venv/bin/pytest tests/test_coverage_floor.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The platform requires each of the six attack categories to be probed a minimum of 10 times per run.
The orchestrator-driven run (044) can violate that: `Orchestrator.next_directive()` prioritizes
re-probing an open high-severity finding (step 2) ABOVE closing coverage gaps (step 3), so once one
early exploit is found, the loop re-probes that one category indefinitely and the other five never
reach the floor before the budget/cap halts the run. This ticket makes the **coverage floor**
(every category reaching `coverage_target` attempts) outrank high-severity re-probing, and pins the
deployed `coverage_target` at 10, so all six categories are always covered to the minimum first.

## Acceptance criteria
- [ ] `Orchestrator.next_directive()` prioritizes the coverage FLOOR — any category whose attempts
      are below `coverage_target` — ABOVE open-high-severity re-probing. Order becomes: (1) budget
      hard-stop, (2) coverage-floor gap → least-covered category, (3) open high-severity re-probe,
      (4) residual coverage-sufficiency gap, (5) halt. An early open finding can no longer starve
      another category's floor.
- [ ] `Runner.run_autonomous()` over the six categories against a purely-defending target drives
      EACH category to ≥ `coverage_target` (10) attempts, then halts cleanly. Even when an exploit
      is found early (an open high-severity finding), all six still reach ≥10 (bounded by an optional
      `max_directives` cap on `run_autonomous` for deterministic testing; default unchanged).
- [ ] `build_autonomous_runner(...)` pins the Orchestrator's `coverage_target = 10` (the platform
      minimum) explicitly; categories still derive from the eval dataset (the six).
- [ ] Back-compat: all existing Orchestrator tests stay green — `test_open_high_severity_finding_is_reprobed`
      (all categories already at floor → still re-probes), `test_run_budget_reached_halts_even_with_gaps`
      (budget remains the first check), coverage-sufficiency, and every 044/043 test. Full suite green.

## Test plan (orchestrator authors these)
- unit: tests/test_coverage_floor.py —
  - `next_directive` picks a below-floor category over an open high-severity finding in a
    *covered* category (the starvation fix), while still re-probing when everything is at floor;
  - `run_autonomous` with the real Orchestrator + 6 categories + defending fakes → each category
    has ≥10 attempts and the run halts;
  - an exploit found on the first attempt does NOT starve the other five — all six still reach ≥10
    (using a small `max_directives` cap);
  - `build_autonomous_runner(...)` yields an Orchestrator with `coverage_target == 10`.
- regression: full suite green; existing test_orchestrator.py unchanged and passing.
