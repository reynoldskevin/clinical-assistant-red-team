---
id: 032
title: Third row 6/3/3 spans + restore static "auto-refresh" pill with green pulse
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [031]
branch: ticket/032-dashboard-pill-spans
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_pill_spans.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Two dashboard tweaks. (1) Set the third row to 6/3/3 spans: OWASP coverage `c6`, Cost `c3`, Findings `c3`. (2) Restyle the refresh pill to a green flashing pulse dot + "auto-refresh" label while KEEPING the per-second countdown — `🟢 auto-refresh · 5s` where the number ticks 5→4→3→…→refresh→5 — replacing the `↻ next refresh Ns / refreshing…` styling. Only the number updates each tick, so the green pulse and label stay put; the poll fires at zero. The run-in-progress indicator (ticket 030) is unchanged.

## Acceptance criteria
- [ ] Third row spans are OWASP `c6` / Cost `c3` / Findings `c3` (tied to their numbered headings 03/04/05).
- [ ] The refresh pill (`id="refresh-pill"`) shows a green flashing `.pulse` dot + "auto-refresh · Ns" with a live countdown number (`id="refresh-count"`); the `↻` icon / `next refresh` / `refreshing` copy is gone.
- [ ] The countdown ticks each second and polls `/api/state` at zero; the `runstate` indicator remains.
- [ ] Full suite stays green; no locked test behavior changes.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_pill_spans.py` — asserts the 6/3/3 third-row spans tied to their headings, the pill markup (green pulse + "auto-refresh" label + `refresh-count` countdown number, no `↻`/`next refresh`/`refreshing`), and that the per-second tick, polling, and runstate indicator are intact.
