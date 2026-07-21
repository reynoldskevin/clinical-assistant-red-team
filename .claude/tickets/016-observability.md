---
id: 016
title: Observability read-model + metrics (the human + orchestrator view)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [004]
branch: ticket/016-observability
base_branch: main
test_command: ".venv/bin/pytest tests/test_observability.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 1
---

## Description
Derive the read-model + metrics over the store that answer the six required questions: categories tested + case count each; pass/fail rate across categories and target versions; resilience trend over versions; finding lifecycle (open/in-progress/resolved); run cost + scaling rate; per-agent ordered activity. This is both the human view and the Orchestrator's input, and the backbone the live demo dashboard renders. Coverage is reported per attack-category AND per OWASP category (using the eval dataset's category->OWASP mapping). Pulled forward from Milestone 2 (depends only on the merged store) to unblock a visible demo UI.

## Acceptance criteria
- [ ] Each of the six questions is answerable via a read-model API over recorded events/metrics/findings.
- [ ] Coverage is reported per attack-category AND per OWASP category.
- [ ] Cost + scaling rate are computed from recorded `cost` rows.

## Test plan (orchestrator authors these)
- unit: `tests/test_observability.py` — seed the store (verdict/attack events across categories and
  target versions, findings with mixed lifecycle statuses, cost rows) then assert: coverage counts
  per category and per OWASP; pass/fail counts + rate per category and per version; an ordered
  resilience trend over versions; finding lifecycle bucket counts; total + per-category cost and a
  per-attempt scaling rate; ordered per-agent activity; and a combined `snapshot()`.
