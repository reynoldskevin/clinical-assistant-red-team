"""Acceptance tests for ticket 002 — LLM client interface + Claude implementation.

These tests are the FIXED contract for the LLM seam. They pin:
- `from forge.llm import LLMClient, ClaudeClient, LLMResponse, LLMError`
- `LLMClient` is a (runtime-checkable) protocol with `complete(messages, model, ...)`.
- `ClaudeClient` wraps an injected Anthropic-style client (`.messages.create(...)`), so the
  provider call is fully mockable — no network, no real `anthropic` package needed in tests.
- Transient failures retry with backoff; exhausted retries raise a typed `LLMError`.
- The model id is passed through per call (never hardcoded).

The injected client must expose `.messages.create(model=..., messages=..., max_tokens=...,
system=..., temperature=...)` and return an object shaped like the Anthropic SDK response:
`.content[0].text`, `.usage.input_tokens`, `.usage.output_tokens`, `.model`.
"""

from types import SimpleNamespace

import pytest


MESSAGES = [{"role": "user", "content": "hello"}]


def _fake_response(text="hi there", input_tokens=11, output_tokens=7, model="claude-x"):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model=model,
    )


class _FakeMessages:
    """Stands in for `anthropic.Anthropic().messages`."""

    def __init__(self, side_effect):
        # side_effect: a list; each element is either an Exception (raised) or a response (returned).
        self._side_effect = list(side_effect)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._side_effect.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, side_effect):
        self.messages = _FakeMessages(side_effect)


# A transient, retryable provider error. The default retry policy must recognize a class whose
# name signals rate-limiting as transient.
class RateLimitError(Exception):
    pass


def _make_client(side_effect, **kwargs):
    from forge.llm import ClaudeClient

    calls = []
    kwargs.setdefault("sleep", lambda s: calls.append(s))
    kwargs.setdefault("backoff", 0.0)
    fake = _FakeClient(side_effect)
    client = ClaudeClient(api_key="sk-test", client=fake, **kwargs)
    return client, fake, calls


def test_imports_and_protocol():
    from forge.llm import LLMClient, ClaudeClient

    client, _, _ = _make_client([_fake_response()])
    # ClaudeClient satisfies the runtime-checkable LLMClient protocol.
    assert isinstance(client, LLMClient)


def test_complete_returns_structured_response():
    from forge.llm import LLMResponse

    client, fake, _ = _make_client(
        [_fake_response(text="pwned", input_tokens=42, output_tokens=9)]
    )
    resp = client.complete(MESSAGES, model="claude-sonnet-5")

    assert isinstance(resp, LLMResponse)
    assert resp.text == "pwned"
    assert resp.input_tokens == 42
    assert resp.output_tokens == 9
    # exactly one provider call, no retries on success
    assert len(fake.messages.calls) == 1


def test_model_is_passed_through_not_hardcoded():
    client, fake, _ = _make_client([_fake_response(), _fake_response()])

    client.complete(MESSAGES, model="claude-opus-4-8")
    client.complete(MESSAGES, model="claude-haiku-4-5-20251001")

    used_models = [c["model"] for c in fake.messages.calls]
    assert used_models == ["claude-opus-4-8", "claude-haiku-4-5-20251001"]


def test_messages_are_forwarded():
    client, fake, _ = _make_client([_fake_response()])
    client.complete(MESSAGES, model="claude-sonnet-5")
    assert fake.messages.calls[0]["messages"] == MESSAGES


def test_retry_then_success():
    # two transient failures, then a success → returns the success
    client, fake, sleeps = _make_client(
        [RateLimitError("slow down"), RateLimitError("slow down"), _fake_response(text="ok")],
        max_retries=3,
    )
    resp = client.complete(MESSAGES, model="claude-sonnet-5")
    assert resp.text == "ok"
    # three attempts total; backoff slept between the two retries
    assert len(fake.messages.calls) == 3
    assert len(sleeps) == 2


def test_exhausted_retries_raise_llm_error():
    from forge.llm import LLMError

    client, fake, _ = _make_client(
        [RateLimitError("nope"), RateLimitError("nope"), RateLimitError("nope")],
        max_retries=2,  # → 3 total attempts (1 + 2 retries)
    )
    with pytest.raises(LLMError):
        client.complete(MESSAGES, model="claude-sonnet-5")
    assert len(fake.messages.calls) == 3


def test_llm_error_is_distinct_type():
    from forge.llm import LLMError

    assert issubclass(LLMError, Exception)
    assert LLMError is not Exception


def test_non_transient_error_wrapped_without_retry():
    from forge.llm import LLMError

    # A plain ValueError is not transient → surfaces as LLMError immediately, no retry.
    client, fake, sleeps = _make_client([ValueError("bad request")], max_retries=3)
    with pytest.raises(LLMError):
        client.complete(MESSAGES, model="claude-sonnet-5")
    assert len(fake.messages.calls) == 1
    assert sleeps == []
