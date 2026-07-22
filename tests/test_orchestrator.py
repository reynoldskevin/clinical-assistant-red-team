"""Acceptance tests for ticket 014 — Orchestrator agent (prioritize · budget · trigger).

The Orchestrator is the strategist: it reads the Observability read-model and
decides the next `AttackDirective`, enforces budgets, halts/redirects on low
signal, applies coverage-sufficiency, and emits `RegressionTrigger`s. These tests
seed a REAL in-memory Store + Observability (verdict events, findings, cost rows)
so the decision logic runs against the genuine read-model, not a mock of it.

Pinned contract:
- `Orchestrator(observability, *, categories, target_id="copilot", run_budget_usd,
  coverage_target, pass_rate_target, directive_max_attempts, directive_max_cost_usd,
  min_spend_before_halt, min_signal_per_usd)`
- `next_directive() -> AttackDirective | None`  (None == halt / nothing to do)
- `is_covered(category) -> bool`
- `signal_per_usd() -> float`
- `should_halt_for_low_signal() -> bool`
- `regression_trigger(*, target_version, previous_version, seconds_since_last_run=None,
  window_seconds=None) -> RegressionTrigger | None`
"""

import pytest

from forge.observability import Observability
from forge.orchestrator import Orchestrator
from forge.schemas import AttackDirective, RegressionTrigger
from forge.store import Store


CATS = ["data_exfiltration", "prompt_injection", "tool_misuse"]


def _obs(store):
    return Observability(store)


def _seed_verdicts(store, category, n, verdict="fail", target_version="v1"):
    for _ in range(n):
        store.append_event(
            {
                "kind": "verdict",
                "category": category,
                "verdict": verdict,
                "confidence": 0.9,
                "target_version": target_version,
            }
        )


def _seed_cost(store, category, usd):
    store.insert_cost({"category": category, "input_tokens": 10, "output_tokens": 5, "usd": usd})


def _orch(store, **kw):
    params = dict(
        categories=CATS,
        target_id="copilot",
        run_budget_usd=5.0,
        coverage_target=3,
        pass_rate_target=1.0,
        directive_max_attempts=3,
        directive_max_cost_usd=1.0,
        min_spend_before_halt=0.5,
        min_signal_per_usd=1.0,
    )
    params.update(kw)
    return Orchestrator(_obs(store), **params)


# --------------------------------------------------------------------------- #
# (1) coverage-driven selection
# --------------------------------------------------------------------------- #
def test_cold_start_selects_a_category():
    store = Store(":memory:")
    d = _orch(store).next_directive()
    assert isinstance(d, AttackDirective)
    assert d.category in CATS
    # budgets propagate onto the directive
    assert d.max_attempts == 3
    assert d.max_cost_usd == 1.0


def test_selects_least_covered_gap():
    store = Store(":memory:")
    _seed_verdicts(store, "prompt_injection", 5)   # covered (>=3, pass_rate 1.0)
    _seed_verdicts(store, "tool_misuse", 1)        # under-covered
    # data_exfiltration has 0 attempts → least covered of all
    d = _orch(store).next_directive()
    assert d is not None
    assert d.category == "data_exfiltration", "picks the least-covered surface"


def test_round_robin_advances_as_categories_fill():
    store = Store(":memory:")
    # two categories at 0, one covered → least-covered tie broken deterministically
    _seed_verdicts(store, "tool_misuse", 5)
    first = _orch(store).next_directive().category
    assert first in ("data_exfiltration", "prompt_injection")
    # once the first gap is covered, the next call advances to the other gap
    _seed_verdicts(store, first, 5)
    second = _orch(store).next_directive().category
    assert second != first
    assert second in ("data_exfiltration", "prompt_injection")


# --------------------------------------------------------------------------- #
# (2) high-severity finding takes priority (re-probe even when covered)
# --------------------------------------------------------------------------- #
def test_open_high_severity_finding_is_reprobed():
    store = Store(":memory:")
    for c in CATS:  # everything sufficiently covered
        _seed_verdicts(store, c, 4)
    store.insert_finding(
        {"severity": "high", "attack_category": "tool_misuse", "status": "open"}
    )
    d = _orch(store).next_directive()
    assert d is not None and d.category == "tool_misuse", (
        "an open high-severity finding is re-probed even when the category is covered"
    )


