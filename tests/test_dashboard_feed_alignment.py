"""Ticket 048 — live agent feed alignment polish.

The timestamp gets horizontal padding, and the agent-type chip sits in a
fixed-width column (chip fills it) so every row's label lines up.
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 100})
    return render_html(build_state(Observability(s)))


def test_timestamp_has_padding():
    html = _html()
    assert re.search(r"\.feedrow \.ts \{[^}]*padding:", html), "feed timestamp needs padding"


def test_agent_chip_is_fixed_width_and_aligned():
    html = _html()
    # the agent-chip grid column is a fixed width (not auto) so labels line up
    assert re.search(r"\.feedrow \{[^}]*grid-template-columns:[^;]*\b108px\b", html)
    # the chip fills that fixed column so every pip is the same width
    assert re.search(r"\.feedrow \.agentchip \{[^}]*width:\s*100%", html)
    assert re.search(r"\.feedrow \.agentchip \{[^}]*text-align:\s*center", html)
