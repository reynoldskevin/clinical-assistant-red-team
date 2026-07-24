---
id: 061
title: Baseline latency/throughput metrics + load/stress harness
status: todo
depends_on: []
branch: ticket/061-perf-baseline-load-stress
base_branch: main
test_command: ".venv/bin/pytest tests/test_load_harness.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Per-step latency is captured on `trace_span` events (`tracing.Span.latency_s`) but never
aggregated, and there is no load/stress harness. Add (a) a latency/throughput view over the
recorded spans (p50/p95/max latency per agent + overall throughput) and (b) a self-contained
load harness that drives N (default 100) attack cases through the target adapter's injectable
fake transport — no live sidecar, no network — capturing baseline CPU-free wall metrics. This
turns the existing timing signal into a defensible performance baseline.

## Acceptance criteria
- [ ] `Observability` (or a `forge/perf.py` helper) exposes a latency view derived from
      `kind=="trace_span"` events: per-agent and overall `count`, `p50`, `p95`, `max` of
      `latency_s`, plus an overall `throughput` (spans per second over the observed window).
      Empty input yields zeros, not an error.
- [ ] A load harness in `forge/` (e.g. `forge/load_test.py` with a callable entrypoint) runs
      N cases (default 100, parameterizable) against a `TargetAdapter` built with an INJECTED
      fake transport — it never opens a socket. It returns a summary: cases run, successes,
      failures, total/mean latency, throughput.
- [ ] The harness is deterministic under a fake clock/transport (injectable time source) so the
      test asserts exact aggregates; it does not sleep on the wall clock.
- [ ] The harness records nothing to a live DB by default (uses an in-memory store) and does
      not require ANTHROPIC_API_KEY (it drives the target transport, not an LLM).
- [ ] A CLI/entrypoint is invokable (e.g. `python -m forge.load_test --cases 100`) and prints
      the summary; covered by a smoke assertion on the callable, not a subprocess.

## Test plan (orchestrator authors these)
- unit (`tests/test_load_harness.py`):
  - latency view over seeded trace_span events: per-agent + overall p50/p95/max + throughput; empty -> zeros.
  - harness drives N fake-transport calls, returns summary with correct counts (successes/failures).
  - injected fake clock -> exact latency aggregate; no real sleep.
  - harness uses in-memory store and no API key; 100-case default run completes and summarizes.
