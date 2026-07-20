---
id: 002
title: LLM client interface + Claude implementation
status: todo            # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [001]
branch: ticket/002-llm-client
base_branch: main
test_command: ".venv/bin/pytest tests/test_llm_client.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Define an `LLMClient` protocol (so a local/OSS model can be swapped per role later — extension
point) and a `ClaudeClient` implementation over the Anthropic API with retry/backoff and a typed
error result for provider/rate-limit failures. Per-role model selection.

## Acceptance criteria
- [ ] `LLMClient` protocol with `complete(messages, model, ...)`; `ClaudeClient` implements it.
- [ ] Anthropic call is mockable; retry/backoff on transient errors; typed `LLMError` on failure.
- [ ] Model id is per-call/per-role configurable (no hardcoded model).

## Test plan (orchestrator authors these)
- unit: `tests/test_llm_client.py` — mocked success; retry then success; exhausted retries →
  `LLMError`; role→model mapping honored (model passed through, not hardcoded).
