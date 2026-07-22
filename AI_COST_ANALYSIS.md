# AI Cost Analysis

This report grounds the platform's AI spend in the recorded production cost rows and projects the cost of running the adversarial suite at production scale. The projection is deliberately **not** a linear token×runs estimate: each scale tier forces a distinct architectural change that bends the cost curve sub-linear.

## Actual development spend

- **Total dev spend:** $3.33 (across 92 attempts / cost rows)
- **Tokens:** 113,949 input / 38,656 output
- **Per-attempt:** $0.0362
- **Model tiers:** Red Team = `claude-sonnet-5` ($3 / $15 per 1M in/out), Judge = `claude-opus-4-8` ($15 / $75 per 1M in/out)

### Per-category spend

| Category | USD |
| --- | ---: |
| prompt_injection | $0.5615 |
| identity_exploitation | $0.6120 |
| data_exfiltration | $0.5577 |
| denial_of_service | $0.5423 |
| state_corruption | $0.5319 |
| tool_misuse | $0.5250 |

## Production cost projections

Naive linear cost assumes every run costs the dev-measured $0.0362/attempt with no reuse. The mitigated line applies the architectural lever each tier forces.

| Runs | Naive linear $ | Projected $ (mitigated) | Effective $/run | Architectural change |
| ---: | ---: | ---: | ---: | --- |
| 100 | $3.62 | $3.62 | $0.0362 | **Direct API calls** — No change: dev-scale volume is negligible, call the API directly. |
| 1,000 | $36.20 | $25.34 | $0.0253 | **Prompt caching** — Cache the static system prompts and per-category rubrics that dominate input tokens, cutting input cost ~30%. |
| 10,000 | $361.98 | $162.89 | $0.0163 | **Request batching + caching** — Amortize fixed prompt overhead across batched Judge/Red-Team calls via the Batches API (~50% off, off-peak throughput). |
| 100,000 | $3,619.78 | $723.96 | $0.0072 | **Suite sampling + local models** — Stratified sampling of the case corpus instead of full re-runs, and move Red Team / first-pass Judge to a local or cheaper model tier, reserving Opus for escalations only. |

## Why the curve is sub-linear

A pure token×runs model draws a straight line: 100,000 runs would cost $3,619.78. That is wrong, because fixed prompt overhead is paid once and reused, and not every run needs the most expensive model.

- **100 runs** — no change; direct API calls; dev-scale cost is negligible.
- **1,000 runs** — **prompt caching**: the static system prompts and per-category rubrics dominate input tokens; caching them cuts input cost ~30%.
- **10,000 runs** — **request batching** + aggressive caching: amortize fixed prompt overhead across batched Judge/Red-Team calls (Anthropic Batches API ~50% off, off-peak throughput).
- **100,000 runs** — **suite sampling** + **local**/cheaper models: stratified sampling of the case corpus instead of full re-runs, and moving Red Team / first-pass Judge to a local or cheaper model tier, reserving Opus for escalations only.

The result: the naive line rises linearly with runs, while the mitigated line flattens — each order-of-magnitude increase in scale buys a cheaper effective per-run cost, not a constant one.
