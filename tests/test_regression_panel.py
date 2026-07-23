"""Ticket 043 — regression replay wired into the run + "Known vulnerabilities" panel.

The regression harness re-runs Judge-confirmed exploits to check whether they are
STILL vulnerable. This ticket wires that into the deployed run (`run_suite` calls
`validate()` before `run_end`, so its `regression_result` events land inside the
run's event-id window and scope to the run), surfaces a per-run
`known_vulnerabilities` view from `build_state`, and renders a dashboard panel.

Verdict semantics (inherited): a regression case is `fixed` when the replay is now
DEFENDED (verdict "fail"), `vulnerable` when the exploit still works.
"""

import json

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.run import CostMeter, Runner
from forge.schemas import AttackAttempt, Verdict
from forge.store import Store


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
class _FakeRT:
    def run(self, directive, pid):
        return [AttackAttempt(category=directive.category, prompt="attack")]


class _FakeJudge:
    def evaluate(self, attempt, **kw):
        return Verdict(verdict="fail", confidence=0.9, rationale="r",
                       owasp_web=[], owasp_llm=["LLM01:Prompt Injection"])


class _RecordingHarness:
    """Stand-in harness: on validate() writes N regression_result events."""

    def __init__(self, store, results):
        self._store = store
        self._results = results
        self.validate_calls = 0

    def validate(self, changed_category=None):
        self.validate_calls += 1
        for r in self._results:
            self._store.append_event({"kind": "regression_result", **r})
        return []


class _BoomHarness:
    def __init__(self):
        self.validate_calls = 0

    def validate(self, changed_category=None):
        self.validate_calls += 1
        raise RuntimeError("target unreachable")


def _result(case_id, category, status, *, verdict=None, reappeared=False):
    return {
        "case_id": case_id,
        "category": category,
        "status": status,
        "verdict": verdict if verdict is not None else ("fail" if status == "fixed" else "success"),
        "passed": status == "fixed",
        "reappeared": reappeared,
        "cross_category": False,
    }


# --------------------------------------------------------------------------- #
# run wiring
# --------------------------------------------------------------------------- #
def test_run_suite_invokes_harness_within_the_run_window():
    s = Store(":memory:")
    harness = _RecordingHarness(
        s,
        [_result("aaa", "denial_of_service", "vulnerable"),
         _result("bbb", "prompt_injection", "fixed")],
    )
    runner = Runner(s, _FakeRT(), _FakeJudge(), pid=1,
                    cost_meter=CostMeter(), regression_harness=harness)
    runner.run_suite({"prompt_injection": ["seed"]})

    assert harness.validate_calls == 1

    events = s.get_events()
    start = next(e["id"] for e in events if e["kind"] == "run_start")
    end = next(e["id"] for e in events if e["kind"] == "run_end")
    reg = [e for e in events if e["kind"] == "regression_result"]
    assert len(reg) == 2
    # every regression_result must land strictly inside [run_start, run_end]
    assert all(start < e["id"] < end for e in reg)


def test_harness_failure_does_not_abort_the_run():
    s = Store(":memory:")
    harness = _BoomHarness()
    runner = Runner(s, _FakeRT(), _FakeJudge(), pid=1,
                    cost_meter=CostMeter(), regression_harness=harness)
    # must not raise, and the run must still close cleanly
    runner.run_suite({"prompt_injection": ["seed"]})

    assert harness.validate_calls == 1
    kinds = [e["kind"] for e in s.get_events()]
    assert "run_start" in kinds and "run_end" in kinds
    # the verdict from the normal suite loop still landed
    assert "verdict" in kinds


def test_runner_without_harness_is_unchanged():
    s = Store(":memory:")
    runner = Runner(s, _FakeRT(), _FakeJudge(), pid=1, cost_meter=CostMeter())
    runner.run_suite({"prompt_injection": ["seed"]})
    assert not [e for e in s.get_events() if e["kind"] == "regression_result"]


# --------------------------------------------------------------------------- #
# build_state — known_vulnerabilities view
# --------------------------------------------------------------------------- #
def _seed_run_with_regressions(store, results, *, version="v1.1", end=True):
    rid = store.append_event({"kind": "run_start", "version": version, "ts": 100})
    store.append_event({"kind": "verdict", "attempt_id": rid * 10, "category": "pi",
                        "verdict": "fail", "confidence": 0.9, "run_id": rid,
                        "target_version": version})
    for r in results:
        store.append_event({"kind": "regression_result", **r})
    if end:
        store.append_event({"kind": "run_end", "version": version, "ts": 200, "run_id": rid})
    return rid


def test_build_state_exposes_known_vulnerabilities():
    s = Store(":memory:")
    _seed_run_with_regressions(s, [
        _result("aaa", "denial_of_service", "vulnerable"),
        _result("bbb", "prompt_injection", "fixed"),
        _result("ccc", "data_exfiltration", "fixed"),
    ])
    state = build_state(Observability(s))
    kv = state["known_vulnerabilities"]

    assert kv["total"] == 3
    assert kv["vulnerable"] == 1
    assert kv["fixed"] == 2
    assert len(kv["cases"]) == 3
    # vulnerable case is listed first
    assert kv["cases"][0]["status"] == "vulnerable"
    assert kv["cases"][0]["case_id"] == "aaa"
    assert kv["cases"][0]["category"] == "denial_of_service"
    # JSON-serializable
    assert json.loads(json.dumps(kv)) == kv


def test_known_vulnerabilities_scoped_to_latest_run():
    s = Store(":memory:")
    # run 1: the vuln was still vulnerable
    _seed_run_with_regressions(s, [_result("aaa", "denial_of_service", "vulnerable")],
                               version="v1.1", end=True)
    # run 2 (latest): the same vuln is now fixed
    _seed_run_with_regressions(s, [_result("aaa", "denial_of_service", "fixed")],
                               version="v1.2", end=True)
    kv = build_state(Observability(s))["known_vulnerabilities"]
    # only the latest run counts — not the union of both runs
    assert kv["total"] == 1
    assert kv["fixed"] == 1
    assert kv["vulnerable"] == 0


def test_known_vulnerabilities_empty_when_no_regressions():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 100})
    kv = build_state(Observability(s))["known_vulnerabilities"]
    assert kv == {"total": 0, "vulnerable": 0, "fixed": 0, "cases": []}


# --------------------------------------------------------------------------- #
# render_html — the panel + layout
# --------------------------------------------------------------------------- #
def _html():
    s = Store(":memory:")
    _seed_run_with_regressions(s, [_result("aaa", "denial_of_service", "vulnerable")])
    return render_html(build_state(Observability(s)))


def test_render_html_has_known_vulnerabilities_panel():
    html = _html()
    assert "Known vulnerabilities" in html
    assert 'id="known-vulns"' in html


def test_render_html_renames_findings_panel():
    html = _html()
    assert "Current run findings" in html
    # the findings pipe container is retained (just re-headed)
    assert 'id="findings-pipe"' in html


def test_render_html_dual_row_layout_spans_owasp_over_both():
    html = _html()
    # a dual-row wrapper groups OWASP (left, full height) with the stacked right column
    assert "dualrow" in html
    assert 'class="rightcol"' in html
    # OWASP coverage + heatrow column template preserved
    assert "OWASP coverage" in html
    assert "grid-template-columns: 400px 1fr 35px" in html
