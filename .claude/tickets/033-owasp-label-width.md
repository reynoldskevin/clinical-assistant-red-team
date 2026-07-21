---
id: 033
title: Row three back to 5/3/4 + widen OWASP label column to 200px
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [032]
branch: ticket/033-owasp-label-width
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_owasp_label.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Revert the third row to 5/3/4 spans (OWASP coverage `c5`, Cost `c3`, Findings `c4`), and inside the OWASP coverage tile widen the heat-row label column from `118px` to `200px` so the longer OWASP category labels have room. Supersedes the 6/3/3 spans from ticket 032; the two older span assertions are updated to match.

## Acceptance criteria
- [ ] Third row spans are OWASP `c5` / Cost `c3` / Findings `c4` (tied to headings 03/04/05).
- [ ] The OWASP heat-row grid label column is `200px` (`grid-template-columns: 200px 1fr 34px`); the `118px` value is gone.
- [ ] Full suite stays green; superseded 6/3/3 assertions updated.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_owasp_label.py` — asserts the 5/3/4 third-row spans tied to their headings and the 200px OWASP label column; the older 6/3/3 assertions in `test_dashboard_polish.py` / `test_dashboard_pill_spans.py` are updated to 5/3/4.
