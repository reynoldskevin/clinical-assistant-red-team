"""Offline load/stress harness for the target adapter (ticket 061).

Drives N attack cases through a :class:`~forge.target.TargetAdapter` built with
an INJECTED fake transport — no live sidecar, no socket, no ANTHROPIC_API_KEY.
Each op is timed with an injectable clock for deterministic aggregates. The
default transport is an offline stub returning ``200 {"answer": "ok"}``.

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import time

from forge.access import TargetRegistry
from forge.store import Store
from forge.target import (
    TargetAdapter,
    TargetUnreachable,
    TransportResponse,
)


def _offline_ok_transport(method, url, headers, body) -> TransportResponse:
    """Built-in default transport: never opens a socket."""
    return TransportResponse(status=200, body={"answer": "ok"})


def run_load(
    cases: int = 100,
    *,
    transport=None,
    clock=None,
    store=None,
    pid: int = 1,
    base_url: str = "http://fake-target",
) -> dict:
    """Run ``cases`` ask() ops through an adapter with a fake transport.

    Returns a summary: cases run, successes, failures, total/mean latency,
    throughput. Deterministic under an injected ``clock`` and ``transport``.
    """
    clock = clock or time.perf_counter
    adapter = TargetAdapter(
        TargetRegistry({"copilot": {"base_url": base_url}}),
        "copilot",
        token_provider=lambda pid: "t",
        store=store or Store(":memory:"),
        transport=transport or _offline_ok_transport,
    )

    successes = 0
    failures = 0
    total = 0.0
    for i in range(cases):
        before = clock()
        try:
            adapter.ask(pid, f"q{i}")
            successes += 1
        except TargetUnreachable:
            failures += 1
        after = clock()
        total += after - before

    return {
        "cases": cases,
        "successes": successes,
        "failures": failures,
        "total_latency_s": total,
        "mean_latency_s": total / cases if cases else 0.0,
        "throughput": cases / total if total > 0 else 0.0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline load/stress harness.")
    parser.add_argument("--cases", type=int, default=100, help="number of cases")
    args = parser.parse_args(argv)
    summary = run_load(cases=args.cases)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
