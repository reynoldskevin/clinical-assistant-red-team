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


def test_widget_numbering_sequential_and_unique():
    html = _html()
    for n in ("01", "02", "03", "04", "05", "06"):
        assert html.count('<span class="id">' + n + "</span>") == 1, n


def test_third_row_spans_are_5_3_4():
    html = _html()
    # OWASP = 5, Cost = 3, Findings = 4, each tied to its numbered heading
    assert re.search(r'class="w c5">\s*<div class="whead"><span class="wt"><span class="id">03</span> OWASP coverage', html)
    assert re.search(r'class="w c3">\s*<div class="whead"><span class="wt"><span class="id">04</span> Cost', html)
    assert re.search(r'class="w c4">\s*<div class="whead"><span class="wt"><span class="id">05</span> Findings', html)
