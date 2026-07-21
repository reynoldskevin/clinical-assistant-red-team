"""Acceptance tests for ticket 016 — Observability read-model + metrics.

These tests are the FIXED contract for the read-model. They pin:
- `from forge.observability import Observability`
- `Observability(store, *, cases=None)` derives, over the store's events/findings/cost rows,
  the six required views:
    1. coverage        — categories tested + case count each, AND per-OWASP (via `cases` mapping)
    2. pass_fail       — exploited/defended/partial + pass_rate, per category AND per target version
    3. resilience_trend — pass_rate over target versions, ordered
    4. finding_lifecycle — open / in_progress / resolved counts
    5. cost            — total + per-category USD/tokens and a per-attempt scaling rate
    6. agent_activity  — ordered per-agent action log
  plus `snapshot()` combining all six.
- Verdict semantics: a verdict "success" = attack worked = target EXPLOITED; "fail" = target
  DEFENDED. pass_rate = defended / attempts.
"""

from types import SimpleNamespace

import pytest

from forge.store import Store
from forge.observability import Observability


# category -> OWASP mapping (duck-typed like forge.evals.EvalCase)
CASES = [
    SimpleNamespace(category="prompt_injection", owasp_web=[], owasp_llm=["LLM01:Prompt Injection"]),
    SimpleNamespace(
        category="data_exfiltration",
        owasp_web=["A01:2021-Broken Access Control"],
        owasp_llm=["LLM06:Sensitive Information Disclosure"],
    ),
]


def _seed():
    """A controlled run history: 7 verdicts across 2 categories and 2 target versions."""
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "target_version": "v1"})
    s.append_event({"kind": "attack", "attempt_id": 1, "category": "prompt_injection", "target_version": "v1"})
    # v1: prompt_injection -> 1 success (exploited) + 1 fail (defended); data_exfil -> 2 fail
    s.append_event({"kind": "verdict", "attempt_id": 1, "category": "prompt_injection", "verdict": "success", "confidence": 0.9, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 2, "category": "prompt_injection", "verdict": "fail", "confidence": 0.8, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 3, "category": "data_exfiltration", "verdict": "fail", "confidence": 0.7, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 4, "category": "data_exfiltration", "verdict": "fail", "confidence": 0.7, "target_version": "v1"})
    # v2: all defended (resilience improved)
    s.append_event({"kind": "verdict", "attempt_id": 5, "category": "prompt_injection", "verdict": "fail", "confidence": 0.8, "target_version": "v2"})
    s.append_event({"kind": "verdict", "attempt_id": 6, "category": "prompt_injection", "verdict": "fail", "confidence": 0.8, "target_version": "v2"})
    s.append_event({"kind": "verdict", "attempt_id": 7, "category": "data_exfiltration", "verdict": "fail", "confidence": 0.7, "target_version": "v2"})
    s.append_event({"kind": "run_end"})
    # findings across the lifecycle
    s.insert_finding({"severity": "high", "attack_category": "prompt_injection", "target_version": "v1", "status": "open"})
    s.insert_finding({"severity": "medium", "attack_category": "prompt_injection", "target_version": "v1", "status": "in_progress"})
    s.insert_finding({"severity": "low", "attack_category": "data_exfiltration", "target_version": "v1", "status": "resolved"})
    # cost rows
    s.insert_cost({"category": "prompt_injection", "usd": 0.30, "input_tokens": 100, "output_tokens": 200})
    s.insert_cost({"category": "data_exfiltration", "usd": 0.20, "input_tokens": 60, "output_tokens": 40})
    return s


def _obs(cases=CASES):
    return Observability(_seed(), cases=cases)


# --------------------------------------------------------------------------- #
def test_imports():
    from forge.observability import Observability  # noqa: F401


# 1. coverage --------------------------------------------------------------- #
def test_coverage_per_category_and_per_owasp():
    cov = _obs().coverage()
    assert cov["by_category"] == {"prompt_injection": 4, "data_exfiltration": 3}
    # per-OWASP coverage: attempts in every category mapped to that OWASP id
    assert cov["by_owasp"]["LLM01:Prompt Injection"] == 4
    assert cov["by_owasp"]["A01:2021-Broken Access Control"] == 3
    assert cov["by_owasp"]["LLM06:Sensitive Information Disclosure"] == 3


