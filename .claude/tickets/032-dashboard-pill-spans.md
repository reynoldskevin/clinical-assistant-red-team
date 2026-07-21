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
Two dashboard tweaks. (1) Set the third row to 6/3/3 spans: OWASP coverage `c6`, Cost `c3`, Findings `c3`. (2) Restore the refresh pill to its original look — a green flashing pulse dot and the static text "auto-refresh · 5s" — instead of the per-second `↻ next refresh Ns / refreshing…` countdown. The dashboard still auto-refreshes on the same 5s interval (`setInterval(poll, 5000)`); only the pill's presentation reverts. The run-in-progress indicator (ticket 030) is unchanged.

## Acceptance criteria
- [ ] Third row spans are OWASP `c6` / Cost `c3` / Findings `c3` (tied to their numbered headings 03/04/05).
- [ ] The refresh pill (`id="refresh-pill"`) shows a `.pulse` dot (green, flashing) + the static text `auto-refresh · 5s`; the `next refresh` / `refreshing` countdown copy is gone.
- [ ] The page still polls `/api/state` on the 5s interval, and the `runstate` indicator remains.
- [ ] Full suite stays green; no locked test behavior changes.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_pill_spans.py` — asserts the 6/3/3 third-row spans tied to their headings, the restored static pill markup (pulse + "auto-refresh · 5s") with the countdown copy removed, and that polling + the runstate indicator are intact.