def test_resolved_finding_is_not_reprobed():
    store = Store(":memory:")
    for c in CATS:
        _seed_verdicts(store, c, 4)
    store.insert_finding(
        {"severity": "high", "attack_category": "tool_misuse", "status": "resolved"}
    )
    # all covered, the only finding is resolved → nothing left to do → halt
    assert _orch(store).next_directive() is None


# --------------------------------------------------------------------------- #
# (3) coverage-sufficiency
# --------------------------------------------------------------------------- #
def test_category_at_threshold_is_marked_covered():
    store = Store(":memory:")
    _seed_verdicts(store, "prompt_injection", 3)   # exactly at coverage_target, all defended
    orch = _orch(store)
    assert orch.is_covered("prompt_injection") is True
    assert orch.is_covered("tool_misuse") is False  # 0 attempts


def test_low_pass_rate_is_not_covered():
    store = Store(":memory:")
    _seed_verdicts(store, "prompt_injection", 3, verdict="fail")
    _seed_verdicts(store, "prompt_injection", 2, verdict="success")  # exploits → pass_rate < 1.0
    # attempts >= target but pass_rate below target → still needs probing
    assert _orch(store).is_covered("prompt_injection") is False


# --------------------------------------------------------------------------- #
# (4) halt / redirect on signal-per-token
# --------------------------------------------------------------------------- #
def test_low_signal_redirects_while_gaps_remain():
    store = Store(":memory:")
    _seed_verdicts(store, "prompt_injection", 5)   # covered, all defended (no signal)
    _seed_cost(store, "prompt_injection", 2.0)     # real spend, zero exploits
    orch = _orch(store)
    assert orch.signal_per_usd() == 0.0
    d = orch.next_directive()
    assert d is not None, "coverage gaps remain → redirect, don't halt"
    assert d.category in ("data_exfiltration", "tool_misuse")


def test_low_signal_halts_when_all_covered():
    store = Store(":memory:")
    for c in CATS:
        _seed_verdicts(store, c, 4)
        _seed_cost(store, c, 0.5)
    orch = _orch(store)
    assert orch.should_halt_for_low_signal() is True
    assert orch.next_directive() is None, "all covered + no signal → halt cleanly"


# --------------------------------------------------------------------------- #
# (5) per-run budget hard stop
# --------------------------------------------------------------------------- #
def test_run_budget_reached_halts_even_with_gaps():
    store = Store(":memory:")
    _seed_verdicts(store, "prompt_injection", 1)   # big coverage gaps remain
    _seed_cost(store, "prompt_injection", 6.0)     # over the 5.0 run budget
    assert _orch(store).next_directive() is None, "budget exhausted → halt regardless of coverage"


# --------------------------------------------------------------------------- #
# (6) regression triggers
# --------------------------------------------------------------------------- #
def test_regression_trigger_on_version_change():
    trig = _orch(Store(":memory:")).regression_trigger(
        target_version="v2", previous_version="v1"
    )
    assert isinstance(trig, RegressionTrigger)
    assert trig.reason == "target_version_change"
    assert trig.target_id == "copilot"
    assert trig.target_version == "v2"


def test_regression_trigger_on_time_window():
    trig = _orch(Store(":memory:")).regression_trigger(
        target_version="v1", previous_version="v1",
        seconds_since_last_run=7200, window_seconds=3600,
    )
    assert isinstance(trig, RegressionTrigger)
    assert trig.reason == "time_window"


def test_no_regression_when_stable_and_within_window():
    trig = _orch(Store(":memory:")).regression_trigger(
        target_version="v1", previous_version="v1",
        seconds_since_last_run=60, window_seconds=3600,
    )
    assert trig is None


def test_version_change_takes_priority_over_window():
    trig = _orch(Store(":memory:")).regression_trigger(
        target_version="v2", previous_version="v1",
        seconds_since_last_run=10, window_seconds=3600,
    )
    assert trig.reason == "target_version_change"
