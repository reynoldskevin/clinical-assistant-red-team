"""Ticket 053 — honest OWASP coverage from Judge-observed verdict tags.

`by_owasp` must count distinct verdicts per OWASP id from the tags the Judge put on
each verdict event — NOT the static case-catalog cross-product. This requires the
Runner to persist `owasp_web`/`owasp_llm` on the verdict event (a wire-crossing
change, so a round-trip contract test pins the shape both sides agree on).
"""

import types

from forge.observability import Observability
from forge.run import CostMeter, Runner
from forge.schemas import AttackAttempt, AttackDirective, Verdict
from forge.store import Store


def _verdict_ev(**kw):
    base = {"kind": "verdict", "attempt_id": 1, "category": "prompt_injection",
            "verdict": "fail", "confidence": 0.8}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# consumer: coverage() from verdict-event tags
# --------------------------------------------------------------------------- #
def test_by_owasp_counts_verdicts_per_id_from_verdict_tags():
    s = Store(":memory:")
    s.append_event(_verdict_ev(attempt_id=1, category="prompt_injection",
                               owasp_web=[], owasp_llm=["LLM01:Prompt Injection"]))
    s.append_event(_verdict_ev(attempt_id=2, category="prompt_injection",
                               owasp_web=["A03:2021-Injection"],
                               owasp_llm=["LLM01:Prompt Injection"]))
    s.append_event(_verdict_ev(attempt_id=3, category="denial_of_service",
                               owasp_web=["A05:2021-Security Misconfiguration"], owasp_llm=[]))
    cov = Observability(s).coverage()
    assert cov["by_category"] == {"prompt_injection": 2, "denial_of_service": 1}
    assert cov["by_owasp"]["LLM01:Prompt Injection"] == 2
    assert cov["by_owasp"]["A03:2021-Injection"] == 1
    assert cov["by_owasp"]["A05:2021-Security Misconfiguration"] == 1


def test_by_owasp_independent_of_cases_catalog():
    s = Store(":memory:")
    s.append_event(_verdict_ev(owasp_web=[], owasp_llm=["LLM01:Prompt Injection"]))
    no_cases = Observability(s).coverage()["by_owasp"]
    with_cases = Observability(
        s, cases=[types.SimpleNamespace(category="prompt_injection",
                                        owasp_web=["A01:2021-Broken Access Control"],
                                        owasp_llm=[])],
    ).coverage()["by_owasp"]
    assert no_cases == with_cases == {"LLM01:Prompt Injection": 1}


def test_untagged_verdict_counts_only_toward_category():
    s = Store(":memory:")
    s.append_event(_verdict_ev(owasp_web=[], owasp_llm=[]))
    cov = Observability(s).coverage()
    assert cov["by_category"] == {"prompt_injection": 1}
    assert cov["by_owasp"] == {}


def test_id_in_both_lists_counts_once_per_verdict():
    s = Store(":memory:")
    s.append_event(_verdict_ev(owasp_web=["LLM01:Prompt Injection"],
                               owasp_llm=["LLM01:Prompt Injection"]))
    assert Observability(s).coverage()["by_owasp"]["LLM01:Prompt Injection"] == 1


# --------------------------------------------------------------------------- #
# producer + round-trip contract (Runner -> verdict event -> coverage)
# --------------------------------------------------------------------------- #
class _RT:
    def run(self, directive, pid):
        return [AttackAttempt(
            category=directive.category, prompt="p",
            transcript=[{"role": "attacker", "content": "x"},
                        {"role": "target", "answer": "y"}])]


class _TagJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="fail", confidence=0.8, rationale="r",
                       owasp_web=["A05:2021-Security Misconfiguration"],
                       owasp_llm=["LLM04:Model Denial of Service"])


class _Orch:
    def __init__(self, ds):
        self._d = list(ds)

    def next_directive(self):
        return self._d.pop(0) if self._d else None


def test_runner_persists_owasp_on_verdict_and_coverage_reflects_it():
    s = Store(":memory:")
    orch = _Orch([AttackDirective(category="denial_of_service", max_attempts=1)])
    Runner(s, _RT(), _TagJudge(), pid=1, cost_meter=CostMeter(),
           orchestrator=orch).run_autonomous()

    v = next(e for e in s.get_events() if e["kind"] == "verdict")
    assert v["owasp_web"] == ["A05:2021-Security Misconfiguration"]
    assert v["owasp_llm"] == ["LLM04:Model Denial of Service"]

    cov = Observability(s).coverage()
    assert cov["by_owasp"]["A05:2021-Security Misconfiguration"] == 1
    assert cov["by_owasp"]["LLM04:Model Denial of Service"] == 1
