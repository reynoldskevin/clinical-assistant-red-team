---
id: 057
title: OWASP panel min-height + legend agent grouping
status: todo
depends_on: []
branch: ticket/057-owasp-minheight-legend-order
base_branch: main
test_command: ".venv/bin/pytest tests/test_owasp_minheight_legend.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
With the honest coverage metric (053), the OWASP panel is empty until a run
populates it, so `#owasp-heat` collapses to zero height and breaks the dual-row
layout. Give it a `min-height` floor. Also, in the Live agent activity legend, move
the Documentation chip to the LEFT of the Regression chip so the four agents
(orchestrator, red_team, judge, documentation) sit together and the deterministic
regression substrate trails last.

## Acceptance criteria
- [ ] `#owasp-heat` has `min-height: 300px` so the panel keeps its height when the
      heat map has no rows.
- [ ] In the Live agent activity legend, the `documentation` chip appears BEFORE the
      `regression` chip (order: orchestrator, red_team, judge, documentation,
      regression).
- [ ] No other layout/markup changes; full suite stays green.

## Test plan (orchestrator authors these)
- unit (`tests/test_owasp_minheight_legend.py`), asserting on `render_html`:
  - a CSS rule gives `#owasp-heat` `min-height: 300px`.
  - the documentation legend chip span precedes the regression legend chip span.
