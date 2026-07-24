"""Acceptance test for ticket 073 — resilience-trend delta relative to the previous run.

The delta chip must compare the current version to the PREVIOUS run (trend[n-2]), not the first
version (trend[0]), and show nothing when there's only one run.
"""

import re

from forge.dashboard import build_state, render_html
from forge.observability import Observability
from forge.store import Store


def _html():
    return render_html(build_state(Observability(Store(":memory:"))))


def test_trend_delta_is_relative_to_previous_run():
    html = _html()
    # delta = current minus PREVIOUS run
    assert re.search(
        r"pct\(trend\[n - 1\]\.pass_rate\)\s*-\s*pct\(trend\[n - 2\]\.pass_rate\)", html
    )
    # the old first-version baseline delta is gone
    assert not re.search(r"-\s*pct\(trend\[0\]\.pass_rate\)", html)


def test_trend_delta_guarded_for_single_run():
    html = _html()
    # a guard so no delta is computed/shown when there's no previous run
    assert re.search(r"if\s*\(\s*n >= 2\s*\)", html)
