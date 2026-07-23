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


def test_row3_spans_are_8_4():
    # Redesign row 3: OWASP coverage (8) · Findings (4).
    html = _html()
    assert re.search(r'class="w c8">\s*<div class="whead"><span class="wt">OWASP coverage', html)
    assert re.search(r'class="w c4">\s*<div class="whead"><span class="wt">Findings', html)


def test_owasp_label_column_is_200px():
    html = _html()
    assert "grid-template-columns: 200px 1fr 34px" in html
    assert "118px 1fr 34px" not in html
