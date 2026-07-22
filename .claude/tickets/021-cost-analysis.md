---
id: 021
title: AI Cost Analysis deliverable
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [016, 018]
branch: ticket/021-cost-analysis
base_branch: main
test_command: ".venv/bin/pytest tests/test_cost_analysis.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
`./AI_COST_ANALYSIS.md`: actual dev spend derived from recorded `cost` data plus projected production cost at 100 / 1K / 10K / 100K test runs, and the architectural change each scale forces (prompt caching, request batching, local/cheaper models, suite sampling) — explicitly NOT a linear token×runs estimate. A `forge/cost_analysis.py` module derives the dev-spend baseline from the store's recorded cost rows and computes the four sub-linear tier projections; the deliverable markdown is rendered from that baseline so the figures are reproducible.

## Acceptance criteria
- [ ] `forge/cost_analysis.py` derives dev spend from recorded cost rows and projects four scale tiers, each sub-linear vs the naive token×runs estimate.
- [ ] Document reports actual dev spend from recorded cost data.
- [ ] Projections for 100/1K/10K/100K runs, each with the architectural change it implies.

## Test plan (orchestrator authors these)
- unit: `tests/test_cost_analysis.py` — baseline derives from recorded cost rows; four tiers present; projection sub-linear (effective < naive above baseline, per-run cost monotonically decreasing); each tier names an architectural change; committed `AI_COST_ANALYSIS.md` present with the four tiers, the architectural levers, and a dev-spend dollar figure.
