"""Latency/throughput baseline view over recorded trace spans (ticket 061).

Per-step latency is captured on ``kind=="trace_span"`` events (see
``tracing.Tracer.record``). :func:`latency_view` aggregates those spans into
per-agent and overall ``count``/``p50``/``p95``/``max`` of ``latency_s`` plus an
overall ``throughput`` (spans per second over the observed time window).

Stdlib only.
"""

from __future__ import annotations

import math
import statistics


def _stats(latencies: list[float]) -> dict:
    """count/p50/p95/max for a non-empty list of latencies."""
    ordered = sorted(latencies)
    n = len(ordered)
    p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
    return {
        "count": n,
        "p50": statistics.median(ordered),
        "p95": ordered[p95_idx],
        "max": ordered[-1],
    }


def latency_view(events) -> dict:
    """Aggregate per-span latency into an overall + per-agent view.

    Only ``kind=="trace_span"`` events are considered; each carries ``agent``
    (str), ``latency_s`` (float), and ``ts`` (float). Empty input yields zeros.
    """
    spans = [e for e in events if e.get("kind") == "trace_span"]

    if not spans:
        return {
            "overall": {
                "count": 0,
                "p50": 0.0,
                "p95": 0.0,
                "max": 0.0,
                "throughput": 0.0,
            },
            "by_agent": {},
        }

    latencies = [float(s["latency_s"]) for s in spans]
    timestamps = [float(s["ts"]) for s in spans]

    overall = _stats(latencies)
    window = max(timestamps) - min(timestamps)
    overall["throughput"] = (
        overall["count"] / window if overall["count"] >= 2 and window > 0 else 0.0
    )

    by_agent: dict[str, dict] = {}
    grouped: dict[str, list[float]] = {}
    for s in spans:
        grouped.setdefault(str(s["agent"]), []).append(float(s["latency_s"]))
    for agent, lats in grouped.items():
        agent_stats = _stats(lats)
        agent_stats["throughput"] = 0.0
        by_agent[agent] = agent_stats

    return {"overall": overall, "by_agent": by_agent}
