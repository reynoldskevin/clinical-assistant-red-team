---
id: 074
title: Auto-refresh polls only while a run is active
status: todo
depends_on: []
branch: ticket/074-poll-only-during-run
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_poll_gating.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The dashboard polls `GET /api/state` every 10s unconditionally (the 1s `tick()` decrements a
countdown and polls at zero, forever). It should only poll while a run is active — from when the
Start button is clicked (or a run is already active on load) until the run is detected finished —
and stay quiet when idle. Gate the poll on a `pollActive` flag driven by run state.

## Acceptance criteria
- [ ] A `pollActive` flag gates polling: `tick()` still paints the elapsed clock every second, but
      when `!pollActive` it does NOT decrement the countdown or call `poll()`.
- [ ] `pollActive` is initialized from the initial state's `run_active` (poll if a run is already
      in progress when the page loads; otherwise idle/no polling).
- [ ] Clicking the Start button sets `pollActive = true` (begin polling) — polling then continues
      across the brief window before `run_start` lands (guarded by the existing `pendingStart`).
- [ ] When a poll observes the run is no longer active (`run_active` false) and nothing is pending,
      `pollActive` is set false — polling STOPS (run detected finished). The 30s Start failsafe also
      clears `pollActive` if the run never became active.
- [ ] No change to the refresh-pill markup, the 10s interval label, `setInterval`, or run-state
      header behavior; existing dashboard tests stay green.

## Test plan (orchestrator authors these)
- unit (`tests/test_dashboard_poll_gating.py`):
  - `tick()` early-returns when `!pollActive` (poll gated) — assert `if (!pollActive) return;`.
  - `pollActive` initialized from `initial.run_active`.
  - Start handler sets `pollActive = true`; renderHeader sets it true when active and false when
    idle-and-not-pending.
  - `setInterval` and the refresh pill are still present (not regressed).
