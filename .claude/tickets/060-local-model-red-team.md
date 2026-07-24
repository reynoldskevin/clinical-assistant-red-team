---
id: 060
title: Local/OSS model client for the Red Team role
status: todo
depends_on: []
branch: ticket/060-local-model-red-team
base_branch: main
test_command: ".venv/bin/pytest tests/test_local_model_client.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The Red Team consumes the `LLMClient` protocol, but only a Claude-backed client is ever built,
and the client is constructed once and shared across roles — so there is no way to run the Red
Team on a local/OSS model to mitigate refusals and cost. Add an OpenAI-compatible chat client
(works against Ollama / any OpenAI-compatible `/v1/chat/completions` endpoint) that implements
`LLMClient.complete(...) -> LLMResponse`, plus a per-role client-selection seam in config so the
Red Team role can be pointed at that endpoint while the Judge stays on Claude. No changes to
`RedTeamAgent`, `Runner`, or the protocol.

## Acceptance criteria
- [ ] A new client (e.g. `OpenAICompatClient`) implements the `LLMClient` protocol:
      `complete(messages, model, max_tokens=1024, system=None, temperature=0.0) -> LLMResponse`.
      It is injectable with a fake HTTP transport (no real network in tests), maps an
      OpenAI-shaped chat response into `LLMResponse(text, input_tokens, output_tokens, model)`,
      prepends `system` as a system message when provided, and satisfies
      `isinstance(client, LLMClient)`.
- [ ] The client raises the shared typed `LLMError` on transport/protocol failure (malformed
      response, non-2xx), consistent with `ClaudeClient`; it does not leak the raw exception type.
- [ ] Config gains a per-role client-kind seam: an env override (e.g.
      `FORGE_CLIENT_<ROLE>` / `providers` map) selects `claude` (default) or an
      OpenAI-compatible endpoint (base_url + model) for a role, WITHOUT changing the default
      behavior (all roles still default to Claude; `test_config.py` stays green).
- [ ] A small factory builds the right `LLMClient` per role from config, so the Red Team role
      can be wired to the local client while other roles keep Claude. The factory is unit-tested
      independently of `run.py` network setup.
- [ ] Cost metering does not crash for a local model absent from the price table — an unknown
      model meters at $0 (or a configured local rate) rather than raising.
- [ ] Existing `tests/test_llm_client.py` and `tests/test_config.py` stay green.

## Test plan (orchestrator authors these)
- unit (`tests/test_local_model_client.py`):
  - OpenAICompatClient.complete maps a fake OpenAI chat JSON -> LLMResponse (text + token counts + model).
  - system prompt injected as a system message; messages forwarded; isinstance LLMClient.
  - malformed / non-2xx response -> LLMError.
  - config seam: FORGE_CLIENT_RED_TEAM=openai-compat (+ base_url/model) selects the compat client
    for red_team only; default (unset) -> Claude for all roles.
  - factory returns the compat client for red_team and a Claude client for judge given that config.
  - CostMeter tolerates an unknown/local model id (no KeyError; $0 or configured rate).
