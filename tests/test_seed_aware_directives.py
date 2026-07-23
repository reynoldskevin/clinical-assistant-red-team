"""Ticket 054 — seed-aware autonomous directives.

The Orchestrator cycles a category's eval-case prompts as directive seeds so the
catalog actually drives the deployed (`run_autonomous`) Red Team, and floors each
seeded category at enough attempts to exercise every seed.
"""

from types import SimpleNamespace

from forge.observability import Observability
from forge.orchestrator import Orchestrator
from forge.run import CostMeter, build_autonomous_runner, seeds_for_category
from forge.store import Store


def _obs(store):
    return Observability(store)


def _seed_verdicts(store, category, n, verdict="fail"):
    for _ in range(n):
        store.append_event({"kind": "verdict", "category": category, "verdict": verdict,
                            "confidence": 0.9, "target_version": "v1"})


# --------------------------------------------------------------------------- #
# seed cycling
# --------------------------------------------------------------------------- #
def test_directive_cycles_category_seeds():
    store = Store(":memory:")
    _seed_verdicts(store, "prompt_injection", 1)  # stays below the floor
    orch = Orchestrator(_obs(store), categories=["prompt_injection"], coverage_target=10,
                        seeds_by_category={"prompt_injection": ["s1", "s2"]})
    seeds = [orch.next_directive().seed for _ in range(4)]
    assert seeds == ["s1", "s2", "s1", "s2"]


def test_unseeded_category_yields_none_seed():
    store = Store(":memory:")
    _seed_verdicts(store, "tool_misuse", 1)
    orch = Orchestrator(_obs(store), categories=["tool_misuse"], coverage_target=10,
                        seeds_by_category={"prompt_injection": ["s1"]})  # none for tool_misuse
    assert orch.next_directive().seed is None


def test_default_no_seed_map_is_backcompat():
    store = Store(":memory:")
    _seed_verdicts(store, "tool_misuse", 1)
    orch = Orchestrator(_obs(store), categories=["tool_misuse"], coverage_target=10)
    assert orch.next_directive().seed is None


# --------------------------------------------------------------------------- #
# seeded floor exercises every seed
# --------------------------------------------------------------------------- #
def test_seeded_floor_probes_until_all_seeds_run_then_halts():
    store = Store(":memory:")
    orch = Orchestrator(_obs(store), categories=["tool_misuse"], coverage_target=3,
                        pass_rate_target=1.0,
                        seeds_by_category={"tool_misuse": ["a", "b", "c", "d", "e"]})
    seen = []
    for _ in range(5):
        d = orch.next_directive()
        assert d is not None
        seen.append(d.seed)
        _seed_verdicts(store, "tool_misuse", 1)  # simulate the attempt landing (defended)
    # all five seeds exercised even though coverage_target is only 3
    assert set(seen) == {"a", "b", "c", "d", "e"}
    # floor met (5 attempts) + all defended → the loop halts
    assert orch.next_directive() is None


def test_unseeded_floor_is_plain_coverage_target():
    store = Store(":memory:")
    _seed_verdicts(store, "tool_misuse", 3, verdict="fail")
    orch = Orchestrator(_obs(store), categories=["tool_misuse"], coverage_target=3,
                        pass_rate_target=1.0)
    # 3 attempts == coverage_target and all defended → covered → halts (no seeded bump)
    assert orch.next_directive() is None


# --------------------------------------------------------------------------- #
# wiring + defensiveness
# --------------------------------------------------------------------------- #
class _RT:
    def run(self, directive, pid):
        return []


class _Judge:
    def evaluate(self, attempt, **kw):  # pragma: no cover - not called here
        raise AssertionError("not exercised")


class _Adapter:
    def ask(self, pid, prompt):  # pragma: no cover - not called here
        raise AssertionError("not exercised")


def test_build_autonomous_runner_wires_case_prompts_as_seeds():
    store = Store(":memory:")
    cases = [
        SimpleNamespace(category="prompt_injection", prompt="pi-seed-1",
                        input_sequence=None, owasp_web=[], owasp_llm=["LLM01:Prompt Injection"]),
        SimpleNamespace(category="tool_misuse", prompt="tm-seed-1",
                        input_sequence=None, owasp_web=["A10:2021-Server-Side Request Forgery (SSRF)"],
                        owasp_llm=[]),
    ]
    runner = build_autonomous_runner(
        store, red_team=_RT(), judge=_Judge(), adapter=_Adapter(),
        cases=cases, cost_meter=CostMeter(), pid=1)
    # empty store → prompt_injection (alpha-least) probed first, carrying its seed
    d = runner._orchestrator.next_directive()
    assert d.category == "prompt_injection"
    assert d.seed == "pi-seed-1"


def test_seeds_for_category_tolerates_prompt_less_cases():
    # a case object with neither prompt nor input_sequence must not raise
    cases = [SimpleNamespace(category="tool_misuse")]
    assert seeds_for_category(cases, "tool_misuse") == []
