"""Ticket 056 — hide adapter rows in the feed, colour documentation green.

Adapter (target_call) rows carry no signal, so the feed filters them out. Adapter
previously owned the green accent; since it's now hidden, the green goes to the
Documentation agent (a real agent). Regression stays grey.
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 100})
    return render_html(build_state(Observability(s)))


def test_feed_filters_out_adapter_rows():
    html = _html()
    assert re.search(r'ev\.agent\s*!==\s*"adapter"', html), \
        "renderFeed must drop adapter activity rows"


def test_documentation_chip_is_green():
    html = _html()
    m = re.search(r"\.agentchip\.doc \{([^}]*)\}", html)
    assert m, "missing .agentchip.doc rule"
    assert "var(--good)" in m.group(1), "documentation chip should use the green accent"


def test_regression_chip_stays_grey():
    html = _html()
    m = re.search(r"\.agentchip\.reg \{([^}]*)\}", html)
    assert m and "var(--muted)" in m.group(1), "regression chip should stay grey"


def test_adapter_removed_from_legend_documentation_kept():
    html = _html()
    assert '<span class="agentchip adp">adapter</span>' not in html, \
        "adapter chip should be gone from the legend"
    assert '<span class="agentchip doc">documentation</span>' in html, \
        "documentation chip stays in the legend"
