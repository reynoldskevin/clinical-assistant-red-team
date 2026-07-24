---
id: 073
title: Resilience-trend delta relative to previous run + OWASP panel 500px
status: todo
depends_on: []
branch: ticket/073-trend-delta-owasp-500
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_trend_delta.py tests/test_owasp_heat_scroll.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The resilience-trend delta chip compares the current version to the FIRST version
(`trend[0]`), so it reads e.g. "-1 pts" against the oldest baseline instead of the change
since the last run. Make the delta relative to the PREVIOUS run (`trend[n-2]`), so a drop from
100% to ~95% reads "▼ -5 pts". Also tighten the OWASP coverage panel cap from 600px to 500px.

## Acceptance criteria
- [ ] `renderTrend` computes the delta as `pct(trend[n-1].pass_rate) - pct(trend[n-2].pass_rate)`
      (current minus PREVIOUS run), no longer using `trend[0]`. The cap keeps its ▲ +N / ▼ -N pts
      format.
- [ ] When there is only one version (`n < 2`, no previous run), the cap is empty (no misleading
      delta against a nonexistent prior run). The `trend-num` (current pass rate) and sub line are
      unchanged.
- [ ] `#owasp-heat` `max-height` is `500px` (was 600px); `min-height: 300px` and `overflow-y: auto`
      preserved.
- [ ] No other dashboard behavior changes.

## Test plan (orchestrator authors these)
- unit (`tests/test_dashboard_trend_delta.py`):
  - the rendered JS computes the delta from `trend[n - 2]` (previous run) and no longer subtracts
    `pct(trend[0].pass_rate)`.
  - a single-version guard (`n >= 2`) exists so no delta is shown for one run.
- update `tests/test_owasp_heat_scroll.py`: assert `max-height: 500px` (not 600px).
