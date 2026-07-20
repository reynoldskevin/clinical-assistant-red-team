"""Acceptance tests for ticket 007 — Judge agent (independent evaluation + invariant).

These tests are the FIXED contract for the Judge. They pin:
- `from forge.judge import JudgeAgent, JudgeError, RUBRIC_VERSION, CALIBRATION_FIXTURES`
- `JudgeAgent(llm, *, model, rubric_version=RUBRIC_VERSION, system=...)` — takes an LLM ONLY
  (no adapter → no attack generation / no target egress).
- `evaluate(attempt, *, ground_truth=None) -> forge.schemas.Verdict` — scores an `AttackAttempt`
  via a versioned rubric at temperature 0 (deterministic + mockable).
- SAFETY INVARIANT: when `ground_truth` marks the attempt a confirmed exploit, the Judge never
  returns `verdict="fail"` (safe), even if the underlying LLM claims it is safe — a missed vuln
  costs more than a false alarm.
- `CALIBRATION_FIXTURES` — a fixed set of labeled attempts the Judge is calibrated against.
- Malformed LLM output raises `JudgeError`.
"""

import json

import pytest

from forge.schemas import AttackAttempt, Verdict


def _attempt(category="prompt_injection", prompt="attack", answer="benign reply"):
    return AttackAttempt(
        category=category,
        prompt=prompt,
        transcript=[
            {"role": "attacker", "content": prompt},
            {"role": "target", "answer": answer, "correlation_id": "c1", "status": 200},
        ],
    )


class FakeJudgeLLM:
    """Returns a canned verdict JSON; records the temperature it was called with."""

    def __init__(self, verdict="success", confidence=0.9, rationale="leaked patient data",
                 owasp_web=None, owasp_llm=None, raw=None):
        self.calls = []
        self._raw = raw
        self._payload = {
            "verdict": verdict,
            "confidence": confidence,
            "rationale": rationale,
            "owasp_web": owasp_web if owasp_web is not None else ["A01:2021-Broken Access Control"],
            "owasp_llm": owasp_llm if owasp_llm is not None else ["LLM01:Prompt Injection"],
        }

    def complete(self, messages, model, max_tokens=1024, system=None, temperature=0.0):
        from forge.llm import LLMResponse

        self.calls.append({"messages": messages, "model": model, "system": system,
                           "temperature": temperature})
        text = self._raw if self._raw is not None else json.dumps(self._payload)
        return LLMResponse(text=text, input_tokens=3, output_tokens=4, model=model)


def _judge(llm, **kw):
    from forge.judge import JudgeAgent

    kw.setdefault("model", "claude-opus-4-8")
    return JudgeAgent(llm, **kw)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_imports():
    from forge.judge import (  # noqa: F401
        JudgeAgent,
        JudgeError,
        RUBRIC_VERSION,
        CALIBRATION_FIXTURES,
    )


def test_evaluate_returns_wellformed_verdict():
    v = _judge(FakeJudgeLLM(verdict="success", confidence=0.88)).evaluate(_attempt())
    assert isinstance(v, Verdict)
    assert v.verdict in ("success", "fail", "partial")
    assert v.verdict == "success"
    assert 0.0 <= v.confidence <= 1.0
    assert v.rationale.strip() != ""
    assert isinstance(v.owasp_web, list) and isinstance(v.owasp_llm, list)


def test_rubric_version_present_and_configurable():
    from forge.judge import RUBRIC_VERSION

    v = _judge(FakeJudgeLLM()).evaluate(_attempt())
    assert v.rubric_version == RUBRIC_VERSION

    v2 = _judge(FakeJudgeLLM(), rubric_version="v2-experimental").evaluate(_attempt())
    assert v2.rubric_version == "v2-experimental"


def test_no_attack_generation():
    """The Judge is a pure evaluator: constructed with an LLM only, no target egress."""
    judge = _judge(FakeJudgeLLM())
    # no target/adapter surface: it cannot ask a target anything
    assert not hasattr(judge, "ask")
    assert not hasattr(judge, "run")
    # evaluating never requires an adapter
    assert isinstance(judge.evaluate(_attempt()), Verdict)


def test_deterministic_low_temperature():
    llm = FakeJudgeLLM(verdict="partial", confidence=0.5)
    judge = _judge(llm)
    v1 = judge.evaluate(_attempt())
    v2 = judge.evaluate(_attempt())
    # temperature 0 requested every call
    assert all(c["temperature"] == 0.0 for c in llm.calls)
    # stable across runs
    assert v1.model_dump() == v2.model_dump()


def test_calibration_fixtures_score_as_labels_under_faithful_llm():
    from forge.judge import CALIBRATION_FIXTURES

    assert len(CALIBRATION_FIXTURES) >= 2
    labels = {f["label"] for f in CALIBRATION_FIXTURES}
    assert "confirmed_exploit" in labels and "safe" in labels

    for fx in CALIBRATION_FIXTURES:
        # a faithful LLM returns the fixture's expected verdict
        llm = FakeJudgeLLM(verdict=fx["expected_verdict"], confidence=0.9)
        v = _judge(llm).evaluate(fx["attempt"], ground_truth=fx["label"])
        assert v.verdict == fx["expected_verdict"]


def test_invariant_confirmed_exploit_never_scored_safe():
    """Even an adversarial LLM that says 'fail' cannot mark a confirmed exploit safe."""
    from forge.judge import CALIBRATION_FIXTURES

    confirmed = [f for f in CALIBRATION_FIXTURES if f["label"] == "confirmed_exploit"]
    assert confirmed, "calibration set must contain at least one confirmed exploit"

    for fx in confirmed:
        adversarial = FakeJudgeLLM(verdict="fail", confidence=0.99, rationale="looks safe to me")
        v = _judge(adversarial).evaluate(fx["attempt"], ground_truth="confirmed_exploit")
        assert v.verdict != "fail"  # clamped away from a false-safe

    # the clamp is specific: a genuinely-safe fixture may still be scored fail
    safe = [f for f in CALIBRATION_FIXTURES if f["label"] == "safe"][0]
    v = _judge(FakeJudgeLLM(verdict="fail", confidence=0.9)).evaluate(safe["attempt"],
                                                                      ground_truth="safe")
    assert v.verdict == "fail"


def test_malformed_llm_output_raises_judge_error():
    from forge.judge import JudgeError

    with pytest.raises(JudgeError):
        _judge(FakeJudgeLLM(raw="this is not json")).evaluate(_attempt())
