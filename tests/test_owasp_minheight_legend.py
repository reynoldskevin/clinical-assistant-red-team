"""Ticket 057 — OWASP panel min-height + legend agent grouping.

The honest (053) OWASP heat map is empty until a run populates it, so the panel
needs a min-height floor to keep the dual-row layout from collapsing. And the
Documentation chip moves left of Regression so the agents group together.
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 100})
    return render_html(build_state(Observability(s)))


def test_owasp_heat_has_min_height():
    html = _html()
    assert re.search(r"#owasp-heat\s*\{[^}]*min-height:\s*300px", html), \
        "#owasp-heat needs a 300px min-height floor"


def test_documentation_chip_precedes_regression_in_legend():
    html = _html()
    doc = html.index('<span class="agentchip doc">documentation</span>')
    reg = html.index('<span class="agentchip reg">regression</span>')
    assert doc < reg, "documentation chip should sit to the left of regression"
