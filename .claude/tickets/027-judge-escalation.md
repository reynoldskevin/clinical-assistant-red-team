---
id: 027
title: Judge low-confidence escalation + per-category rubric spec
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [007]
branch: ticket/027-judge-escalation
base_branch: main
test_command: ".venv/bin/pytest tests/test_judge_escalation.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Encode the reliability bias (a missed vuln costs more than a false alarm): when the Judge's confidence is below a threshold, **escalate to human review** rather than silently passing. Ship an explicit **per-category success/fail/partial rubric** (not just a general one), versioned alongside the calibration set.

## Acceptance criteria
- [ ] A below-threshold verdict is routed to human review, not auto-passed.
- [ ] Each attack category has a written, testable success/fail/partial definition the Judge applies.
- [ ] The per-category rubric is versioned and covered by the calibration set.

## Test plan (orchestrator authors these)
- unit: `tests/test_judge_escalation.py` — `should_escalate` below/above threshold; `review()` routes a low-confidence verdict (incl. a low-confidence "safe" verdict) to human review without auto-passing; `rubric_for(category)` returns a success/fail/partial spec for every category (unknown → default, no crash); the per-category rubric is injected into the Judge prompt; `CATEGORY_RUBRIC_VERSION` is defined and every calibration-fixture category has a rubric.
