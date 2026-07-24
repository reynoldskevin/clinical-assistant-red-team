# Performance Baseline & Regression SLO

Committed performance evidence for the adversarial platform (ticket 068). The
numbers below are captured by `forge.perf.baseline_run(100)` and gated in CI by
`tests/test_perf_baseline.py`.

## Methodology

A single **representative 100-case run** drives the full platform load loop
(`forge.load_test.run_load`) through a **deterministic in-process target** — the
built-in offline transport returns `200 {"answer": "ok"}` with no socket, no
live sidecar, and no `ANTHROPIC_API_KEY`. `forge.perf.baseline_run` wraps that
run in profiling: `time.perf_counter()` for wall time, `time.process_time()`
for CPU, and `tracemalloc` for peak memory (peak bytes / 1024 = KB). Throughput
is `cases / wall_s`.

We deliberately do **not** hammer the live sidecar 100× for a committed,
reproducible artifact: real 100-call LLM/sidecar load is cost-inappropriate and
PHI-inappropriate to bake into the repo. So this baseline characterizes the
**platform's own orchestration + storage overhead**, which is deterministic and
reproducible. Real LLM/target latency is characterized **separately** from the
recorded `trace_span` `latency_s` events aggregated by
`forge/perf.py::latency_view` (per-agent / overall p50/p95/max/throughput). The
two are honestly split: this document is the offline-platform baseline; the
`latency_view` percentiles are the real-LLM-latency view.

## Baseline Metrics

Captured on this machine from a 100-case offline in-process platform load
(`baseline_run(100)`):

- Environment: **Python 3.14** (CPython 3.14.6), **macOS** (Darwin, arm64),
  offline in-process platform load — no network, no API key.

| Metric | Value |
| --- | --- |
| Cases | 100 |
| Wall time (`wall_s`) | 0.0032 s |
| CPU time (`cpu_s`) | 0.0032 s |
| Peak memory (`peak_mem_kb`) | 17.4 KB |
| Throughput (`throughput_cps`) | ~31,000 cases/s |
| Load-summary successes / failures | 100 / 0 |
| Load-summary mean latency (`mean_latency_s`) | ~2.5e-05 s |
| Load-summary total latency (`total_latency_s`) | ~0.0025 s |

Numbers are of that order (sub-4ms wall for 100 cases, tens of KB peak); exact
values vary slightly per run and machine — re-capture with
`python -c "from forge.perf import baseline_run; print(baseline_run(100))"`.

## Bottleneck

The offline baseline shows the **in-process platform is effectively free**: 100
full ask() ops complete in ~3ms of wall time with ~17 KB peak allocation and
tens of thousands of cases/sec of throughput. Orchestration + storage overhead
is therefore **not** the bottleneck.

In a **real** run the wall-time is dominated almost entirely by **LLM calls**
(attacker generation + Judge evaluation + live target/sidecar round-trips). Each
of those is 100s of ms to seconds; the platform glue around them (as the numbers
above demonstrate) is microseconds per case. Any real-run latency budget is an
LLM-latency budget, not a platform-overhead budget.

## Remediation

Because LLM calls dominate, the scaling remediation is **architectural, not
micro-optimization**: batching attacker/Judge requests, caching deterministic
Judge verdicts (already exploited in `RegressionHarness.replay`), sampling /
capping replays, and moving high-volume red-team generation to a
**local-or-OSS red-team model** (ticket 060) instead of the metered frontier
API. See `AI_COST_ANALYSIS.md` for the per-run and at-scale cost/latency
projections that justify this split.

## Regression SLO

`forge.perf.REGRESSION_SLO_SECONDS = 5.0` is the CI budget for a **full
exploit-DB regression scan** — `RegressionHarness.validate()` replaying every
persisted confirmed case with a fake adapter/judge (no LLM). This gates the
platform's scan/replay overhead independently of LLM latency. It is a real,
tight-ish budget (not a no-op): a 25-case full-DB scan must finish well under
5 seconds. Verified in CI by `tests/test_perf_baseline.py`
(`test_regression_scan_meets_slo`), alongside the `baseline_run` metric checks.
