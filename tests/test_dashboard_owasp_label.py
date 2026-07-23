"""Acceptance tests for ticket 033 — third row back to 5/3/4 + wider OWASP
coverage label column (200px)."""

import re

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import build_state, render_html


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start"})
    return render_html(build_state(Observability(s)))


def test_row2_spans_are_5_4_3():
    # Redesign row 2: Pass/fail (5) · Resilience trend (4) · Cost (3).
    html = _html()
    assert re.search(r'class="w c5">\s*<div class="whead"><span class="wt">Pass / fail by category', html)
    assert re.search(r'class="w c4">\s*<div class="whead"><span class="wt">Resilience trend', html)
    assert re.search(r'class="w c3">\s*<div class="whead"><span class="wt">Cost', html)


def test_row3_dual_row_layout():
    # Redesign (ticket 043): row 3 is a dual-row — OWASP coverage (left, full height)
    # beside a right column stacking "Current run findings" over "Known vulnerabilities".
    html = _html()
    assert "dualrow" in html
    assert 'class="rightcol"' in html
    assert re.search(r'class="w owasp">\s*<div class="whead"><span class="wt">OWASP coverage', html)
    assert re.search(r'<span class="wt">Current run findings', html)
    assert re.search(r'<span class="wt">Known vulnerabilities', html)


def test_owasp_label_column_is_400px():
    html = _html()
    assert "grid-template-columns: 400px 1fr 35px" in html
    assert "300px 1fr 35px" not in html
