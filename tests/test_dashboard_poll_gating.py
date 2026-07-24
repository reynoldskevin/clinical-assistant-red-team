"""Acceptance tests for ticket 074 — auto-refresh polls only while a run is active.

Polling is gated on a `pollActive` flag: enabled from an in-progress initial state or a Start
click, disabled when a run is detected finished. `tick()` keeps the clock live but does not poll
when idle.
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    return render_html(build_state(Observability(Store(":memory:"))))


def test_tick_gates_poll_on_pollactive():
    html = _html()
    assert re.search(r"if \(!pollActive\) return", html), "tick() must not poll when idle"


def test_pollactive_initialized_from_run_active():
    html = _html()
    assert re.search(r"pollActive = !!\(initial && initial\.run_active\)", html)


def test_start_click_enables_polling():
    html = _html()
    assert re.search(r"pollActive = true", html)


def test_idle_disables_polling():
    html = _html()
    assert re.search(r"pollActive = false", html)


def test_interval_and_pill_not_regressed():
    html = _html()
    assert "setInterval" in html
    assert 'id="refresh-pill"' in html
    assert '<span class="num" id="refresh-count">10</span>' in html
