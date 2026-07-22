---
id: 018
title: Wire the full autonomous loop
status: todo # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [013, 014, 015, 016, 017]
branch: ticket/018-full-loop
base_branch: ticket/017-regression-harness
attempts: 0
test_command: ".venv/bin/pytest tests/test_full_loop.py -q"
full_suite_command: ".venv/bin/pytest -q"
---

## Description
Compose Orchestrator → Red Team → Judge → Documentation → Harness → Observability into a graph with checkpointed, resumable state, and prove an end-to-end trace from directive to documented + regression-tested finding. Implemented as a stdlib state-graph (nodes + checkpointed resumable state persisted to the store) honoring LangGraph's semantics without adding the dependency to the stdlib-first stack; the LangGraph library remains an optional swap at the same seam.

## Acceptance criteria
- [ ] The graph runs a full cycle end-to-end (mock target/LLM) producing a documented finding + regression case.
- [ ] State is checkpointed after each node; a mid-run resume continues from the last checkpoint without re-doing completed steps.
- [ ] An end-to-end trace (ordered agent events: directive → attack → verdict → vuln_report → regression_case) is captured in Observability.
- [ ] A defended cycle (no exploit) completes without documenting; an Orchestrator halt (no directive) ends the loop cleanly.

## Test plan (orchestrator authors these)
- unit/integration: `tests/test_full_loop.py` (real Orchestrator/Documentation/Harness; mock Red Team/Judge/Adapter) — full cycle → documented finding + regression case; resume from checkpoint does not re-run completed nodes; ordered trace present in Observability; defended cycle documents nothing; orchestrator-halt ends the loop.
