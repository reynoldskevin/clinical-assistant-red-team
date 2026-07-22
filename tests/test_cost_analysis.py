"""Ticket 021 — AI Cost Analysis deliverable.

Locked acceptance tests. Two halves:

1. `forge/cost_analysis.py` derives the dev-spend baseline from *recorded cost
   rows* and projects production cost across four scale tiers, where each tier
   forces a distinct architectural change (so the projection is NOT a linear
   token×runs estimate).
2. The committed `./AI_COST_ANALYSIS.md` reports actual dev spend and the four
   tiers, each with its architectural note.
"""

from __future__ import annotations

import pathlib
import re

from forge.cost_analysis import (
    DEFAULT_TIERS,
    dev_baseline,
    project,
    render_markdown,
)
from forge.store import Store

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "AI_COST_ANALYSIS.md"


def _seed_store(tmp_path) -> Store:
    store = Store(str(tmp_path / "cost.db"))
    # Two categories, known USD + token figures.
    store.insert_cost({"category": "prompt_injection", "input_tokens": 1000, "output_tokens": 400, "usd": 0.30})
    store.insert_cost({"category": "tool_misuse", "input_tokens": 500, "output_tokens": 200, "usd": 0.10})
    # Four verdict events => four attempts.
    for _ in range(4):
        store.append_event({"kind": "verdict", "category": "prompt_injection", "verdict": "fail"})
    return store


def test_dev_baseline_derives_from_recorded_cost_rows(tmp_path) -> None:
    store = _seed_store(tmp_path)
    base = dev_baseline(store)
    assert base["total_usd"] == 0.40
    assert base["attempts"] == 4
    assert base["usd_per_attempt"] == 0.10


def test_empty_store_baseline_is_zero(tmp_path) -> None:
    store = Store(str(tmp_path / "empty.db"))
    base = dev_baseline(store)
    assert base["total_usd"] == 0.0
    assert base["attempts"] == 0
    assert base["usd_per_attempt"] == 0.0


def test_projection_has_the_four_required_tiers(tmp_path) -> None:
    base = dev_baseline(_seed_store(tmp_path))
    tiers = project(base)
    assert [t.runs for t in tiers] == list(DEFAULT_TIERS) == [100, 1_000, 10_000, 100_000]


def test_projection_is_nonlinear_and_sublinear_per_run(tmp_path) -> None:
    base = dev_baseline(_seed_store(tmp_path))
    tiers = project(base)
    # Naive linear cost is usd_per_attempt * runs.
    for t in tiers:
        assert abs(t.naive_usd - base["usd_per_attempt"] * t.runs) < 1e-9
    # Above the baseline tier, the architectural change makes effective cost
    # strictly cheaper than the naive linear estimate.
    for t in tiers[1:]:
        assert t.effective_usd < t.naive_usd
    # Per-run effective cost decreases monotonically as scale grows (sub-linear).
    per_run = [t.per_run_usd for t in tiers]
    assert per_run == sorted(per_run, reverse=True)
    assert per_run[-1] < per_run[0]


def test_each_tier_names_an_architectural_change(tmp_path) -> None:
    base = dev_baseline(_seed_store(tmp_path))
    for t in project(base):
        assert isinstance(t.strategy, str) and t.strategy.strip()
        assert isinstance(t.note, str) and len(t.note.strip()) >= 10


def test_render_markdown_reports_tiers_and_strategies(tmp_path) -> None:
    base = dev_baseline(_seed_store(tmp_path))
    md = render_markdown(base)
    for label in ("100", "1,000", "10,000", "100,000"):
        assert label in md
    lowered = md.lower()
    assert "cach" in lowered
    assert "batch" in lowered
    assert "sampl" in lowered
    assert "local" in lowered
    # Reports actual dev spend derived from the baseline.
    assert f"{base['total_usd']:.2f}" in md


def test_committed_doc_present_and_complete() -> None:
    assert DOC.exists(), "AI_COST_ANALYSIS.md must exist at repo root"
    text = DOC.read_text()
    for label in ("100", "1,000", "10,000", "100,000"):
        assert label in text, f"tier {label} missing from doc"
    lowered = text.lower()
    # Each mandated architectural lever is discussed.
    for kw in ("cach", "batch", "sampl", "local"):
        assert kw in lowered, f"architectural lever '{kw}' missing from doc"
    # Reports an actual dev-spend dollar figure.
    assert re.search(r"\$\s?\d+(\.\d+)?", text), "no dev-spend dollar figure in doc"
