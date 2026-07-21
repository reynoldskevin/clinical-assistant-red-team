---
id: 029-fix2
title: Dashboard "Findings" widget shows verdict outcomes (defended/partial/exploited), not the empty lifecycle
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [029]
branch: fix/029-findings-outcomes
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_findings.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
On the live dashboard the "Findings" widget rendered `Open / In progress / Resolved` and read all zeros. That widget was wired to the finding-lifecycle view, but findings are only created on a confirmed exploit — the target defended every attempt in the seeded run, so the lifecycle is legitimately empty and the tile looked broken. The approved mockup showed this tile as the verdict-outcome breakdown (`Exploited / Partial / Defended`), which always carries real numbers. Fix: rebind the widget to the aggregate verdict outcomes from `pass_fail().overall` and restore the mockup headings. `build_state` gains a small `outcomes` block (`exploited`/`partial`/`defended`) mirroring the KPI/verdict convenience keys; the tile's headings become `Exploited` (crit) / `Partial` (warn) / `Defended` (good) and the `In progress`/`Resolved` lifecycle labels are removed. The finding-lifecycle view is still present in `build_state` (unused by the UI) for later use.

## Acceptance criteria
- [ ] `build_state(obs)["outcomes"]` == `{"exploited": overall.exploits, "partial": overall.partial, "defended": overall.defended}` and JSON-round-trips.
- [ ] `render_html(state)` renders the Findings tile with headings `Exploited`, `Partial`, `Defended`, driven by `state["outcomes"]`.
- [ ] The finding-lifecycle labels `In progress` and `Resolved` no longer appear in the rendered document (the regressed binding is gone).
- [ ] No locked `tests/test_dashboard.py` behavior changes; full suite stays green.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_findings.py` — seeds a store with a mixed verdict set (successes + partial + fails), asserts `build_state["outcomes"]` equals the expected exploited/partial/defended counts and is JSON-serializable, asserts `render_html` contains the three outcome headings and NOT the `In progress`/`Resolved` lifecycle labels.
