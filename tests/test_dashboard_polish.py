"""Acceptance tests for ticket 031 — dashboard copy + layout polish.

Removes stale dev-facing copy (the header note + footer), makes the Findings tag
method-call style (`outcomes()`), sets the third row to 5/3/4 spans, and fixes the
widget numbering so 01–06 are sequential and unique.
"""

import re

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import build_state, render_html


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start"})
    return render_html(build_state(Observability(s)))


def test_stale_copy_removed():
    html = _html()
    assert "every tile maps" not in html          # header note gone
    assert "forge serve" not in html.lower()       # stale footer line gone
    assert "polls + re-renders" not in html        # footer gone
    assert 'class="foot"' not in html              # whole footer removed


def test_findings_tag_is_method_call_style():
    html = _html()
    assert '<span class="wtag">outcomes()</span>' in html
    assert '<span class="wtag">outcomes</span>' not in html  # bare form gone


def test_widget_box_numbering_removed():
    # Redesign: the 01–06 box numbering is gone and titles are the accent color.
    html = _html()
    for n in ("01", "02", "03", "04", "05", "06"):
        assert ('<span class="id">' + n + "</span>") not in html, n
    assert '<span class="id">' not in html  # no numbering markers at all
    # widget titles are rendered in the accent color
    assert re.search(r"\.w \.wt \{[^}]*color: var\(--accent\)", html)


def test_third_row_spans():
    # Redesign: row 3 is 8/4 (OWASP coverage / Findings); Cost moved up to row 2.
    # Authoritative assertion lives in tests/test_dashboard_owasp_label.py.
    html = _html()
    assert re.search(r'class="w c8">\s*<div class="whead"><span class="wt">OWASP coverage', html)
    assert re.search(r'class="w c4">\s*<div class="whead"><span class="wt">Findings', html)
