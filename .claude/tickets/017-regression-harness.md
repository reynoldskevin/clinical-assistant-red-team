---
id: 017
title: Regression & Validation Harness
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [005, 007, 004, 015]
branch: ticket/017-regression-harness
base_branch: main
test_command: ".venv/bin/pytest tests/test_regression_harness.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Convert confirmed exploits into deterministic, repeatable regression cases; on a `RegressionTrigger` replay the recorded transcript through the Adapter and ask the Judge for a verdict (a **meaningful** pass = unsafe behavior genuinely absent per the Judge, not merely different output); detect reappearance of a previously-fixed vuln and flag when fixing one category regresses another. Cases + replay outcomes persist as append-only store events. Decision logic only — live wiring is the full loop (018).

## Acceptance criteria
- [ ] A confirmed exploit (`success` verdict) is converted into a stored deterministic regression case; a non-confirmed verdict is rejected.
- [ ] Replaying a still-vulnerable target yields a Judge-confirmed regression FAIL, driven by the Judge verdict (meaningful), NOT by an output diff — an output that merely changed but is still exploited fails, and a genuinely-defended replay passes even when the wording differs.
- [ ] Reappearance of a previously-fixed vuln is detected (was fixed → now vulnerable again).
- [ ] Cross-category regression is flagged: a previously-fixed case in a category other than the one just changed that regresses is marked cross-category.

## Test plan (orchestrator authors these)
- unit: `tests/test_regression_harness.py` (Adapter + Judge mocked) — case creation + non-success rejected; meaningful pass/fail driven by the Judge (not output-diff); reappearance detection; cross-category regression flag via `validate(changed_category=...)`.
