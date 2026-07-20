---
id: 007
title: Judge agent (independent evaluation + invariant)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [002, 003]
branch: ticket/007-judge
base_branch: main
test_command: ".venv/bin/pytest tests/test_judge.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 1
---

## Description
Independent evaluator: given an `AttackAttempt`, return a `Verdict` (`success|fail|partial`, confidence, rationale, OWASP mapping) using a versioned rubric. No attack generation. Ships a fixed calibration fixture and enforces the invariant that the Judge never marks a labeled-confirmed exploit as safe.

## Acceptance criteria
- [ ] Given an `AttackAttempt`, returns a well-formed `Verdict`; rubric carries a version.
- [ ] Low-temperature/deterministic path is mockable and stable across runs.
- [ ] Invariant test: a labeled-confirmed exploit fixture is never scored `fail`/safe.

## Test plan (orchestrator authors these)
- unit: `tests/test_judge.py` (LLM mocked) — attempt → well-formed `Verdict`; rubric version
  present and configurable; the Judge does NO attack generation (no target egress); the LLM is
  called at temperature 0 and two runs over the same input yield an identical Verdict;
  calibration fixtures score as their labels under a faithful LLM; the safety invariant holds —
  a labeled-confirmed exploit is never scored `fail`/safe even when the (adversarial) LLM says
  so (it is clamped to a non-safe verdict); malformed LLM output raises a typed `JudgeError`.
