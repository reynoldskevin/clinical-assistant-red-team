---
id: 068
title: Performance baseline artifact + regression SLO verified in CI
status: todo
depends_on: []
branch: ticket/068-perf-baseline-and-slo
base_branch: main
test_command: ".venv/bin/pytest tests/test_perf_baseline.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Ticket 061 built the perf TOOLING (`forge/perf.py` latency view, `forge/load_test.py` load
harness) but the brief's optional perf deliverable also wants captured EVIDENCE: baseline
CPU/memory/latency/throughput profiles under a representative 100-case run, a bottleneck
analysis with the architectural fix, and a regression-scan SLO verified in CI. Add a profiled
`baseline_run` (wall/CPU/peak-memory + throughput over the offline 100-case platform load),
commit a `PERF_BASELINE.md` capturing the numbers + methodology + bottleneck + remediation, and
add a deterministic regression-SLO test that gates the full-DB regression scan under a documented
time budget.

## Acceptance criteria
- [ ] `forge.perf.baseline_run(cases=100, *, transport=None, store=None) -> dict` runs the
      offline load harness under profiling and returns at least: `cases`, `wall_s`, `cpu_s`,
      `peak_mem_kb`, `throughput_cps` (cases per wall-second), and `load_summary` (the
      `run_load` dict). All numeric values are non-negative; it needs no network and no
      ANTHROPIC_API_KEY (drives the fake target transport).
- [ ] `forge.perf.REGRESSION_SLO_SECONDS` is a documented module constant (a real, tight-ish
      budget, not a no-op) — the deterministic full-DB regression scan must complete under it.
- [ ] A regression-SLO test seeds N confirmed cases into a store, runs
      `RegressionHarness.validate()` over the whole DB with fake adapter/judge (no LLM), and
      asserts it completes within `REGRESSION_SLO_SECONDS` — a CI gate on the platform's
      scan/replay overhead (independent of LLM latency).
- [ ] `PERF_BASELINE.md` exists at the repo root with sections: `Methodology`,
      `Baseline Metrics` (a table of the captured wall/CPU/memory/latency/throughput numbers
      from a 100-case run, with the environment noted), `Bottleneck`, `Remediation`, and
      `Regression SLO`. It states the 100-case methodology, names the offline-load vs
      real-LLM-latency split honestly, cross-references `AI_COST_ANALYSIS.md` for the scaling
      remediation, and cites the SLO test.
- [ ] No behavior change to existing perf/load/regression code beyond additive functions; full
      suite stays green.

## Test plan (orchestrator authors these)
- unit (`tests/test_perf_baseline.py`):
  - `baseline_run(cases=N)` returns the documented keys, `cases == N`, all metrics non-negative,
    `load_summary["cases"] == N`; runs offline (no API key).
  - regression SLO: seed N cases, time `validate()` over the full DB, assert `< REGRESSION_SLO_SECONDS`
    and that the budget is meaningfully small (not a no-op).
  - `PERF_BASELINE.md` present with all required sections + a metrics table + the 100-case
    methodology + `AI_COST_ANALYSIS.md` cross-reference + the SLO test citation.
