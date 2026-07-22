---
id: 025
title: Agent failure-handling policy + circuit breaker
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [003, 018]
branch: ticket/025-failure-handling
base_branch: main
test_command: ".venv/bin/pytest tests/test_failure_handling.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Turn the typed error results into a defined recovery policy: transient errors (target unreachable, judge timeout, rate limit) → bounded retry-with-backoff → skip/redirect; hard errors (budget exceeded, no-signal) → Orchestrator redirects or halts. A **circuit breaker** aborts a run after K agent failures and surfaces it to the operator (no cascading loop).

## Acceptance criteria
- [ ] A transient error retries with backoff up to N, then skips/redirects — not a crash.
- [ ] A hard error routes to the Orchestrator's halt/redirect path.
- [ ] K failures within a run trips the circuit breaker: run aborts, reason logged to `events`.

## Test plan (orchestrator authors these)
- unit: `tests/test_failure_handling.py` — transient → retry then skip; transient that recovers → ok; hard → halt; classification of each ErrorType; K failures → breaker aborts (CircuitOpen) + logs a `circuit_breaker` event.
