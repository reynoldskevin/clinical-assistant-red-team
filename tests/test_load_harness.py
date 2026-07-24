"""Acceptance tests for ticket 061 — latency/throughput baseline + load harness.

- `forge.perf.latency_view(events)` aggregates the per-span `latency_s` recorded on
  `kind=="trace_span"` events into per-agent and overall p50/p95/max + throughput.
- `forge.load_test.run_load(...)` drives N cases through a TargetAdapter built with an
  INJECTED fake transport (no socket, no API key), under an injected clock for determinism,
  and returns a summary.
"""

import pytest

from forge.store import Store
from forge.perf import latency_view
from forge.load_test import run_load, main
from forge.target import TransportResponse


# --------------------------------------------------------------------------- #
# latency_view
# --------------------------------------------------------------------------- #
def _seed_spans(store):
    # red_team: 3 spans, judge: 2 spans; ts spans exactly 1.0s (1000.0 -> 1001.0)
    rows = [
        ("red_team", 0.1, 1000.0),
        ("red_team", 0.3, 1000.25),
        ("red_team", 0.5, 1000.5),
        ("judge", 0.2, 1000.75),
        ("judge", 0.4, 1001.0),
    ]
    for agent, lat, ts in rows:
        store.append_event({"kind": "trace_span", "agent": agent, "latency_s": lat, "ts": ts})


def test_latency_view_overall_and_per_agent():
    s = Store(":memory:")
    _seed_spans(s)
    view = latency_view(s.get_events())

    ov = view["overall"]
    assert ov["count"] == 5
    assert ov["max"] == pytest.approx(0.5)
    assert ov["p50"] == pytest.approx(0.3)  # median of [.1,.2,.3,.4,.5]
    assert ov["p50"] <= ov["p95"] <= ov["max"]
    # throughput = spans / elapsed window (1001.0 - 1000.0 == 1.0s)
    assert ov["throughput"] == pytest.approx(5.0)

    rt = view["by_agent"]["red_team"]
    assert rt["count"] == 3
    assert rt["max"] == pytest.approx(0.5)
    assert rt["p50"] == pytest.approx(0.3)
    assert view["by_agent"]["judge"]["count"] == 2


def test_latency_view_empty_is_zeros():
    view = latency_view([])
    assert view["overall"]["count"] == 0
    assert view["overall"]["p50"] == 0.0
    assert view["overall"]["p95"] == 0.0
    assert view["overall"]["max"] == 0.0
    assert view["overall"]["throughput"] == 0.0
    assert view["by_agent"] == {}


def test_latency_view_ignores_non_span_events():
    s = Store(":memory:")
    s.append_event({"kind": "verdict", "verdict": "fail"})
    _seed_spans(s)
    assert latency_view(s.get_events())["overall"]["count"] == 5


# --------------------------------------------------------------------------- #
# load harness
# --------------------------------------------------------------------------- #
class _StepClock:
    """Deterministic monotonic clock: each call advances by ``step`` seconds."""

    def __init__(self, step=1.0):
        self.t = 0.0
        self.step = step

    def __call__(self):
        v = self.t
        self.t += self.step
        return v


def _ok_transport(method, url, headers, body):
    return TransportResponse(status=200, body={"answer": "ok"})


def _fail_transport(method, url, headers, body):
    return TransportResponse(status=500, body={})


def test_run_load_counts_successes():
    summary = run_load(cases=5, transport=_ok_transport, clock=_StepClock(1.0), store=Store(":memory:"))
    assert summary["cases"] == 5
    assert summary["successes"] == 5
    assert summary["failures"] == 0
    # each op measured across two clock ticks -> 1.0s; 5 ops -> 5.0s total
    assert summary["total_latency_s"] == pytest.approx(5.0)
    assert summary["mean_latency_s"] == pytest.approx(1.0)
    assert summary["throughput"] == pytest.approx(5.0 / 5.0)


def test_run_load_counts_failures():
    summary = run_load(cases=4, transport=_fail_transport, clock=_StepClock(1.0), store=Store(":memory:"))
    assert summary["cases"] == 4
    assert summary["successes"] == 0
    assert summary["failures"] == 4


def test_run_load_default_100_cases_is_offline():
    # no transport, no store, no API key -> must run fully offline against a built-in stub
    summary = run_load(clock=_StepClock(0.5))
    assert summary["cases"] == 100
    assert summary["successes"] == 100


def test_main_entrypoint_runs():
    # callable smoke (not a subprocess); default offline stub transport
    assert main(["--cases", "3"]) == 0
