---
id: 071
title: OWASP coverage panel — cap height at 600px and scroll overflow
status: todo
depends_on: []
branch: ticket/071-owasp-heat-maxheight-scroll
base_branch: main
test_command: ".venv/bin/pytest tests/test_owasp_heat_scroll.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
As the OWASP coverage list grows it can overrun its panel. Cap the `#owasp-heat` coverage list
at a max height of 600px and scroll the overflow, keeping the existing 300px min-height (ticket
057) so the panel never collapses.

## Acceptance criteria
- [ ] The `#owasp-heat` CSS rule sets `max-height: 600px` and scrolls vertical overflow
      (`overflow-y: auto`), while preserving the existing `min-height: 300px`.
- [ ] No other dashboard styles/behavior change; the panel markup is unchanged.

## Test plan (orchestrator authors these)
- unit (`tests/test_owasp_heat_scroll.py`):
  - the rendered HTML's `#owasp-heat` rule contains `max-height: 600px`, `overflow-y: auto`,
    and still `min-height: 300px`.
