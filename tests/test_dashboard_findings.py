"""Acceptance tests for fix 029 — the dashboard "Findings" tile shows verdict
outcomes (Exploited/Partial/Defended), not the finding-lifecycle.

The live dashboard rendered `Open / In progress / Resolved` reading all zeros
because findings only exist on a confirmed exploit; the target defended every
attempt, so the lifecycle was legitimately empty and looked broken. The approved
mockup showed the verdict-outcome breakdown, which always has real numbers.
"""

import json

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import build_state, render_html


def _seed():
    """2 exploited (success) + 1 partial + 4 defended (fail) = 7 attempts."""
    s = Store(":memory:")
    for i, v in enumerate(["success", "success", "partial", "fail", "fail", "fail", "fail"], 1):
        s.append_event(
            {"kind": "verdict", "attempt_id": i, "category": "prompt_injection",
             "verdict": v, "confidence": 0.8, "target_version": "v1"}
        )
    return s


def _state():
    return build_state(Observability(_seed()))


def test_build_state_exposes_verdict_outcomes():
    state = _state()
    assert state["outcomes"] == {"exploited": 2, "partial": 1, "defended": 4}
    # still JSON-serializable
    assert json.loads(json.dumps(state)) == state


def test_outcomes_match_pass_fail_overall():
    obs = Observability(_seed())
    overall = obs.pass_fail()["overall"]
    outcomes = build_state(obs)["outcomes"]
    assert outcomes["exploited"] == overall["exploits"]
    assert outcomes["partial"] == overall["partial"]
    assert outcomes["defended"] == overall["defended"]


def test_findings_tile_shows_outcome_headings_not_lifecycle():
    html = render_html(_state())
    # mockup headings restored
    for heading in ("Exploited", "Partial", "Defended"):
        assert heading in html
    # the regressed finding-lifecycle labels are gone
    assert "In progress" not in html
    assert "Resolved" not in html
