---
id: 026
title: Red Team refusal detection + reframe
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [006, 013]
branch: ticket/026-red-team-refusal
base_branch: main
test_command: ".venv/bin/pytest tests/test_red_team_refusal.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Keep the Red Team from being blocked by the safety filters it is probing: detect when the model refuses to generate an attack, and retry with authorized-testing reframing (bounded attempts). If refusals persist past the cap, emit a typed signal so the Orchestrator/operator can flip to the local/OSS model seam (from ticket 002).

## Acceptance criteria
- [ ] A refusal response is detected (not treated as a valid attack) and retried with reframing, up to a cap.
- [ ] Persistent refusal past the cap emits a typed `refusal-exhausted` signal (does not crash the run).
- [ ] The refusal rate is recorded so it can be measured against the local/OSS-swap decision.

## Test plan (orchestrator authors these)
- unit: `tests/test_red_team_refusal.py` (LLM mocked) — refusal → reframed retry with escalated authorized-testing framing; recovery on a later attempt returns the probe; persistent refusal past the cap → `ProbeGeneration.exhausted` with `signal == "refusal-exhausted"` (no crash); refusal rate recorded across generations.
