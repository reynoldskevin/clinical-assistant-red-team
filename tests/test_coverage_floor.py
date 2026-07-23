"""Ticket 045 — the six-category coverage floor (≥10 attempts each).

The platform must probe every attack category a minimum of `coverage_target`
(10) times per run. The orchestrator-driven run must therefore reach that floor
for all six categories BEFORE re-probing an open finding can monopolize the loop.

Verdict semantics: "success" = EXPLOITED, "fail" = DEFENDED.
"""

from types import SimpleNamespace

from forge.observability import Observability
from forge.orchestrator import Orchestrator
from forge.regression import RegressionHarness  # noqa: F401 (documents wiring under test)
from forge.run import CostMeter, Runner, build_autonomous_runner
from forge.schemas import AttackAttempt, AttackDirective, Verdict
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
class _FakeOrch:
    def __init__(self, directives):
        self._d = list(directives)

    def next_directive(self):
        return self._d.pop(0) if self._d else None


class _FakeRT:
    def run(self, directive, pid):
        return [AttackAttempt(category=directive.category, prompt="attack",
                              transcript=[{"role": "attacker", "content": "x"}])]


class _DefendJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="fail", confidence=0.9, rationale="defended",
                       owasp_web=[], owasp_llm=[])


class _ExploitOnceJudge:
    """Confirms an exploit on the very first attempt, defends thereafter."""

    def __init__(self):
        self._first = True

    def evaluate(self, attempt, **kw):
        if self._first:
            self._first = False
            return Verdict(verdict="success", confidence=0.9, rationale="pwned",
                           owasp_web=[], owasp_llm=[])
        return Verdict(verdict="fail", confidence=0.9, rationale="defended",
                       owasp_web=[], owasp_llm=[])


class _FakeAdapter:
    def ask(self, pid, prompt):
        return SimpleNamespace(answer="a", correlation_id="c", status=200, body={})


def _obs(store):
    return Observability(store)


def _seed_verdicts(store, category, n, verdict="fail"):
    for _ in range(n):
        store.append_event({"kind": "verdict", "category": category, "verdict": verdict,
                            "confidence": 0.9, "target_version": "v1"})


def _attempts_by_category(store):
    counts = {}
    for e in store.get_events():
        if e.get("kind") == "verdict":
            counts[e["category"]] = counts.get(e["category"], 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# (1) Orchestrator: coverage floor outranks high-severity re-probe
# --------------------------------------------------------------------------- #
def test_coverage_floor_beats_high_severity_reprobe():
    store = Store(":memory:")
    # tool_misuse is fully covered AND has an open high-severity finding …
    _seed_verdicts(store, "tool_misuse", 10)
    store.insert_finding({"severity": "high", "attack_category": "tool_misuse", "status": "open"})
    # … but prompt_injection is still below the floor (only 2 attempts).
    _seed_verdicts(store, "prompt_injection", 2)
    orch = Orchestrator(_obs(store), categories=["prompt_injection", "tool_misuse"],
                        coverage_target=10, pass_rate_target=1.0, run_budget_usd=100.0)
    d = orch.next_directive()
    assert d is not None
    assert d.category == "prompt_injection", (
        "a below-floor category must be probed before re-probing an open finding"
    )


def test_high_severity_reprobe_still_wins_once_all_at_floor():
    # Existing behavior preserved: with everyone at the floor, the open finding is re-probed.
    store = Store(":memory:")
    for c in ("prompt_injection", "tool_misuse"):
        _seed_verdicts(store, c, 10)
    store.insert_finding({"severity": "high", "attack_category": "tool_misuse", "status": "open"})
    orch = Orchestrator(_obs(store), categories=["prompt_injection", "tool_misuse"],
                        coverage_target=10, pass_rate_target=1.0, run_budget_usd=100.0)
    assert orch.next_directive().category == "tool_misuse"


# --------------------------------------------------------------------------- #
# (2) run_autonomous covers all six to the floor
# --------------------------------------------------------------------------- #
def test_autonomous_run_covers_all_six_to_the_floor():
    store = Store(":memory:")
    obs = Observability(store)
    orch = Orchestrator(obs, categories=SIX, coverage_target=10, run_budget_usd=1e9)
    Runner(store, _FakeRT(), _DefendJudge(), pid=1, cost_meter=CostMeter(),
           orchestrator=orch).run_autonomous()

    counts = _attempts_by_category(store)
    for cat in SIX:
        assert counts.get(cat, 0) >= 10, f"{cat} under the floor: {counts.get(cat, 0)}"
    assert any(e["kind"] == "run_end" for e in store.get_events())  # halted cleanly


def test_early_exploit_does_not_starve_the_other_categories():
    store = Store(":memory:")
    obs = Observability(store)
    orch = Orchestrator(obs, categories=SIX, coverage_target=10, run_budget_usd=1e9)
    # first attempt is a confirmed exploit → an open high-severity finding early on
    Runner(store, _FakeRT(), _ExploitOnceJudge(), pid=1, cost_meter=CostMeter(),
           orchestrator=orch).run_autonomous(max_directives=200)

    counts = _attempts_by_category(store)
    for cat in SIX:
        assert counts.get(cat, 0) >= 10, (
            f"{cat} starved by the early exploit's re-probe: {counts.get(cat, 0)}"
        )


# --------------------------------------------------------------------------- #
# (3) deployed factory pins the platform minimum
# --------------------------------------------------------------------------- #
def test_build_autonomous_runner_pins_coverage_target_to_ten():
    store = Store(":memory:")
    cases = [SimpleNamespace(category=c, owasp_web=[], owasp_llm=[]) for c in SIX]
    r = build_autonomous_runner(store, red_team=_FakeRT(), judge=_DefendJudge(),
                                adapter=_FakeAdapter(), cases=cases, cost_meter=CostMeter(), pid=1)
    assert r._orchestrator.coverage_target == 10
    assert set(r._orchestrator.categories) == set(SIX)