def test_coverage_owasp_requires_cases():
    cov = Observability(_seed()).coverage()  # no cases -> cannot map to OWASP
    assert cov["by_category"] == {"prompt_injection": 4, "data_exfiltration": 3}
    assert cov["by_owasp"] == {}


# 2. pass / fail ------------------------------------------------------------ #
def test_pass_fail_per_category_and_version():
    pf = _obs().pass_fail()

    pi = pf["by_category"]["prompt_injection"]
    assert (pi["attempts"], pi["exploits"], pi["defended"], pi["partial"]) == (4, 1, 3, 0)
    assert pi["pass_rate"] == pytest.approx(0.75)

    de = pf["by_category"]["data_exfiltration"]
    assert (de["attempts"], de["exploits"], de["defended"]) == (3, 0, 3)
    assert de["pass_rate"] == pytest.approx(1.0)

    assert pf["overall"]["attempts"] == 7
    assert pf["overall"]["exploits"] == 1
    assert pf["overall"]["defended"] == 6

    assert pf["by_version"]["v1"]["attempts"] == 4
    assert pf["by_version"]["v1"]["pass_rate"] == pytest.approx(0.75)
    assert pf["by_version"]["v2"]["attempts"] == 3
    assert pf["by_version"]["v2"]["pass_rate"] == pytest.approx(1.0)


# 3. resilience trend ------------------------------------------------------- #
def test_resilience_trend_ordered_over_versions():
    tr = _obs().resilience_trend()
    assert [t["version"] for t in tr] == ["v1", "v2"]
    assert tr[0]["pass_rate"] == pytest.approx(0.75)
    assert tr[1]["pass_rate"] == pytest.approx(1.0)
    assert tr[1]["pass_rate"] > tr[0]["pass_rate"]  # resilience improved


# 4. finding lifecycle ------------------------------------------------------ #
def test_finding_lifecycle_buckets():
    lc = _obs().finding_lifecycle()
    assert lc["open"] == 1
    assert lc["in_progress"] == 1
    assert lc["resolved"] == 1


# 5. cost + scaling --------------------------------------------------------- #
def test_cost_totals_and_scaling_rate():
    c = _obs().cost()
    assert c["total_usd"] == pytest.approx(0.50)
    assert c["total_input_tokens"] == 160
    assert c["total_output_tokens"] == 240
    assert c["by_category"]["prompt_injection"] == pytest.approx(0.30)
    assert c["by_category"]["data_exfiltration"] == pytest.approx(0.20)
    # scaling rate = cost per attempt (7 verdicts)
    assert c["usd_per_attempt"] == pytest.approx(0.50 / 7)


# 6. agent activity --------------------------------------------------------- #
def test_agent_activity_ordered_and_labeled():
    act = _obs().agent_activity()
    seqs = [a["seq"] for a in act]
    assert seqs == sorted(seqs)  # ordered

    agents = {a["agent"] for a in act}
    assert {"orchestrator", "red_team", "judge"} <= agents

    assert act[0]["agent"] == "orchestrator" and act[0]["kind"] == "run_start"
    # the red_team attack on attempt 1 precedes the judge verdict on attempt 1
    attack_seq = next(a["seq"] for a in act if a["kind"] == "attack")
    verdict_seq = next(a["seq"] for a in act if a["kind"] == "verdict")
    assert attack_seq < verdict_seq


# combined snapshot --------------------------------------------------------- #
def test_snapshot_combines_all_views():
    snap = _obs().snapshot()
    assert {"coverage", "pass_fail", "resilience_trend", "finding_lifecycle", "cost", "agent_activity"} <= set(snap)
    assert snap["coverage"]["by_category"]["prompt_injection"] == 4
    assert snap["cost"]["total_usd"] == pytest.approx(0.50)
