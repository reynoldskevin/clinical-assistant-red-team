---
id: 014
title: Orchestrator agent (prioritize · budget · trigger)
status: todo # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [016]
branch: ticket/014-orchestrator
base_branch: main
test_command: ".venv/bin/pytest tests/test_orchestrator.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Reads the Observability read-model and selects the next `AttackDirective` by coverage gaps + open high-severity findings; enforces per-run/per-directive budgets; halts or redirects when spend accrues without signal; emits a `RegressionTrigger` on a target-version change or on a configured time window. Applies a coverage-sufficiency rule (a category is "done" when it meets a defined case-count/pass-rate threshold) to stop over-testing it, and a no-clear-priority fallback (round-robin the least-covered categories; if all at target coverage or budget spent, stop cleanly). Decision logic only — wiring into the live run is the full autonomous loop (018).

## Acceptance criteria
- [ ] Given a read-model state, chooses a directive targeting an under-covered / high-severity surface.
- [ ] Halts/redirects when signal-per-token falls below threshold (redirect to least-covered while coverage gaps remain; halt cleanly once coverage is met with no signal).
- [ ] Marks a category sufficiently-covered per the threshold and stops selecting it.
- [ ] Emits `RegressionTrigger` on a target-version change AND on the configured time window.
- [ ] With no clear priority, falls back to least-covered round-robin, then stops when nothing remains.
- [ ] Enforces the per-run budget: once run spend reaches the budget, halts regardless of coverage.

## Test plan (orchestrator authors these)
- unit: `tests/test_orchestrator.py` (real in-memory Store + Observability seeded with verdict events / findings / cost rows) — coverage-gap state → expected least-covered category; open high-severity finding → re-probed even when covered; category at threshold → skipped; all-covered + low-signal → halt; run-budget reached → halt; version-change and time-window → RegressionTrigger; no-priority → round-robin then stop.
