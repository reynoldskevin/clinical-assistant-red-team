---
id: 035
title: Refusal-safe LLM unwrap + suite failure isolation
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [002, 009]
branch: ticket/035-refusal-safe-run
base_branch: main
test_command: ".venv/bin/pytest tests/test_refusal_safe_run.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
A live suite run died mid-flight when the Anthropic API returned an empty `content` array (a model refusal / content-stop) for a Red Team generation: `forge/llm.py` unwrapped `resp.content[0].text` with no guard, raised `IndexError`, and — because `run_suite` had no failure isolation — the exception aborted the whole run with `run_end` never written, leaving the dashboard's `run_active` stuck `True`. This hardens both layers: the LLM unwrap becomes refusal-safe (a blockless/empty response surfaces a typed `LLMError`, not an `IndexError`), and the Runner isolates per-attempt failures (skip + log and continue), always writes `run_end` via `try/finally`, and trips a bounded circuit breaker after K failures in a run.

## Acceptance criteria
- [ ] An empty / text-less LLM `content` response raises a typed `LLMError` (never `IndexError`); a normal response still returns the first text block.
- [ ] A failed generation for one attempt is caught, logged as an `attempt_error` event, and the run continues (other categories/attempts still produce verdicts) — one bad generation never aborts the suite.
- [ ] `run_suite` always appends `run_end` even when a category raises (via `try/finally`), so `run_active` can never get stuck.
- [ ] With `max_failures=K`, K failures in a run trip a circuit breaker: a `circuit_breaker` event is logged, the run stops early, and `run_end` is still written.

## Test plan (orchestrator authors these)
- unit: `tests/test_refusal_safe_run.py` — empty/text-less `content` → `LLMError` (not IndexError); normal content still returns text; a faulty red-team generation is skipped+logged and the suite completes with `run_end` last; `max_failures` trips a logged circuit breaker and still closes the run cleanly; a healthy run logs no `attempt_error`/`circuit_breaker`.
