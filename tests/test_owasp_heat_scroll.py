"""Acceptance test for ticket 071 — OWASP coverage panel max-height + scroll.

`#owasp-heat` caps at 600px and scrolls vertical overflow, keeping the 300px min-height (057).
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    return render_html(build_state(Observability(Store(":memory:"))))


def test_owasp_heat_caps_height_and_scrolls():
    html = _html()
    m = re.search(r"#owasp-heat\s*\{([^}]*)\}", html)
    assert m, "#owasp-heat rule must exist"
    body = m.group(1)
    assert re.search(r"max-height:\s*600px", body)
    assert re.search(r"overflow-y:\s*auto", body)
    assert re.search(r"min-height:\s*300px", body)  # 057 preserved
