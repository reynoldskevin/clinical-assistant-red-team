"""Ticket 044 — one full-agent deployed loop.

`forge run` now drives `Runner.run_autonomous()`: the **Orchestrator** selects
directives (`next_directive()` until it halts), **Red Team** → **Judge** run per
directive, the **Regression** harness replays known cases, and the
**Documentation** agent drafts reports — all in ONE path, with the same run
bookkeeping (versioned `run_start`/`run_end`, `run_id`/`target_version` stamping)
the dashboard depends on. `AutonomousLoop` is retired.

Verdict semantics: "success" = EXPLOITED, "fail" = DEFENDED.
"""

import importlib
import pathlib
import tempfile
from types import SimpleNamespace

import pytest

from forge.documentation import DocumentationAgent
from forge.observability import Observability
from forge.orchestrator import Orchestrator
from forge.regression import RegressionHarness
from forge.run import CostMeter, Runner
from forge.schemas import AttackAttempt, AttackDirective, Verdict
from forge.store import Store


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
def _directive(category="prompt_injection"):
    return AttackDirective(category=category, max_attempts=1)


class _FakeOrch:
    """Yields the given directives in order, then halts (None)."""

    def __init__(self, directives):
        self._d = list(directives)
        self.calls = 0

    def next_directive(self):
        self.calls += 1
        return self._d.pop(0) if self._d else None


class _FakeRT:
    def run(self, directive, pid):
        return [
            AttackAttempt(
                category=directive.category,
                prompt="attack",
                transcript=[
                    {"role": "attacker", "content": "do the bad thing"},
                    {"role": "target", "answer": "ok"},
                ],
            )
        ]


class _ExploitJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="success", confidence=0.9, rationale="pwned",
                       owasp_web=[], owasp_llm=["LLM01:Prompt Injection"])


class _DefendJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="fail", confidence=0.9, rationale="held the line",
                       owasp_web=[], owasp_llm=["LLM01:Prompt Injection"])


class _Resp:
    answer = "an answer"
    correlation_id = "cid"
    status = 200
    body = {"answer": "an answer"}


class _FakeAdapter:
    def ask(self, pid, prompt):
        return _Resp()


class _BoomDoc:
    _reports_dir = tempfile.gettempdir()

    def is_duplicate(self, attempt):
        raise RuntimeError("documentation down")


def _tmp_doc(store):
    return DocumentationAgent(store, reports_dir=tempfile.mkdtemp())


# --------------------------------------------------------------------------- #
# orchestrator-driven attack phase
# --------------------------------------------------------------------------- #
def test_run_autonomous_loops_until_orchestrator_halts():
    s = Store(":memory:")
    orch = _FakeOrch([_directive(), _directive(), _directive()])
    r = Runner(s, _FakeRT(), _DefendJudge(), pid=1, cost_meter=CostMeter(), orchestrator=orch)
    r.run_autonomous()

    assert orch.calls == 4  # 3 directives + the terminating None
    verds = [e for e in s.get_events() if e["kind"] == "verdict"]
    assert len(verds) == 3  # one Red Team → Judge cycle per directive


def test_run_autonomous_versions_and_stamps():
    s = Store(":memory:")
    Runner(s, _FakeRT(), _DefendJudge(), pid=1, cost_meter=CostMeter(),
           orchestrator=_FakeOrch([_directive()])).run_autonomous()

    starts = [e for e in s.get_events() if e["kind"] == "run_start"]
    assert starts and starts[0]["version"] == "v1.1"   # first NEW run (v1.0 = baseline)
    rid = starts[0]["id"]

    verds = [e for e in s.get_events() if e["kind"] == "verdict"]
    assert verds and all(v["run_id"] == rid and v["target_version"] == "v1.1" for v in verds)
    costs = s.get_costs()
    assert costs and all(c["run_id"] == rid for c in costs)

    # a second run increments the minor version
    Runner(s, _FakeRT(), _DefendJudge(), pid=1, cost_meter=CostMeter(),
           orchestrator=_FakeOrch([_directive()])).run_autonomous()
    versions = [e["version"] for e in s.get_events() if e["kind"] == "run_start"]
    assert versions == ["v1.1", "v1.2"]


