---
id: 054
title: Seed-aware autonomous directives
status: ready-for-merge
depends_on: []
branch: ticket/054-seed-aware-directives
base_branch: main
test_command: ".venv/bin/pytest tests/test_seed_aware_directives.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The deployed loop (`run_autonomous`) drives the Red Team from category-only
directives — the Orchestrator's `next_directive()` never sets `directive.seed`, so
the `evals/*.json` attack prompts never reach the target. Make the Orchestrator
seed-aware: it cycles a category's eval-case prompts as directive seeds, and floors
each seeded category at enough attempts to exercise every one of its seeds. This
makes the existing catalog actually drive the deployed run (and lets thin-area
cases, ticket 055, measurably lift their OWASP coverage).

## Acceptance criteria
- [ ] `Orchestrator(..., seeds_by_category=None)` accepts a `{category: [seed,...]}`
      map (default: none → today's behavior). Each `next_directive()` for a category
      with seeds sets `directive.seed` to that category's NEXT seed, cycling through
      the list across successive directives; a category with no seeds yields
      `directive.seed is None`.
- [ ] The coverage floor for a seeded category is `max(coverage_target, len(seeds))`
      so EVERY seed is exercised at least once (a category with more seeds than
      `coverage_target` keeps being probed until all seeds have run). Unseeded
      categories keep the plain `coverage_target` floor.
- [ ] `build_autonomous_runner` derives `seeds_by_category` from the `cases`
      (via `seeds_for_category`) and passes it to the Orchestrator, so the deployed
      run is seed-driven.
- [ ] `seeds_for_category` is defensive: a case object lacking `prompt`/
      `input_sequence` attributes contributes no seed (no `AttributeError`).
- [ ] No change to halting/coverage semantics beyond the seeded floor; existing
      orchestrator + run tests stay green.

## Test plan (orchestrator authors these)
- unit (`tests/test_seed_aware_directives.py`):
  - successive `next_directive()` for a below-floor seeded category cycle its seeds
    (s1, s2, s1, …); an unseeded category → `seed is None`; default (no map) → None.
  - a category with more seeds than `coverage_target` is probed until ALL seeds have
    run, then halts (seeded floor = max(target, #seeds)).
  - `build_autonomous_runner` wires case prompts as seeds: the built Orchestrator's
    first directive carries the matching category's case prompt.
  - `seeds_for_category` tolerates prompt-less case objects.
