"""Acceptance tests for ticket 030 — dashboard run-in-progress indicator +
live refresh countdown.

`build_state` exposes `run_active` (a run started with no later `run_end`) so the
masthead can show a "run in progress" chip; the refresh pill counts down per second.
"""

import json

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import build_state, render_html


def _obs(events):
    s = Store(":memory:")
    for ev in events:
        s.append_event(ev)
    return Observability(s)


def test_run_active_true_when_started_not_ended():
    obs = _obs([
        {"kind": "run_start"},
        {"kind": "attack", "attempt_id": 1, "category": "prompt_injection"},
    ])
    state = build_state(obs)
    assert state["run_active"] is True
    assert json.loads(json.dumps(state)) == state


def test_run_active_false_after_run_end():
    obs = _obs([{"kind": "run_start"}, {"kind": "run_end"}])
    assert build_state(obs)["run_active"] is False


def test_run_active_true_when_new_run_starts_after_prior_end():
    # a fresh run started after the previous one ended -> active again
    obs = _obs([
        {"kind": "run_start"}, {"kind": "run_end"},
        {"kind": "run_start"},
    ])
    assert build_state(obs)["run_active"] is True


def test_run_active_false_with_no_run_events():
    obs = _obs([
        {"kind": "verdict", "attempt_id": 1, "category": "x", "verdict": "fail", "target_version": "v1"},
    ])
    assert build_state(obs)["run_active"] is False


def test_render_html_has_run_indicator_and_countdown():
    html = render_html(build_state(_obs([{"kind": "run_start"}])))
    # run-in-progress indicator element present
    assert 'id="runstate"' in html
    # refresh pill with a countdown
    assert 'id="refresh-pill"' in html
    assert "refresh" in html.lower()
    # a per-second tick that still polls the state endpoint
    assert "setInterval" in html
    assert "/api/state" in html
