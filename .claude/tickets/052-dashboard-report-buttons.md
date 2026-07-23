---
id: 052
title: Dashboard report-button visibility + polish
status: todo
depends_on: []
branch: ticket/052-dashboard-report-buttons
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_report_buttons.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Small dashboard refinements: the "View reports" button in the Exploits KPI panel
should only show when there are exploits to view; the Known vulnerabilities panel
gains its own "View reports" button shown only when there are unfixed cases; the
Known-vulnerabilities `wtag` reads `regression()` for consistency with the other
method-name tags; and the live-agent-activity timestamp column gets 30px more room.

## Acceptance criteria
- [ ] The Exploits-panel `#view-reports` button is hidden when `k.exploits === 0`
      and shown when `k.exploits > 0` (toggled in `renderKpis`).
- [ ] The Known-vulnerabilities panel has its own report button `#view-reports-kv`
      that starts hidden and is shown only when `kv.vulnerable > 0` (toggled in
      `renderKnownVulns`); clicking it opens the SAME reports modal (`openReports`).
- [ ] The Known-vulnerabilities `whead` tag is `<span class="wtag">regression()</span>`
      (was `regression`).
- [ ] The `.feedrow` grid timestamp column widens by 30px (68px → 98px); the other
      columns (38px / 108px / 1fr / auto) are unchanged.
- [ ] The Resilience-trend sub line labels each version's rate with a percent sign
      (`v1.0 87%` not `v1.0 87`).
- [ ] The Resilience-trend chart shows a pip (small circle) on EVERY datapoint, not
      just the final endpoint (the final point keeps its emphasized dot/halo).
- [ ] No behavioral change beyond the above; full suite stays green.

## Test plan (orchestrator authors these)
- unit (`tests/test_dashboard_report_buttons.py`), asserting on `render_html`:
  - `renderKpis` ties `#view-reports` `.hidden` to `k.exploits > 0`.
  - `#view-reports-kv` exists, starts `hidden`, `renderKnownVulns` ties its
    `.hidden` to `kv.vulnerable`, and it is wired to `openReports` (two buttons
    now open the reports modal).
  - the `regression()` wtag is present and the bare `regression` wtag is gone.
  - the `.feedrow` grid-template-columns is `38px 98px 108px 1fr auto`.
  - `renderTrend` appends `"%"` to each version's `pass_rate` in the sub line.
  - the SVG carries a `#trend-dots` group and `renderTrend` populates it with one
    circle per point derived from `pts`.
