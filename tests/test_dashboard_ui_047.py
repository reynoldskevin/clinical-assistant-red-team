"""Ticket 047 — dashboard UI refinements.

1. Start-run button shows a disabled spinner from click until the run is live.
2. Live agent feed scrolls, shows ALL of this run's activity, colour-codes the
   regression + documentation steps (grey, in the key, not clipped), and shows a
   timestamp after each step's hash id.
3. Known vulnerabilities panel mirrors the Current-run-findings three-box layout:
   Known (blue) / Unfixed (red) / Fixed (green); no summary line, no case list.
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
# item 2 — backend: timestamps + step labels
# --------------------------------------------------------------------------- #
def test_append_event_stamps_ts():
    s = Store(":memory:")
    eid = s.append_event({"kind": "attack", "category": "pi"})
    ev = next(e for e in s.get_events() if e["id"] == eid)
    assert isinstance(ev.get("ts"), (int, float)) and ev["ts"] > 0


def test_append_event_preserves_explicit_ts():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "ts": 12345.0})
    ev = s.get_events()[0]
    assert ev["ts"] == 12345.0


def test_agent_activity_carries_ts_and_labels_steps():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1"})
    s.append_event({"kind": "regression_result", "case_id": "a", "category": "dos", "status": "fixed"})
    s.append_event({"kind": "vuln_report", "report_id": "R1"})
    s.append_event({"kind": "vuln_report_link", "report_id": "R1", "case_id": "a"})
    act = Observability(s).agent_activity()

    assert all("ts" in a for a in act)
    by_kind = {a["kind"]: a["agent"] for a in act}
    assert by_kind["regression_result"] == "regression"
    assert by_kind["vuln_report"] == "documentation"
    assert by_kind["vuln_report_link"] == "documentation"


# --------------------------------------------------------------------------- #
# item 1 — start button spinner
# --------------------------------------------------------------------------- #
def test_start_button_has_busy_spinner():
    html = _html()
    assert re.search(r"\.startbtn\.busy", html)      # a busy/disabled visual state
    assert "@keyframes spin" in html                  # the spinner animation
    assert "pendingStart" in html                     # JS tracks the pending-start state


# --------------------------------------------------------------------------- #
# item 2 — feed: scroll, key chips, timestamps, no cap
# --------------------------------------------------------------------------- #
def test_feed_scrolls_and_labels_regression_and_documentation():
    html = _html()
    # the feed container scrolls (its own rule carries overflow-y:auto)
    assert re.search(r"\.feed \{[^}]*overflow-y:\s*auto", html)
    # regression + documentation appear as grey chips in the legend/key
    assert '<span class="agentchip reg">regression</span>' in html
    assert '<span class="agentchip doc">documentation</span>' in html
    # both grey chip classes styled
    assert re.search(r"\.agentchip\.reg", html) and re.search(r"\.agentchip\.doc", html)


def test_feed_shows_timestamp_and_no_fixed_cap():
    html = _html()
    assert "toLocaleTimeString" in html          # a per-row timestamp is formatted
    assert ".slice(0, 8)" not in html            # the old top-8 cap is gone


# --------------------------------------------------------------------------- #
# item 3 — known vulnerabilities as three boxes
# --------------------------------------------------------------------------- #
def test_known_vulns_uses_three_box_pipe():
    html = _html()
    # a Known (blue/accent) stage variant exists
    assert re.search(r"\.stage\.known", html)
    # the three box labels are rendered by the known-vulns renderer
    assert ">Known<" in html
    assert ">Unfixed<" in html
    assert ">Fixed<" in html
    # the panel container is the pipe (id preserved)
    assert 'id="known-vulns"' in html


def test_known_vulns_summary_and_list_removed():
    html = _html()
    assert "still vulnerable" not in html   # the "N of M still vulnerable" line is gone
    assert "kv-row" not in html             # the per-case list is gone
