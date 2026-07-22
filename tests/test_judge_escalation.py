"""Acceptance tests for ticket 027 — Judge low-confidence escalation + per-category rubric.

Pins the FIXED contract for the reliability-bias upgrade to the Judge (ticket-007
`evaluate()` stays backward compatible):

- `JudgeAgent(..., confidence_threshold=0.6, category_rubrics=None)` — new knobs.
- `should_escalate(verdict) -> bool` — True when `verdict.confidence` is below the
  threshold (a missed vuln costs more than a false alarm → route to human review).
- `review(attempt, *, ground_truth=None) -> EscalationDecision` — evaluates, then
  routes a below-threshold verdict to human review WITHOUT auto-passing it (even a
  low-confidence "fail"/safe verdict escalates).
- `rubric_for(category) -> dict` — a written success/fail/partial spec per category;
  unknown category → a default spec (no crash).
- The per-category rubric is injected into the Judge's prompt.
- `CATEGORY_RUBRIC_VERSION` is defined; every calibration-fixture category has a rubric.
"""

import json

import pytest

from forge.judge import (
    CALIBRATION_FIXTURES,
    CATEGORY_RUBRIC_VERSION,
    CATEGORY_RUBRICS,
    EscalationDecision,
    JudgeAgent,
)
from forge.llm import LLMResponse
from forge.schemas import AttackAttempt

SEED_CATEGORIES = [
    "data_exfiltration",
    "denial_of_service",
    "identity_exploitation",
    "prompt_injection",
    "state_corruption",
    "tool_misuse",
]


class FakeLLM:
    """Returns a canned verdict JSON at a configurable confidence; records prompts."""

    def __init__(self, verdict="success", confidence=0.9):
        self.calls = []
        self._payload = {
            "verdict": verdict,
            "confidence": confidence,
            "rationale": "scored",
            "owasp_web": ["A01:2021-Broken Access Control"],
            "owasp_llm": ["LLM01:Prompt Injection"],
        }

    def complete(self, messages, model, max_tokens=1024, system=None, temperature=0.0):
        self.calls.append({"messages": messages, "model": model, "system": system})
        return LLMResponse(text=json.dumps(self._payload), input_tokens=3,
                           output_tokens=4, model=model)


def _attempt(category="prompt_injection", answer="benign"):
    return AttackAttempt(
        category=category,
        prompt="probe",
        transcript=[
            {"role": "attacker", "content": "probe"},
            {"role": "target", "answer": answer, "correlation_id": "c", "status": 200},
        ],
    )


def _judge(llm, **kw):
    kw.setdefault("model", "claude-opus-4-8")
    return JudgeAgent(llm, **kw)


# --------------------------------------------------------------------------- #
# (1) below-threshold verdict routed to human review, not auto-passed
# --------------------------------------------------------------------------- #
def test_should_escalate_below_and_above_threshold():
    judge = _judge(FakeLLM(), confidence_threshold=0.6)
    from forge.schemas import Verdict

    below = Verdict(verdict="fail", confidence=0.4, rationale="unsure",
                    owasp_web=[], owasp_llm=[])
    at = Verdict(verdict="fail", confidence=0.6, rationale="ok", owasp_web=[], owasp_llm=[])
    above = Verdict(verdict="success", confidence=0.95, rationale="clear",
                    owasp_web=[], owasp_llm=[])
    assert judge.should_escalate(below) is True
    assert judge.should_escalate(at) is False, "at threshold is not below it"
    assert judge.should_escalate(above) is False


def test_review_routes_low_confidence_to_human_without_autopass():
    # A low-confidence "fail" (target looks SAFE) must NOT be silently accepted as safe.
    judge = _judge(FakeLLM(verdict="fail", confidence=0.35), confidence_threshold=0.6)
    decision = judge.review(_attempt())
    assert isinstance(decision, EscalationDecision)
    assert decision.escalated is True, "low-confidence safe verdict routes to human review"
    assert decision.verdict.verdict == "fail", "the underlying verdict is preserved, not flipped"
    assert decision.reason and "confidence" in decision.reason.lower()


def test_review_high_confidence_not_escalated():
    judge = _judge(FakeLLM(verdict="success", confidence=0.92), confidence_threshold=0.6)
    decision = judge.review(_attempt())
    assert decision.escalated is False
    assert decision.reason is None


# --------------------------------------------------------------------------- #
# (2) per-category rubric — written spec applied per category
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("category", SEED_CATEGORIES)
def test_rubric_for_every_seed_category(category):
    judge = _judge(FakeLLM())
    rubric = judge.rubric_for(category)
    assert set(["success", "fail", "partial"]).issubset(rubric), \
        f"{category} needs a success/fail/partial definition"
    assert all(rubric[k].strip() for k in ("success", "fail", "partial")), \
        "each definition is written, non-empty"


def test_rubric_for_unknown_category_returns_default_no_crash():
    judge = _judge(FakeLLM())
    rubric = judge.rubric_for("no_such_category_xyz")
    assert set(["success", "fail", "partial"]).issubset(rubric)
    assert all(rubric[k].strip() for k in ("success", "fail", "partial"))


def test_evaluate_injects_per_category_rubric_into_prompt():
    llm = FakeLLM()
    judge = _judge(llm)
    judge.evaluate(_attempt(category="prompt_injection"))
    blob = str(llm.calls[0]["messages"]) + " " + str(llm.calls[0]["system"])
    success_def = judge.rubric_for("prompt_injection")["success"]
    assert success_def in blob, "the per-category success definition is applied in the prompt"


# --------------------------------------------------------------------------- #
# (3) versioned + covered by the calibration set
# --------------------------------------------------------------------------- #
def test_category_rubric_is_versioned():
    assert isinstance(CATEGORY_RUBRIC_VERSION, str) and CATEGORY_RUBRIC_VERSION


def test_every_calibration_category_has_a_rubric():
    for fx in CALIBRATION_FIXTURES:
        category = fx["attempt"].category
        assert category in CATEGORY_RUBRICS, \
            f"calibration fixture category {category!r} lacks a per-category rubric"


# --------------------------------------------------------------------------- #
# backward compatibility — ticket 007 evaluate() unchanged in behavior
# --------------------------------------------------------------------------- #
def test_evaluate_still_returns_verdict():
    v = _judge(FakeLLM(verdict="success", confidence=0.9)).evaluate(_attempt())
    assert v.verdict == "success"
