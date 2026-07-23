"""Ticket 046 — scope the Orchestrator to the current run.

The Orchestrator assesses coverage against the store it reads. When that store is
the cumulative event log, a run after history exists sees every category already
covered and halts immediately — the empty-run bug. `run_autonomous` must scope the
Orchestrator to the CURRENT run so each run re-covers all six categories from zero.

Verdict semantics: "success" = EXPLOITED, "fail" = DEFENDED.
"""

from types import SimpleNamespace

from forge.observability import Observability
from forge.orchestrator import Orchestrator
from forge.run import CostMeter, Runner
from forge.scoping import RunScopedStore, current_run
from forge.schemas import AttackAttempt, Verdict
from forge.store import Store


SIX = [
    "data_exfiltration",
    "denial_of_service",
    "identity_exploitation",
    "prompt_injection",
    "state_corruption",
    "tool_misuse",
]


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
class _FakeRT:
    def run(self, directive, pid):
        return [AttackAttempt(category=directive.category, prompt="attack",
                              transcript=[{"role": "attacker", "content": "x"}])]


class _DefendJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="fail", confidence=0.9, rationale="defended",
                       owasp_web=[], owasp_llm=[])


def _seed_full_prior_run(store, *, version="v1.1", per_cat=12):
    """A completed prior run that covers every category well past the floor."""
    rid = store.append_event({"kind": "run_start", "version": version, "ts": 1})
    for cat in SIX:
        for _ in range(per_cat):
            store.append_event({"kind": "verdict", "category": cat, "verdict": "fail",
                                "confidence": 0.9, "target_version": version, "run_id": rid})
    store.append_event({"kind": "run_end", "version": version, "ts": 2, "run_id": rid})
    return rid


def _verdicts_by_cat_for_version(store, version):
    counts = {}
    for e in store.get_events():
        if e.get("kind") == "verdict" and e.get("target_version") == version:
            counts[e["category"]] = counts.get(e["category"], 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# RunScopedStore
# --------------------------------------------------------------------------- #
def test_run_scoped_store_windows_events_and_scopes_rows():
    s = Store(":memory:")
    s.append_event({"kind": "verdict", "category": "pi", "verdict": "fail", "confidence": 0.9})  # id 1 (before)
    start = s.append_event({"kind": "run_start", "version": "v1.1"})                              # id 2
    s.append_event({"kind": "verdict", "category": "pi", "verdict": "fail", "confidence": 0.9})   # id 3 (in)
    s.insert_finding({"severity": "high", "attack_category": "pi", "status": "open", "run_id": start})
    s.insert_finding({"severity": "low", "attack_category": "pi", "status": "open", "run_id": 999})  # other run
    s.insert_cost({"category": "pi", "usd": 0.5, "run_id": start})
    s.insert_cost({"category": "pi", "usd": 9.9, "run_id": 999})  # other run

    scoped = RunScopedStore(s, start_id=start, end_id=None)
    # events limited to the window [start, ∞)
    ids = [e["id"] for e in scoped.get_events()]
    assert start in ids and 1 not in ids
    # findings/costs scoped by run_id == start
    assert [f["run_id"] for f in scoped.list_findings()] == [start]
    assert [c["run_id"] for c in scoped.get_costs()] == [start]
    # a passed filter is honored ALONGSIDE the run_id scope
    assert all(f.get("status") == "open" and f["run_id"] == start
               for f in scoped.list_findings(status="open"))


def test_current_run_reports_latest_window():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.0"})
    s.append_event({"kind": "run_end"})
    start = s.append_event({"kind": "run_start", "version": "v1.1"})
    got = current_run(s.get_events())
    assert got is not None
    start_id, end_id, version = got
    assert start_id == start and end_id is None and version == "v1.1"


# --------------------------------------------------------------------------- #
# the fix: orchestrator over a run-scoped store ignores prior coverage
# --------------------------------------------------------------------------- #
def test_orchestrator_over_run_scope_ignores_prior_run_coverage():
    s = Store(":memory:")
    _seed_full_prior_run(s)                       # every category covered cumulatively
    start = s.append_event({"kind": "run_start", "version": "v1.2"})   # a fresh run begins

    # cumulative view → halts (the bug)
    assert Orchestrator(Observability(s), categories=SIX, coverage_target=10).next_directive() is None

    # run-scoped view → the new run has zero coverage → it drives a directive
    scoped = Observability(RunScopedStore(s, start_id=start, end_id=None))
    assert Orchestrator(scoped, categories=SIX, coverage_target=10).next_directive() is not None


def test_run_autonomous_covers_categories_despite_prior_run():
    s = Store(":memory:")
    _seed_full_prior_run(s)   # a complete prior run already over the floor everywhere
    orch = Orchestrator(Observability(s), categories=SIX, coverage_target=10, run_budget_usd=1e9)
    Runner(s, _FakeRT(), _DefendJudge(), pid=1, cost_meter=CostMeter(),
           orchestrator=orch).run_autonomous()

    # the new run is v1.2 and must itself cover all six ≥10 (not inherit prior coverage)
    new_counts = _verdicts_by_cat_for_version(s, "v1.2")
    for cat in SIX:
        assert new_counts.get(cat, 0) >= 10, f"{cat} not covered in the new run: {new_counts.get(cat, 0)}"
