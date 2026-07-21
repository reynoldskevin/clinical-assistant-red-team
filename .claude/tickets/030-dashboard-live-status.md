---
id: 030
title: Dashboard run-in-progress indicator + live refresh countdown
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [029]
branch: ticket/030-dashboard-live-status
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_runstatus.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Two live-demo affordances for the dashboard. (1) A run-in-progress indicator: the store logs `run_start`/`run_end` boundary events, so `build_state` gains a `run_active` flag (a run has started with no later `run_end`), and the masthead shows a pulsing "run in progress" chip next to the refresh pill when true (hidden otherwise). (2) A live refresh countdown: the static "auto-refresh · 5s" pill becomes an actual per-second countdown (5 → 1 → "refreshing…" during the fetch → reset), so viewers see the real time until the next `/api/state` poll. Both are presentation-only; the read-model and endpoints are unchanged.

## Acceptance criteria
- [ ] `build_state(obs)["run_active"]` is `True` when the latest `run_start` event has no later `run_end`, `False` after a `run_end` (or when there are no run events); JSON-serializable.
- [ ] `render_html(state)` includes a run-status element (`id="runstate"`) that is hidden unless a run is active, and drives it from `state["run_active"]`.
- [ ] `render_html(state)` includes a refresh pill (`id="refresh-pill"`) with a per-second countdown element, and the page decrements it each second and re-polls `/api/state` at zero (`setInterval` 1s tick).
- [ ] No locked `tests/test_dashboard.py` behavior changes; full suite stays green.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_runstatus.py` — pins `build_state["run_active"]` across started/ended/no-run stores and JSON-serializability; asserts `render_html` carries the `runstate` indicator and the `refresh-pill` countdown and still polls `/api/state` on an interval.
