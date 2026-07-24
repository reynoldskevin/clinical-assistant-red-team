"""Acceptance tests for ticket 059 — Judge panel (majority vote).

A ``JudgePanel`` duck-types the Judge's ``evaluate(attempt, *, ground_truth=None) -> Verdict``
interface but runs N members and returns the MAJORITY verdict, so a single outlier can't flip
the outcome. Confidence is the mean over the winning-verdict members; owasp tags are the union
of the winners; a tie falls back to a conservative tie-breaker.
"""

import pytest

from forge.schemas import Verdict
from forge.judge import JudgePanel


def _v(verdict, confidence=0.8, owasp_web=None, owasp_llm=None, rationale="r"):
    return Verdict(
        verdict=verdict,
        confidence=confidence,
        rationale=rationale,
        owasp_web=owasp_web or [],
        owasp_llm=owasp_llm or [],
    )


class _FakeJudge:
    """A member that returns a canned verdict and records how it was called."""

    def __init__(self, verdict):
        self._verdict = verdict
        self.calls = []

    def evaluate(self, attempt, *, ground_truth=None):
        self.calls.append((attempt, ground_truth))
        return self._verdict


_ATTEMPT = object()  # panel must not care about the attempt's concrete type


# --------------------------------------------------------------------------- #
def test_majority_verdict_wins_over_outlier():
    members = [_FakeJudge(_v("fail", 0.8)), _FakeJudge(_v("fail", 0.6)), _FakeJudge(_v("success", 0.9))]
    panel = JudgePanel(members)
    out = panel.evaluate(_ATTEMPT)
    assert isinstance(out, Verdict)
    assert out.verdict == "fail"  # 2/3 majority beats the lone success
    # confidence = mean of the members that voted for the winner
    assert out.confidence == pytest.approx((0.8 + 0.6) / 2)


def test_tie_falls_back_to_conservative_tie_breaker():
    members = [_FakeJudge(_v("success")), _FakeJudge(_v("fail")), _FakeJudge(_v("partial"))]
    panel = JudgePanel(members)  # default tie_breaker
    assert panel.evaluate(_ATTEMPT).verdict == "partial"

    two_way = [_FakeJudge(_v("success")), _FakeJudge(_v("fail"))]
    assert JudgePanel(two_way).evaluate(_ATTEMPT).verdict == "partial"


def test_owasp_tags_are_unioned_across_winning_members():
    members = [
        _FakeJudge(_v("fail", owasp_llm=["LLM01:Prompt Injection"])),
        _FakeJudge(_v("fail", owasp_web=["A01:2021-Broken Access Control"], owasp_llm=["LLM01:Prompt Injection", "LLM06:Sensitive Information Disclosure"])),
        _FakeJudge(_v("success", owasp_llm=["LLM09:Overreliance"])),  # loser, excluded
    ]
    out = JudgePanel(members).evaluate(_ATTEMPT)
    assert out.verdict == "fail"
    assert set(out.owasp_llm) == {"LLM01:Prompt Injection", "LLM06:Sensitive Information Disclosure"}
    assert set(out.owasp_web) == {"A01:2021-Broken Access Control"}
    # loser's tag must not leak in
    assert "LLM09:Overreliance" not in out.owasp_llm


def test_each_member_called_once_and_ground_truth_forwarded():
    members = [_FakeJudge(_v("fail")), _FakeJudge(_v("fail")), _FakeJudge(_v("success"))]
    JudgePanel(members).evaluate(_ATTEMPT, ground_truth="confirmed_exploit")
    for m in members:
        assert len(m.calls) == 1
        assert m.calls[0] == (_ATTEMPT, "confirmed_exploit")


def test_rationale_reflects_the_tally():
    members = [_FakeJudge(_v("fail")), _FakeJudge(_v("fail")), _FakeJudge(_v("success"))]
    out = JudgePanel(members).evaluate(_ATTEMPT)
    assert "2" in out.rationale and "3" in out.rationale  # e.g. "2/3 fail"
    assert out.rationale.strip() != ""


def test_size_one_panel_is_passthrough():
    v = _v("partial", 0.55, owasp_llm=["LLM01:Prompt Injection"])
    out = JudgePanel([_FakeJudge(v)]).evaluate(_ATTEMPT)
    assert out.verdict == "partial"
    assert out.confidence == pytest.approx(0.55)
    assert out.owasp_llm == ["LLM01:Prompt Injection"]


def test_panel_duck_types_as_a_judge():
    panel = JudgePanel([_FakeJudge(_v("fail"))])
    assert hasattr(panel, "evaluate")
    assert isinstance(panel.evaluate(_ATTEMPT), Verdict)
