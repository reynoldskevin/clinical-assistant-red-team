---
id: 024
title: Langfuse self-hosted tracing (agent cost/latency + lineage)
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [016, 018]
branch: ticket/024-tracing
base_branch: main
test_command: ".venv/bin/pytest tests/test_tracing.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Instrument the LangGraph agents with **self-hosted Langfuse** for execution traces: per-agent spans with token/cost/latency and a finding→agent lineage trace. Domain data stays in SQLite; traces stay in-environment (no hosted SaaS). Observability's cost view reads **agent-level** cost from traces, not just platform totals.

## Design note (stdlib-first)
Langfuse is not a runtime dependency (the stack is stdlib-first with a requirements drift guard, and the test plan mocks the Langfuse client). So this ships a pluggable tracing seam — a `Tracer` over an injected Langfuse-shaped client (mock/local) — that honors Langfuse span semantics (per-agent spans carrying token/cost/latency, grouped by trace id for lineage) without adding a hosted-SaaS dependency. Spans are also persisted to the SQLite event log so Observability can read agent-level cost in-environment. Flagged explicitly, as ticket 018 flagged LangGraph.

## Acceptance criteria
- [ ] Each agent step emits a Langfuse span with token, cost, and latency (against a local/mock Langfuse).
- [ ] A confirmed finding can be traced back through the exact agent steps that produced it.
- [ ] Cost is attributable per-agent, not only per-run.

## Test plan (orchestrator authors these)
- unit: `tests/test_tracing.py` (Langfuse client mocked) — spans emitted per agent with cost/latency; lineage resolves finding→steps; per-agent cost rollup correct; Observability reads agent-level cost from persisted spans.
