---
id: 002-fix
title: ClaudeClient must not send params the current models reject (temperature; system=None)
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [002]
branch: fix/002-llm-param-compat
base_branch: main
test_command: ".venv/bin/pytest tests/test_llm_client.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The first live smoke run of `forge run` surfaced a blocking defect in the merged `ClaudeClient` (ticket 002): it unconditionally forwards `temperature` to `messages.create`, but the Claude 5 / Opus 4.8 family (the platform's default red_team=`claude-sonnet-5` and judge=`claude-opus-4-8` models) rejects it with HTTP 400 `"temperature is deprecated for this model."` Every real LLM call fails, so the whole live loop is blocked. Fix: do not send `temperature` to the API (drop it, even when a caller passes an explicit value). Also omit `system` from the request when it is `None` (the same param-the-API-does-not-want class of bug, and it mirrors the temperature-free shim proven working end-to-end in the smoke run). Core kwargs (`model`, `messages`, `max_tokens`) and a provided `system` are still forwarded; retry/backoff behavior is unchanged.

## Acceptance criteria
- [ ] `ClaudeClient.complete` never includes `temperature` in the `messages.create` kwargs, even when the caller passes an explicit `temperature`.
- [ ] `system` is forwarded when provided but omitted from the kwargs when `None`.
- [ ] `model`, `messages`, `max_tokens` are still forwarded; existing retry/backoff/error tests still pass unchanged.

## Test plan (orchestrator authors these)
- unit: `tests/test_llm_client.py` — a new locked test asserts `temperature` is absent from every
  recorded `create` call (default and explicit-value paths), `system` is omitted when `None` and
  forwarded when provided, and the core kwargs are present. The pre-existing 002 tests (structured
  response, model pass-through, messages forwarded, retry/backoff, typed error) remain green.
