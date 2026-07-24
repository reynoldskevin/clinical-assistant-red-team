"""Ticket 052 — report-button visibility + trend polish.

1. Exploits-panel "View reports" button hides when exploits == 0.
2. Known-vulnerabilities panel gets its own "View reports" button, shown only when
   there are unfixed cases, opening the SAME reports modal.
3. Known-vulns wtag reads `regression()` for consistency.
4. Live-agent-activity timestamp column widens by 30px (68 -> 98).
5. Resilience-trend sub line labels each version's rate with a percent sign.
6. Resilience-trend shows a pip on every datapoint, not just the endpoint.
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 100})
    return render_html(build_state(Observability(s)))


# --------------------------------------------------------------------------- #
# (1) exploits button visibility
# --------------------------------------------------------------------------- #
def test_exploits_report_button_toggled_by_report_availability():
    html = _html()
    assert 'id="view-reports"' in html
    # ticket 070: renderKpis shows it based on report availability (k.reports > 0),
    # not the run's exploit count — so a partial-only run with reports still surfaces it.
    assert re.search(r'\.hidden\s*=\s*!\(\s*k\.reports\s*>\s*0\s*\)', html)


# --------------------------------------------------------------------------- #
# (2) known-vulns report button
# --------------------------------------------------------------------------- #
def test_known_vulns_report_button_exists_hidden_and_toggled():
    html = _html()
    # a distinct button lives in the known-vulns panel, initially hidden
    assert re.search(r'id="view-reports-kv"[^>]*hidden', html)
    # renderKnownVulns ties its visibility to the unfixed (vulnerable) count
    assert re.search(r'\.hidden\s*=\s*!\(+\s*kv\.vulnerable', html)


def test_both_report_buttons_open_the_same_modal():
    html = _html()
    # both buttons wire their click to openReports
    assert len(re.findall(r'addEventListener\("click",\s*openReports\)', html)) >= 2
    assert html.count("view-reports-kv") >= 3  # button html + render toggle + wire


# --------------------------------------------------------------------------- #
# (3) wtag consistency
# --------------------------------------------------------------------------- #
def test_known_vulns_wtag_is_regression_call():
    html = _html()
    assert '<span class="wtag">regression()</span>' in html
    assert '<span class="wtag">regression</span>' not in html


# --------------------------------------------------------------------------- #
# (4) feed timestamp column width
# --------------------------------------------------------------------------- #
def test_feed_timestamp_column_widened_by_30px():
    html = _html()
    assert re.search(r'\.feedrow \{[^}]*grid-template-columns:\s*38px\s+98px\s+108px\s+1fr\s+auto',
                     html)
    assert "38px 68px 108px" not in html  # the old width is gone


# --------------------------------------------------------------------------- #
# (5) trend sub percent label
# --------------------------------------------------------------------------- #
def test_trend_sub_appends_percent_sign():
    html = _html()
    assert re.search(r'pct\(p\.pass_rate\)\s*\+\s*"%"', html)


# --------------------------------------------------------------------------- #
# (6) a pip on every trend datapoint
# --------------------------------------------------------------------------- #
def test_trend_pip_per_datapoint():
    html = _html()
    # a dedicated group holds the per-point pips
    assert 'id="trend-dots"' in html
    assert re.search(r'getElementById\("trend-dots"\)', html)
    # renderTrend builds a circle per point from the pts array
    assert re.search(r'pts\.map\([\s\S]{0,200}<circle', html)
