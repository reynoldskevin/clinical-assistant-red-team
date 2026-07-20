---
id: 008
title: Seed eval dataset (>=3 categories, OWASP-mapped)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [003]
branch: ticket/008-seed-evals
base_branch: main
test_command: ".venv/bin/pytest tests/test_evals_dataset.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 1
---

## Description
`./evals/` seed suite covering >=3 attack categories. Each case: category/subcategory, prompt or input sequence, expected safe behavior, observed-behavior field, severity, add-to-regression flag, and `owasp_web`/`owasp_llm` mapping (mandatory engineering requirement). Loader + case-schema validation.

## Acceptance criteria
- [ ] >=3 distinct attack categories present in `./evals/`.
- [ ] Every case validates against the case schema, including a required OWASP mapping.
- [ ] Loader reads all cases and exposes them for a run.

## Test plan (orchestrator authors these)
- unit: `tests/test_evals_dataset.py` — the seed `./evals/` has >=3 distinct categories; every
  seed case validates against the `EvalCase` schema with required fields (category, prompt-or-
  sequence, expected_behavior, severity, add_to_regression, OWASP mapping) and an
  observed_behavior slot for a run to fill; the loader returns every case; a case missing its
  OWASP mapping / prompt / with a bad severity is rejected; the loader raises a typed
  `EvalCaseError` on an invalid case file.
