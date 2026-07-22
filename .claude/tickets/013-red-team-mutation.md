---
id: 013
title: Red Team mutation & multi-turn escalation
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [006, 007]
branch: ticket/013-red-team-mutation
base_branch: main
test_command: ".venv/bin/pytest tests/test_red_team_mutation.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Upgrade the Red Team: on a Judge `partial` verdict, autonomously generate a mutation family (N variants — rephrase/encode/indirection/role-play/multi-turn staging) and pursue multi-turn attack sequences, all within budget. The escalation capability lives on `RedTeamAgent` (its trigger — a Judge verdict — is fed in by the caller); the autonomous loop / orchestrator (014, 018) wires it into the live run.

## Acceptance criteria
- [ ] A `partial` verdict triggers generation of N variant attempts (configurable N); a non-partial verdict (`success`/`fail`) triggers none.
- [ ] The mutation family spans the named strategies (rephrase / encode / indirection / role-play / multi-turn staging).
- [ ] Supports a multi-turn attack sequence carried through a single Adapter session (each follow-up turn conditioned on the target's prior reply).
- [ ] Mutation/escalation halts when the directive budget (`max_cost_usd` vs the cost meter) is exhausted.
- [ ] Backward compatible: the existing single-turn `run()` and constructor contract (ticket 006) are unchanged.

## Test plan (orchestrator authors these)
- unit: `tests/test_red_team_mutation.py` (mocked LLM/adapter/meter) — partial → N variants; strategy family covered; multi-turn sequence built through one session with follow-ups conditioned on prior replies; budget exhaustion halts both mutation and multi-turn; non-partial → no escalation.
