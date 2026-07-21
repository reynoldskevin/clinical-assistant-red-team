---
id: 031
title: Dashboard copy + layout polish (stale copy, findings tag, row-3 spans, numbering)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [030]
branch: ticket/031-dashboard-copy-layout
base_branch: ticket/030-dashboard-live-status
test_command: ".venv/bin/pytest tests/test_dashboard_polish.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Presentation cleanups on the live dashboard. Remove two stale dev-facing lines that are no longer accurate — the "# every tile maps 1:1 …" header note and the "forge serve → GET /api/state …" footer. Make the Findings tile's source tag method-call style (`outcomes()`) to match the other tags (`pass_fail()`, `coverage()`, `cost()`). Set the third row to 5/3/4 spans (OWASP coverage 5, Cost 3, Findings 4). Fix the widget numbering so the six tiles read 01–06 sequentially and uniquely (OWASP was a duplicate `04`; it becomes `03`). Stacked on ticket 030 (also dashboard-only) to keep the live UI coherent.

## Acceptance criteria
- [ ] The header note ("every tile maps…") and the footer (`class="foot"`, "forge serve…") are removed from `render_html`.
- [ ] The Findings tile tag is `outcomes()` (not the bare `outcomes`).
- [ ] Third row spans are OWASP `c5` / Cost `c3` / Findings `c4`.
- [ ] Widget numbers 01–06 each appear exactly once (sequential, no gap/dup).
- [ ] Full suite stays green; no locked test behavior changes.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_polish.py` — asserts the stale copy is gone, the `outcomes()` tag, the 5/3/4 row spans tied to their numbered headings, and unique sequential 01–06 numbering.
