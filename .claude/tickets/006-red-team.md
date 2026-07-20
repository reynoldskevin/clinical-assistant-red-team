---
id: 006
title: Red Team agent (MVP single-turn generation)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [002, 003, 005]
branch: ticket/006-red-team
base_branch: main
test_command: ".venv/bin/pytest tests/test_red_team.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 1
---

## Description
Given an `AttackDirective(category, seed?, budget)`, generate a single-turn adversarial input via the LLM client, send it through the Target Adapter, and return an `AttackAttempt` (with transcript). Sandboxed: talks to the Target only via the Adapter; never writes findings. Uses authorized-security-testing system framing to avoid refusals.

## Acceptance criteria
- [ ] Produces an `AttackAttempt` with a non-empty attack prompt for the directed category.
- [ ] Calls the Target only via the Adapter; performs no store writes to findings.
- [ ] Respects the directive budget (max attempts) and stops when exhausted.

## Test plan (orchestrator authors these)
- unit: `tests/test_red_team.py` (LLM + Adapter mocked) — directive → valid AttackAttempt;
  attack prompt is the LLM output and is non-empty; the directive category drives generation;
  the attack is delivered via the Adapter and the target reply is captured in the transcript;
  sandbox (a real store accrues target_call transcripts but zero findings); budget cap enforced
  (exactly max_attempts LLM+Adapter calls, never more); each attempt is single-turn.
