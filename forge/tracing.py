"""Pluggable tracing seam with Langfuse semantics (ticket 024).

A stdlib-only tracing layer that mirrors Langfuse's span/trace model without
taking a runtime dependency on it. `Tracer` accepts an optional Langfuse-shaped
`client` (mock or local) and an optional `Store`:

    - `record(...)` emits one `Span` per agent step, mirrors it to the client as
      a Langfuse `span(name=..., trace_id=..., metadata={...})` call, and
      persists it to the event log (kind="trace_span").
    - `lineage(finding_id)` resolves a confirmed finding back to the exact agent
      steps that produced it (all spans on the finding's trace(s)), in order.
    - `cost_by_agent()` rolls per-span cost up per agent.
    - `start_trace()` mints a fresh unique trace id.

No client and/or no store must never crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count


@dataclass
class Span:
    """A single agent step in a trace, with cost/latency/token attribution."""

    trace_id: str
    span_id: str
    agent: str
    tokens: int
    cost_usd: float
    latency_s: float
    finding_id: int | None = None
    parent_span_id: str | None = None


class Tracer:
    """Records agent steps as spans, optionally mirroring to a Langfuse client
    and persisting to the event log."""

    def __init__(self, client=None, store=None):
        self.client = client
        self.store = store
        self.spans: list[Span] = []
        self._span_seq = count(1)
        self._trace_seq = count(1)

    def record(
        self,
        agent: str,
        *,
        trace_id: str,
        tokens: int,
        cost_usd: float,
        latency_s: float,
        finding_id: int | None = None,
        parent_span_id: str | None = None,
    ) -> Span:
        span = Span(
            trace_id=trace_id,
            span_id=f"span-{next(self._span_seq)}",
            agent=agent,
            tokens=tokens,
            cost_usd=cost_usd,
            latency_s=latency_s,
            finding_id=finding_id,
            parent_span_id=parent_span_id,
        )
        self.spans.append(span)

        if self.client is not None:
            self.client.span(
                name=agent,
                trace_id=trace_id,
                metadata={
                    "tokens": tokens,
                    "cost_usd": cost_usd,
                    "latency_s": latency_s,
                },
            )

        if self.store is not None:
            self.store.append_event(
                {
                    "kind": "trace_span",
                    "trace_id": trace_id,
                    "span_id": span.span_id,
                    "agent": agent,
                    "tokens": tokens,
                    "cost_usd": cost_usd,
                    "latency_s": latency_s,
                    "finding_id": finding_id,
                }
            )

        return span

    def lineage(self, finding_id) -> list[Span]:
        trace_ids = {
            span.trace_id for span in self.spans if span.finding_id == finding_id
        }
        if not trace_ids:
            return []
        return [span for span in self.spans if span.trace_id in trace_ids]

    def cost_by_agent(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for span in self.spans:
            totals[span.agent] = totals.get(span.agent, 0.0) + span.cost_usd
        return totals

    def start_trace(self) -> str:
        return f"trace-{next(self._trace_seq)}"
