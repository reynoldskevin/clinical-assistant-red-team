"""Acceptance tests for ticket 035 — refusal-safe LLM unwrap + suite failure isolation.

Reproduces and pins the fix for a live crash: the Anthropic API returned an empty
`content` array (a refusal / content-stop) for a Red Team generation, `forge/llm.py`
did `resp.content[0].text` with no guard → `IndexError`, and `run_suite` had no
failure isolation, so the whole run aborted with `run_end` never written (leaving
`run_active` stuck True).

Two layers are hardened:
  1. `ClaudeClient.complete` — an empty / text-less `content` raises a typed `LLMError`
     (never `IndexError`); a normal response still returns the first text block.
  2. `Runner` — a failed generation is caught, logged as an `attempt_error` event, and
     the run continues; `run_suite` always writes `run_end` (try/finally); and
     `max_failures=K` trips a logged `circuit_breaker` that stops the run cleanly.
"""

from types import SimpleNamespace

import pytest

from forge.llm import ClaudeClient, LLMError
from forge.run import Runner
from forge.schemas import AttackAttempt, Verdict
from forge.store import Store

MESSAGES = [{"role": "user", "content": "x"}]


# --------------------------------------------------------------------------- #
# LLM unwrap fakes
# --------------------------------------------------------------------------- #
class _Msgs:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._resp


class _Client:
    def __init__(self, resp):
        self.messages = _Msgs(resp)


def _resp(content):
    return SimpleNamespace(
        content=content,
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        model="claude-sonnet-5",
    )


def _claude(resp):
    return ClaudeClient(
        api_key="sk-test", client=_Client(resp), backoff=0.0, sleep=lambda s: None
    )


# --------------------------------------------------------------------------- #
# (1) refusal-safe unwrap — empty / text-less content → LLMError, not IndexError
# --------------------------------------------------------------------------- #
def test_empty_content_raises_llm_error_not_indexerror():
    client = _claude(_resp([]))
    with pytest.raises(LLMError):
        client.complete(MESSAGES, model="claude-sonnet-5")


def test_textless_content_block_raises_llm_error():
    # a non-text block (e.g. tool_use) with no usable .text must not crash
    client = _claude(_resp([SimpleNamespace(type="tool_use")]))
    with pytest.raises(LLMError):
        client.complete(MESSAGES, model="claude-sonnet-5")


def test_normal_content_still_returns_first_text():
    client = _claude(_resp([SimpleNamespace(text="hello")]))
    resp = client.complete(MESSAGES, model="claude-sonnet-5")
    assert resp.text == "hello"


def test_empty_content_error_is_not_indexerror_type():
    client = _claude(_resp([]))
    try:
        client.complete(MESSAGES, model="claude-sonnet-5")
    except LLMError:
        pass
    except IndexError:  # pragma: no cover
        pytest.fail("empty content must not surface as a raw IndexError")


# --------------------------------------------------------------------------- #
# Runner fakes
# --------------------------------------------------------------------------- #
def _attempt(category):
    return AttackAttempt(
        category=category,
        prompt="probe",
        target_id="copilot",
        turns=1,
        transcript=[
            {"role": "attacker", "content": "probe"},
            {"role": "target", "answer": "safe", "correlation_id": "c", "status": 200},
        ],
    )


class FaultyRedTeam:
    """Real duck-typed Red Team: raises LLMError for chosen categories, else a probe."""

    def __init__(self, fail_on=frozenset()):
        self.fail_on = set(fail_on)
        self.calls = []

    def run(self, directive, pid):
        self.calls.append(directive.category)
        if directive.category in self.fail_on:
            raise LLMError("LLM returned no text content (empty/refusal)")
        return [_attempt(directive.category)]


class FakeJudge:
    def evaluate(self, attempt, *, ground_truth=None):
        return Verdict(verdict="fail", confidence=0.9, rationale="refused",
                       owasp_web=[], owasp_llm=[])


# --------------------------------------------------------------------------- #
# (2) a failed generation is skipped + logged; the suite completes
# --------------------------------------------------------------------------- #
def test_failed_generation_skips_and_run_continues():
    store = Store(":memory:")
    rt = FaultyRedTeam(fail_on={"state_corruption"})
    runner = Runner(store, rt, FakeJudge(), pid=1)

    summary = runner.run_suite(
        {"prompt_injection": ["a"], "state_corruption": ["b"], "tool_misuse": ["c"]}
    )

    kinds = [e["kind"] for e in store.get_events()]
    assert kinds[0] == "run_start"
    assert kinds[-1] == "run_end", "run_end is written even though a category failed"
    assert "attempt_error" in kinds, "the failed generation is logged, not swallowed silently"
    # the two healthy categories still produced verdicts
    assert kinds.count("verdict") == 2
    # every category was attempted; none aborted the others
    assert rt.calls == ["prompt_injection", "state_corruption", "tool_misuse"]
    assert set(summary.categories) >= {"prompt_injection", "tool_misuse"}


def test_attempt_error_event_names_the_category():
    store = Store(":memory:")
    rt = FaultyRedTeam(fail_on={"state_corruption"})
    runner = Runner(store, rt, FakeJudge(), pid=1)
    runner.run_suite({"state_corruption": ["b"], "tool_misuse": ["c"]})

    errs = [e for e in store.get_events() if e["kind"] == "attempt_error"]
    assert len(errs) == 1
    assert errs[0].get("category") == "state_corruption"


# --------------------------------------------------------------------------- #
# (3) run_end always written even on an unexpected (non-LLMError) exception
# --------------------------------------------------------------------------- #
def test_run_end_written_even_on_unexpected_error():
    class ExplodingRedTeam:
        def run(self, directive, pid):
            raise ValueError("totally unexpected")

    store = Store(":memory:")
    runner = Runner(store, ExplodingRedTeam(), FakeJudge(), pid=1)
    runner.run_suite({"prompt_injection": ["a"]})
    kinds = [e["kind"] for e in store.get_events()]
    assert kinds[0] == "run_start" and kinds[-1] == "run_end"
    assert "attempt_error" in kinds


# --------------------------------------------------------------------------- #
# (4) circuit breaker trips after K failures and still closes the run
# --------------------------------------------------------------------------- #
def test_circuit_breaker_trips_after_max_failures():
    store = Store(":memory:")
    rt = FaultyRedTeam(fail_on={"a", "b", "c"})  # every category fails
    runner = Runner(store, rt, FakeJudge(), pid=1, max_failures=2)

    runner.run_suite({"a": ["1"], "b": ["2"], "c": ["3"]})

    kinds = [e["kind"] for e in store.get_events()]
    assert "circuit_breaker" in kinds, "K failures trip the breaker"
    assert kinds[-1] == "run_end", "the run still closes cleanly on a breaker trip"
    # the breaker stopped the run before every category was attempted
    assert rt.calls == ["a", "b"], "aborted at the threshold, category 'c' never ran"


def test_healthy_run_logs_no_error_or_breaker():
    store = Store(":memory:")
    runner = Runner(store, FaultyRedTeam(fail_on=set()), FakeJudge(), pid=1, max_failures=2)
    runner.run_suite({"prompt_injection": ["a"], "tool_misuse": ["b"]})
    kinds = [e["kind"] for e in store.get_events()]
    assert "attempt_error" not in kinds
    assert "circuit_breaker" not in kinds
    assert kinds[-1] == "run_end"
