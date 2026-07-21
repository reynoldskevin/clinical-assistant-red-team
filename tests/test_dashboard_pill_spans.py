"""Acceptance tests for ticket 032 — third-row 6/3/3 spans + restored static
"auto-refresh" pill with the green flashing pulse (countdown reverted).
"""

import re

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import build_state, render_html


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start"})
    return render_html(build_state(Observability(s)))


def test_third_row_spans():
    # superseded by ticket 033 (5/3/4); authoritative assertion in
    # tests/test_dashboard_owasp_label.py
    html = _html()
    assert re.search(r'class="w c5">\s*<div class="whead"><span class="wt"><span class="id">03</span> OWASP coverage', html)
    assert re.search(r'class="w c3">\s*<div class="whead"><span class="wt"><span class="id">04</span> Cost', html)
    assert re.search(r'class="w c4">\s*<div class="whead"><span class="wt"><span class="id">05</span> Findings', html)


def test_refresh_pill_green_pulse_autorefresh_label_and_countdown():
    html = _html()
    # green flashing pulse dot + "auto-refresh" label + a live countdown number
    assert (
        '<span class="live" id="refresh-pill"><span class="pulse"></span>'
        'auto-refresh · <span class="num" id="refresh-count">5</span>s</span>'
    ) in html
    # the ↻ icon / "next refresh" / "refreshing" variants are gone
    assert "next refresh" not in html
    assert "refreshing" not in html.lower()
    assert "↻" not in html
    # the number counts down each second (per-second tick) and still polls
    assert "setInterval" in html
    assert 'id="refresh-count"' in html


def test_polling_and_runstate_intact():
    html = _html()
    assert "setInterval" in html
    assert "/api/state" in html
    assert 'id="runstate"' in html  # run-in-progress indicator kept
