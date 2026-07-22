"""Acceptance tests for ticket 024 — Langfuse-semantics tracing seam.

Pins the FIXED contract for the tracing upgrade:

- `Tracer(client=None, store=None)` — a pluggable seam over a Langfuse-shaped
  client (mock/local). `record(agent, *, trace_id, tokens, cost_usd, latency_s,
  finding_id=None, parent_span_id=None) -> Span` emits one span per agent step.
- Each recorded step emits a Langfuse `span(name=<agent>, trace_id=..., metadata=
  {tokens, cost_usd, latency_s})` against the injected (mock) client.
- Lineage: `lineage(finding_id) -> list[Span]` resolves a confirmed finding back
  to the exact agent steps (spans sharing the finding's trace), in order.
- Per-agent cost rollup: `cost_by_agent() -> dict[str, float]`.
- Spans persist to the SQLite event log (kind="trace_span") so
  `Observability.agent_cost()` reports agent-level cost in-environment.
- No client and/or no store must never crash.
"""

import pytest

from forge.observability import Observability
from forge.store import Store
from forge.tracing import Span, Tracer


class FakeLangfuse:
    """Mock Langfuse client: records every span() call verbatim."""

    def __init__(self):
        self.spans = []

    def span(self, **kwargs):
        self.spans.append(kwargs)


# (agent, tokens, cost_usd, latency_s)
AGENTS = [
    ("red_team", 120, 0.004, 0.5),
    ("judge", 300, 0.010, 0.8),
    ("documentation", 80, 0.002, 0.3),
]


def _emit_run(tracer, trace_id, *, finding_on="judge", finding_id=7):
    spans = []
    for agent, tokens, cost, latency in AGENTS:
        spans.append(
            tracer.record(
                agent,
                trace_id=trace_id,
                tokens=tokens,
                cost_usd=cost,
                latency_s=latency,
                finding_id=(finding_id if agent == finding_on else None),
            )
        )
    return spans


# --------------------------------------------------------------------------- #
# (1) each agent step emits a Langfuse span with token / cost / latency
# --------------------------------------------------------------------------- #
def test_each_agent_step_emits_span_with_cost_latency():
    client = FakeLangfuse()
    tracer = Tracer(client=client)
    _emit_run(tracer, "trace-1")

    assert len(client.spans) == 3, "one span per agent step"
    assert [s["name"] for s in client.spans] == ["red_team", "judge", "documentation"]
    for s in client.spans:
        assert s["trace_id"] == "trace-1"
        md = s["metadata"]
        assert "tokens" in md and "cost_usd" in md and "latency_s" in md
    # the judge span carries the concrete cost/latency it was recorded with
    judge_span = next(s for s in client.spans if s["name"] == "judge")
    assert judge_span["metadata"]["cost_usd"] == pytest.approx(0.010)
    assert judge_span["metadata"]["latency_s"] == pytest.approx(0.8)
    assert judge_span["metadata"]["tokens"] == 300


# --------------------------------------------------------------------------- #
# (2) a confirmed finding traces back to the exact producing steps
# --------------------------------------------------------------------------- #
def test_finding_traces_back_to_producing_steps():
    tracer = Tracer()
    _emit_run(tracer, "trace-1", finding_on="judge", finding_id=7)
    # an unrelated trace whose spans must NOT bleed into the finding's lineage
    tracer.record("red_team", trace_id="trace-2", tokens=10, cost_usd=0.001, latency_s=0.1)

    lineage = tracer.lineage(7)
    assert [s.agent for s in lineage] == ["red_team", "judge", "documentation"], (
        "lineage resolves to the exact steps on the finding's trace, in order"
    )
    assert all(s.trace_id == "trace-1" for s in lineage)
    assert all(isinstance(s, Span) for s in lineage)


def test_lineage_of_unknown_finding_is_empty():
    tracer = Tracer()
    _emit_run(tracer, "trace-1")
    assert tracer.lineage(999) == []


# --------------------------------------------------------------------------- #
# (3) cost is attributable per-agent, not only per-run
# --------------------------------------------------------------------------- #
def test_cost_attributable_per_agent():
    tracer = Tracer()
    _emit_run(tracer, "trace-1")
    _emit_run(tracer, "trace-2")

    by_agent = tracer.cost_by_agent()
    assert by_agent["red_team"] == pytest.approx(0.008)
    assert by_agent["judge"] == pytest.approx(0.020)
    assert by_agent["documentation"] == pytest.approx(0.004)


# --------------------------------------------------------------------------- #
# (4) spans persist to the store; Observability reads agent-level cost
# --------------------------------------------------------------------------- #
def test_observability_reads_agent_level_cost_from_spans():
    store = Store(":memory:")
    tracer = Tracer(store=store)
    _emit_run(tracer, "trace-1")

    span_events = [e for e in store.get_events() if e.get("kind") == "trace_span"]
    assert len(span_events) == 3, "each span persisted as an append-only event"

    agent_cost = Observability(store).agent_cost()
    assert set(agent_cost) == {"red_team", "judge", "documentation"}
    assert agent_cost["judge"] == pytest.approx(0.010)
    assert agent_cost["red_team"] == pytest.approx(0.004)


# --------------------------------------------------------------------------- #
# (5) degrade gracefully with no client and/or no store
# --------------------------------------------------------------------------- #
def test_tracer_without_client_or_store_still_records():
    tracer = Tracer()
    span = tracer.record("judge", trace_id="t", tokens=1, cost_usd=0.1, latency_s=0.2)
    assert isinstance(span, Span)
    assert tracer.cost_by_agent() == {"judge": pytest.approx(0.1)}


def test_start_trace_ids_are_unique():
    tracer = Tracer()
    ids = {tracer.start_trace() for _ in range(5)}
    assert len(ids) == 5, "each started trace gets a distinct id"
