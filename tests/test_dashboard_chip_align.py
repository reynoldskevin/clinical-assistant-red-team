"""Acceptance tests for ticket 034 — group the status chips in one right-aligned
bar, 10s refresh interval, and header spacing matching the grid gap."""

import re

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import build_state, render_html


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start"})
    return render_html(build_state(Observability(s)))


def test_status_chips_grouped_in_one_right_aligned_bar():
    html = _html()
    # both chips wrapped in one .statusbar, in order, before the grid
    i_bar = html.find('class="statusbar"')
    i_run = html.find('id="runstate"')
    i_pill = html.find('id="refresh-pill"')
    i_grid = html.find('class="grid"')
    assert -1 < i_bar < i_run < i_pill < i_grid
    # only the wrapper carries margin-left:auto (chips no longer split apart)
    assert re.search(r"\.statusbar \{[^}]*margin-left: auto", html)
    assert not re.search(r"\.live \{[^}]*margin-left: auto", html)
    assert not re.search(r"\.runstate \{[^}]*margin-left: auto", html)


def test_refresh_interval_is_10s():
    html = _html()
    assert "REFRESH_S = 10" in html
    assert '<span class="num" id="refresh-count">10</span>' in html


def test_header_spacing_matches_grid_gap():
    html = _html()
    # masthead bottom margin equals the grid row gap (14px)
    assert re.search(r"\.masthead \{[^}]*margin-bottom: 14px", html)
    assert re.search(r"\.grid \{[^}]*gap: 14px", html)
