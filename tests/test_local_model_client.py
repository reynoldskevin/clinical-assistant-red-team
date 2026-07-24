"""Acceptance tests for ticket 060 — local/OSS model client for the Red Team role.

An OpenAI-compatible chat client implements the same `LLMClient.complete(...) -> LLMResponse`
contract as `ClaudeClient`, is injectable with a fake transport (no network), and maps an
OpenAI-shaped chat response into `LLMResponse`. A per-role config seam + factory lets the Red
Team run on that client while the Judge stays on Claude — default behavior unchanged.
"""

import pytest

from forge.llm import (
    LLMClient,
    LLMResponse,
    LLMError,
    ClaudeClient,
    OpenAICompatClient,
    build_llm_client,
)
from forge.config import Config
from forge.run import CostMeter


_BASE_ENV = {"ANTHROPIC_API_KEY": "sk-test", "TARGET_BASE_URL": "http://target"}


def _openai_response(content="pwned", model="llama3", pt=11, ct=22):
    return {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": pt, "completion_tokens": ct},
    }


class _FakeTransport:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        if self.raises is not None:
            raise self.raises
        return self.response


# --------------------------------------------------------------------------- #
# OpenAICompatClient
# --------------------------------------------------------------------------- #
def test_complete_maps_openai_response_to_llmresponse():
    t = _FakeTransport(response=_openai_response(content="exfiltrated", pt=7, ct=9))
    client = OpenAICompatClient("http://localhost:11434", transport=t)
    out = client.complete([{"role": "user", "content": "hi"}], model="llama3")
    assert isinstance(out, LLMResponse)
    assert out.text == "exfiltrated"
    assert out.input_tokens == 7
    assert out.output_tokens == 9
    assert out.model  # non-empty


def test_system_prepended_and_messages_forwarded():
    t = _FakeTransport(response=_openai_response())
    client = OpenAICompatClient("http://localhost:11434", transport=t)
    client.complete([{"role": "user", "content": "attack"}], model="llama3", system="be evil")
    (_url, body) = t.calls[0]
    msgs = body["messages"]
    assert msgs[0] == {"role": "system", "content": "be evil"}
    assert msgs[-1] == {"role": "user", "content": "attack"}
    assert body["model"] == "llama3"


def test_no_system_message_when_absent():
    t = _FakeTransport(response=_openai_response())
    OpenAICompatClient("http://x", transport=t).complete(
        [{"role": "user", "content": "a"}], model="m"
    )
    msgs = t.calls[0][1]["messages"]
    assert all(m["role"] != "system" for m in msgs)


def test_satisfies_llmclient_protocol():
    client = OpenAICompatClient("http://x", transport=_FakeTransport(response=_openai_response()))
    assert isinstance(client, LLMClient)


def test_malformed_response_raises_llmerror():
    client = OpenAICompatClient("http://x", transport=_FakeTransport(response={"nope": 1}))
    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "a"}], model="m")


def test_transport_failure_raises_llmerror():
    client = OpenAICompatClient("http://x", transport=_FakeTransport(raises=RuntimeError("502 Bad Gateway")))
    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "a"}], model="m")


# --------------------------------------------------------------------------- #
# config seam
# --------------------------------------------------------------------------- #
def test_config_default_all_roles_claude():
    cfg = Config.from_env(dict(_BASE_ENV))
    assert set(cfg.providers) >= {"orchestrator", "red_team", "judge", "documentation"}
    for role, p in cfg.providers.items():
        assert p["kind"] == "claude"


def test_config_red_team_openai_compat_only():
    env = dict(_BASE_ENV)
    env["FORGE_CLIENT_RED_TEAM"] = "openai-compat"
    env["FORGE_CLIENT_RED_TEAM_BASE_URL"] = "http://localhost:11434"
    cfg = Config.from_env(env)
    assert cfg.providers["red_team"]["kind"] == "openai-compat"
    assert cfg.providers["red_team"]["base_url"] == "http://localhost:11434"
    # other roles remain claude
    assert cfg.providers["judge"]["kind"] == "claude"


# --------------------------------------------------------------------------- #
# factory
# --------------------------------------------------------------------------- #
def test_factory_selects_per_role_client():
    env = dict(_BASE_ENV)
    env["FORGE_CLIENT_RED_TEAM"] = "openai-compat"
    env["FORGE_CLIENT_RED_TEAM_BASE_URL"] = "http://localhost:11434"
    cfg = Config.from_env(env)

    rt = build_llm_client("red_team", cfg, transport=_FakeTransport(response=_openai_response()))
    assert isinstance(rt, OpenAICompatClient)

    # judge stays on Claude; pass a fake anthropic client so no network/import surprises
    jd = build_llm_client("judge", cfg, claude_client=object())
    assert isinstance(jd, ClaudeClient)


def test_factory_default_is_claude():
    cfg = Config.from_env(dict(_BASE_ENV))
    rt = build_llm_client("red_team", cfg, claude_client=object())
    assert isinstance(rt, ClaudeClient)


# --------------------------------------------------------------------------- #
# metering tolerance for local models
# --------------------------------------------------------------------------- #
def test_cost_meter_tolerates_unknown_local_model():
    meter = CostMeter()  # empty price table
    usd = meter.record("llama3-local", 1000, 2000)
    assert usd == 0.0
    assert meter.total_in == 1000 and meter.total_out == 2000