# --------------------------------------------------------------------------- #
# regression replay + documentation, in order, within the run window
# --------------------------------------------------------------------------- #
def test_regression_replay_runs_before_documentation_and_within_window():
    s = Store(":memory:")
    judge = _ExploitJudge()
    harness = RegressionHarness(s, _FakeAdapter(), judge, pid=1)
    # a pre-existing known case (created before the run) so validate() has something to replay
    harness.create_case(
        Verdict(verdict="success", confidence=0.9, rationale="r", owasp_web=[], owasp_llm=[]),
        AttackAttempt(category="denial_of_service", prompt="loop",
                      transcript=[{"role": "attacker", "content": "loop forever"}]),
    )
    r = Runner(s, _FakeRT(), judge, pid=1, cost_meter=CostMeter(),
               orchestrator=_FakeOrch([_directive()]),
               documentation=_tmp_doc(s), regression_harness=harness)
    r.run_autonomous()

    events = s.get_events()
    start = next(e["id"] for e in events if e["kind"] == "run_start")
    end = next(e["id"] for e in events if e["kind"] == "run_end")
    rr = [e["id"] for e in events if e["kind"] == "regression_result"]
    vl = [e["id"] for e in events if e["kind"] == "vuln_report_link"]

    assert rr, "regression replay must have produced a regression_result"
    assert vl, "documentation pass must have linked a report to a case"
    assert all(start < i < end for i in rr + vl)  # everything inside the run window
    assert max(rr) < min(vl)                       # validate() BEFORE the documentation pass


def test_documentation_pass_writes_report_and_creates_case():
    s = Store(":memory:")
    judge = _ExploitJudge()
    harness = RegressionHarness(s, _FakeAdapter(), judge, pid=1)
    reports_dir = tempfile.mkdtemp()
    doc = DocumentationAgent(s, reports_dir=reports_dir)

    Runner(s, _FakeRT(), judge, pid=1, cost_meter=CostMeter(),
           orchestrator=_FakeOrch([_directive()]),
           documentation=doc, regression_harness=harness).run_autonomous()

    files = list(pathlib.Path(reports_dir).glob("*.json"))
    assert len(files) == 1  # Documentation agent drafted a report file
    assert [e for e in s.get_events() if e["kind"] == "vuln_report_link"]
    # create_case registered the newly-found exploit as a future regression case
    assert [e for e in s.get_events() if e["kind"] == "regression_case"]


def test_documentation_or_harness_failure_is_isolated():
    s = Store(":memory:")
    judge = _ExploitJudge()
    harness = RegressionHarness(s, _FakeAdapter(), judge, pid=1)
    r = Runner(s, _FakeRT(), judge, pid=1, cost_meter=CostMeter(),
               orchestrator=_FakeOrch([_directive()]),
               documentation=_BoomDoc(), regression_harness=harness)
    r.run_autonomous()  # must not raise

    kinds = [e["kind"] for e in s.get_events()]
    assert "run_start" in kinds and "run_end" in kinds
    assert "verdict" in kinds  # the attack phase still completed


# --------------------------------------------------------------------------- #
# the REAL Orchestrator drives + halts (strategist genuinely wired)
# --------------------------------------------------------------------------- #
def test_real_orchestrator_drives_and_halts_on_coverage():
    s = Store(":memory:")
    cases = [SimpleNamespace(category="prompt_injection", owasp_web=[],
                             owasp_llm=["LLM01:Prompt Injection"])]
    obs = Observability(s, cases=cases)
    orch = Orchestrator(obs, categories=["prompt_injection"],
                        coverage_target=2, pass_rate_target=0.0, run_budget_usd=100.0)
    r = Runner(s, _FakeRT(), _DefendJudge(), pid=1, cost_meter=CostMeter(), orchestrator=orch)
    r.run_autonomous()

    verds = [e for e in s.get_events() if e["kind"] == "verdict"]
    assert len(verds) >= 2                       # drove until the coverage target was met
    assert any(e["kind"] == "run_end" for e in s.get_events())  # halted cleanly (not infinite)


# --------------------------------------------------------------------------- #
# deployed wiring: the four-agent factory
# --------------------------------------------------------------------------- #
def test_build_autonomous_runner_wires_all_four_agents():
    from forge.run import build_autonomous_runner

    s = Store(":memory:")
    cases = [SimpleNamespace(category="prompt_injection", owasp_web=[], owasp_llm=[])]
    r = build_autonomous_runner(
        s, red_team=_FakeRT(), judge=_DefendJudge(), adapter=_FakeAdapter(),
        cases=cases, cost_meter=CostMeter(), pid=1,
    )
    assert isinstance(r._orchestrator, Orchestrator)     # Orchestrator wired
    assert isinstance(r._documentation, DocumentationAgent)  # Documentation wired
    assert isinstance(r._regression_harness, RegressionHarness)  # Regression wired
    assert r._red_team is not None and r._judge is not None      # Red Team + Judge wired


# --------------------------------------------------------------------------- #
# AutonomousLoop retired
# --------------------------------------------------------------------------- #
def test_autonomous_loop_module_is_retired():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("forge.loop")
