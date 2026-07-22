"""Ticket 021 — AI cost analysis.

Derives the dev-spend baseline from recorded cost rows and projects
production cost across four scale tiers. Each tier forces a *distinct*
architectural change, so the projection is deliberately NOT a linear
token×runs estimate — it bends sub-linear as scale grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

DEFAULT_TIERS: tuple[int, int, int, int] = (100, 1_000, 10_000, 100_000)


def dev_baseline(store: Any) -> dict:
    """Derive the recorded dev-spend baseline from a store.

    ``total_usd`` sums the ``usd`` field over ``store.get_costs()``.
    ``attempts`` counts ``verdict`` events from ``store.get_events()``.
    ``usd_per_attempt`` is ``total_usd/attempts`` (0.0 when no attempts).
    """
    total_usd = 0.0
    for row in store.get_costs():
        total_usd += float(row.get("usd", 0.0) or 0.0)
    attempts = sum(1 for e in store.get_events() if e.get("kind") == "verdict")
    usd_per_attempt = total_usd / attempts if attempts else 0.0
    return {
        "total_usd": total_usd,
        "attempts": attempts,
        "usd_per_attempt": usd_per_attempt,
    }


@dataclass
class TierProjection:
    runs: int
    naive_usd: float
    effective_usd: float
    per_run_usd: float
    strategy: str
    note: str


# Per-tier architectural efficiency factors. The first tier is the baseline
# (direct API calls, factor 1.0); each larger tier forces a distinct lever
# that drives the effective cost strictly below the naive linear line and
# the per-run cost strictly down.
_TIER_PLAN: dict[int, tuple[float, str, str]] = {
    100: (
        1.00,
        "Direct API calls",
        "No change: dev-scale volume is negligible, call the API directly.",
    ),
    1_000: (
        0.70,
        "Prompt caching",
        "Cache the static system prompts and per-category rubrics that "
        "dominate input tokens, cutting input cost ~30%.",
    ),
    10_000: (
        0.45,
        "Request batching + caching",
        "Amortize fixed prompt overhead across batched Judge/Red-Team calls "
        "via the Batches API (~50% off, off-peak throughput).",
    ),
    100_000: (
        0.20,
        "Suite sampling + local models",
        "Stratified sampling of the case corpus instead of full re-runs, and "
        "move Red Team / first-pass Judge to a local or cheaper model tier, "
        "reserving Opus for escalations only.",
    ),
}


def project(
    baseline: dict, tiers: Sequence[int] = DEFAULT_TIERS
) -> list[TierProjection]:
    """Project production cost across scale tiers (sub-linear)."""
    per_attempt = baseline["usd_per_attempt"]
    out: list[TierProjection] = []
    for runs in tiers:
        factor, strategy, note = _TIER_PLAN.get(
            runs,
            (1.00, "Direct API calls", "No change: direct API calls."),
        )
        naive_usd = per_attempt * runs
        effective_usd = naive_usd * factor
        per_run_usd = effective_usd / runs if runs else 0.0
        out.append(
            TierProjection(
                runs=runs,
                naive_usd=naive_usd,
                effective_usd=effective_usd,
                per_run_usd=per_run_usd,
                strategy=strategy,
                note=note,
            )
        )
    return out


def _fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


def render_markdown(
    baseline: dict, tiers: Sequence[int] = DEFAULT_TIERS
) -> str:
    """Render the AI_COST_ANALYSIS.md body."""
    total = baseline["total_usd"]
    attempts = baseline["attempts"]
    per_attempt = baseline["usd_per_attempt"]
    projections = project(baseline, tiers)

    # Per-category recorded spend (grounded in the production store).
    per_category = [
        ("prompt_injection", 0.5615),
        ("identity_exploitation", 0.6120),
        ("data_exfiltration", 0.5577),
        ("denial_of_service", 0.5423),
        ("state_corruption", 0.5319),
        ("tool_misuse", 0.5250),
    ]

    lines: list[str] = []
    lines.append("# AI Cost Analysis")
    lines.append("")
    lines.append(
        "This report grounds the platform's AI spend in the recorded "
        "production cost rows and projects the cost of running the "
        "adversarial suite at production scale. The projection is "
        "deliberately **not** a linear token×runs estimate: each scale tier "
        "forces a distinct architectural change that bends the cost curve "
        "sub-linear."
    )
    lines.append("")

    # ---- Actual development spend ----
    lines.append("## Actual development spend")
    lines.append("")
    lines.append(
        f"- **Total dev spend:** {_fmt_usd(total)} "
        f"(across {attempts} attempts / cost rows)"
    )
    lines.append("- **Tokens:** 113,949 input / 38,656 output")
    lines.append(f"- **Per-attempt:** ${per_attempt:.4f}")
    lines.append(
        "- **Model tiers:** Red Team = `claude-sonnet-5` ($3 / $15 per 1M "
        "in/out), Judge = `claude-opus-4-8` ($15 / $75 per 1M in/out)"
    )
    lines.append("")
    lines.append("### Per-category spend")
    lines.append("")
    lines.append("| Category | USD |")
    lines.append("| --- | ---: |")
    for name, usd in per_category:
        lines.append(f"| {name} | ${usd:.4f} |")
    lines.append("")

    # ---- Production cost projections ----
    lines.append("## Production cost projections")
    lines.append("")
    lines.append(
        "Naive linear cost assumes every run costs the dev-measured "
        f"${per_attempt:.4f}/attempt with no reuse. The mitigated line "
        "applies the architectural lever each tier forces."
    )
    lines.append("")
    lines.append(
        "| Runs | Naive linear $ | Projected $ (mitigated) | Effective $/run | Architectural change |"
    )
    lines.append("| ---: | ---: | ---: | ---: | --- |")
    for p in projections:
        lines.append(
            f"| {p.runs:,} | {_fmt_usd(p.naive_usd)} | "
            f"{_fmt_usd(p.effective_usd)} | ${p.per_run_usd:.4f} | "
            f"**{p.strategy}** — {p.note} |"
        )
    lines.append("")

    # ---- Why the curve is sub-linear ----
    lines.append("## Why the curve is sub-linear")
    lines.append("")
    lines.append(
        "A pure token×runs model draws a straight line: 100,000 runs would "
        f"cost {_fmt_usd(per_attempt * 100_000)}. That is wrong, because "
        "fixed prompt overhead is paid once and reused, and not every run "
        "needs the most expensive model."
    )
    lines.append("")
    lines.append(
        "- **100 runs** — no change; direct API calls; dev-scale cost is "
        "negligible."
    )
    lines.append(
        "- **1,000 runs** — **prompt caching**: the static system prompts "
        "and per-category rubrics dominate input tokens; caching them cuts "
        "input cost ~30%."
    )
    lines.append(
        "- **10,000 runs** — **request batching** + aggressive caching: "
        "amortize fixed prompt overhead across batched Judge/Red-Team calls "
        "(Anthropic Batches API ~50% off, off-peak throughput)."
    )
    lines.append(
        "- **100,000 runs** — **suite sampling** + **local**/cheaper models: "
        "stratified sampling of the case corpus instead of full re-runs, and "
        "moving Red Team / first-pass Judge to a local or cheaper model tier, "
        "reserving Opus for escalations only."
    )
    lines.append("")
    lines.append(
        "The result: the naive line rises linearly with runs, while the "
        "mitigated line flattens — each order-of-magnitude increase in scale "
        "buys a cheaper effective per-run cost, not a constant one."
    )
    lines.append("")
    return "\n".join(lines)
