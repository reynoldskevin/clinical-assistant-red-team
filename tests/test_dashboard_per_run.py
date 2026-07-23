"""Per-run stat scoping + versioned resilience trend.

Dashboard stats reset each run (everything shown is for the latest run only);
the resilience trend is the one cross-run view, one point per versioned run.
`run.py` stamps each run with a mock version (v1.0, v1.1, …) and a run_id.
"""

from forge.dashboard import build_state
from forge.observability import Observability
from forge.run import CostMeter, Runner
from forge.schemas import AttackAttempt, Verdict
from forge.store import Store


# --------------------------------------------------------------------------- #
# scoping helpers
# --------------------------------------------------------------------------- #
def _run(store, version, ts, verdicts, costs, *, end=True):
    """Append a run (run_start, verdicts, cost rows, optional run_end)."""
    rid = store.append_event({"kind": "run_start", "version": version, "ts": ts})
    for i, (cat, v) in enumerate(verdicts):
        store.append_event({
            "kind": "verdict", "attempt_id": rid * 100 + i, "category": cat,
            "verdict": v, "confidence": 0.9, "target_version": version, "run_id": rid,
        })
    for cat, usd in costs:
        store.insert_cost({"category": cat, "usd": usd, "input_tokens": 10,
                           "output_tokens": 5, "run_id": rid})
    if end:
        store.append_event({"kind": "run_end", "version": version, "ts": ts + 10, "run_id": rid})
    return rid


def test_new_run_scopes_stats_to_itself():
    s = Store(":memory:")
    _run(s, "v1.0", 100, [("pi", "fail"), ("pi", "success")], [("pi", 0.5)], end=True)
    _run(s, "v1.1", 200, [("pi", "fail")], [("pi", 0.1)], end=False)  # active
    state = build_state(Observability(s))
    # only the active run counts — not the 3-verdict cumulative total
    assert state["kpis"]["attempts"] == 1
    assert state["kpis"]["exploits"] == 0            # run 1's exploit is excluded
    assert state["kpis"]["total_usd"] == 0.1         # run 2's cost only
    assert state["outcomes"] == {"exploited": 0, "partial": 0, "defended": 1}
    assert state["run_active"] is True


def test_fresh_run_resets_to_zero():
    s = Store(":memory:")
    _run(s, "v1.0", 100, [("pi", "fail"), ("pi", "success")], [("pi", 0.5)], end=True)
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 200})  # just started, no verdicts
    state = build_state(Observability(s))
    assert state["kpis"]["attempts"] == 0
    assert state["kpis"]["exploits"] == 0
    assert state["kpis"]["total_usd"] == 0.0
    assert state["outcomes"] == {"exploited": 0, "partial": 0, "defended": 0}


def test_resilience_trend_spans_runs():
    s = Store(":memory:")
    _run(s, "v1.0", 100, [("pi", "fail"), ("pi", "success")], [("pi", 0.5)], end=True)  # 0.5
    _run(s, "v1.1", 200, [("pi", "fail")], [("pi", 0.1)], end=False)                     # 1.0
    trend = build_state(Observability(s))["resilience_trend"]
    assert [p["version"] for p in trend] == ["v1.0", "v1.1"]
    by_ver = {p["version"]: p["pass_rate"] for p in trend}
    assert by_ver["v1.0"] == 0.5
    assert by_ver["v1.1"] == 1.0


def test_trend_versions_sort_numerically():
    s = Store(":memory:")
    _run(s, "v1.2", 100, [("pi", "fail")], [], end=True)
    _run(s, "v1.10", 200, [("pi", "fail")], [], end=True)
    versions = [p["version"] for p in build_state(Observability(s))["resilience_trend"]]
    assert versions == ["v1.2", "v1.10"]   # numeric, not lexical ("v1.10" last)


def test_no_run_markers_falls_back_to_all():
    s = Store(":memory:")
    s.append_event({"kind": "verdict", "attempt_id": 1, "category": "pi",
                    "verdict": "fail", "confidence": 0.9})
    state = build_state(Observability(s))
    assert state["kpis"]["attempts"] == 1  # nothing to scope to → shown


# --------------------------------------------------------------------------- #
# run.py versioning + stamping
# --------------------------------------------------------------------------- #
class _FakeRT:
    def run(self, directive, pid):
        return [AttackAttempt(category=directive.category, prompt="attack")]


class _FakeJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="fail", confidence=0.9, rationale="r",
                       owasp_web=[], owasp_llm=["LLM01:Prompt Injection"])


def test_run_suite_stamps_version_and_run_id():
    s = Store(":memory:")
    runner = Runner(s, _FakeRT(), _FakeJudge(), pid=1, cost_meter=CostMeter())
    runner.run_suite({"prompt_injection": ["seed"]})

    starts = [e for e in s.get_events() if e["kind"] == "run_start"]
    assert len(starts) == 1
    assert starts[0]["version"] == "v1.0"
    rid = starts[0]["id"]

    verds = [e for e in s.get_events() if e["kind"] == "verdict"]
    assert verds and all(v["target_version"] == "v1.0" and v["run_id"] == rid for v in verds)
    costs = s.get_costs()
    assert costs and all(c["run_id"] == rid for c in costs)


def test_second_run_increments_minor_version():
    s = Store(":memory:")
    runner = Runner(s, _FakeRT(), _FakeJudge(), pid=1, cost_meter=CostMeter())
    runner.run_suite({"prompt_injection": ["seed"]})
    runner.run_suite({"prompt_injection": ["seed"]})
    versions = [e["version"] for e in s.get_events() if e["kind"] == "run_start"]
    assert versions == ["v1.0", "v1.1"]
