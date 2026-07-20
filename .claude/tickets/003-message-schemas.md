---
id: 003
title: Versioned inter-agent message schemas (v1) + typed errors
status: tests-authored     # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [001]
branch: ticket/003-message-schemas
base_branch: main
test_command: ".venv/bin/pytest tests/test_schemas.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Pydantic models for `AttackDirective`, `AttackAttempt`, `Verdict`, `RegressionTrigger`,
`VulnReport`, each with `schema_version` (v1), plus typed error results (target unreachable, budget
exceeded, judge timeout, no findings in window, regression detected). This is the seam for the
optional `/contracts` JSON-Schema publication + contract tests.

## Acceptance criteria
- [ ] All five messages + error results defined with `schema_version="v1"`.
- [ ] Round-trip (serialize→deserialize) is lossless; invalid payloads raise validation errors.
- [ ] Required fields enforced (e.g. `Verdict` has verdict/confidence/rationale/owasp mapping).

## Test plan (orchestrator authors these)
- unit: `tests/test_schemas.py` — valid round-trip per model; missing required field rejected;
  `schema_version` present on every model.
