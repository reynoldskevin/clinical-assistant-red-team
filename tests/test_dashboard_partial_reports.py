"""Acceptance tests for ticket 070 — View-reports button reflects report availability.

A partial-only run (exploits == 0) must still surface the "View reports" button when reports
exist on disk, because the reports modal is not run-scoped. The button is gated on
`kpis.reports` (report availability), not the run's exploit count.
"""

import json
import re
import threading
import urllib.request

from forge.dashboard import build_state, render_html, make_server
from forge.observability import Observability
from forge.store import Store


def _write_reports(tmp_path, n=2):
    for i in range(n):
        (tmp_path / f"VULN-{i}.json").write_text(
            json.dumps({"id": f"VULN-{i}", "severity": "high", "description": "d"})
        )
    return tmp_path


# --------------------------------------------------------------------------- #
# kpis.reports = report availability
# --------------------------------------------------------------------------- #
def test_build_state_exposes_report_count(tmp_path):
    _write_reports(tmp_path, 2)
    state = build_state(Observability(Store(":memory:")), reports_dir=str(tmp_path))
    assert state["kpis"]["reports"] == 2


def test_build_state_report_count_defaults_zero():
    state = build_state(Observability(Store(":memory:")))
    assert state["kpis"]["reports"] == 0


# --------------------------------------------------------------------------- #
# the user scenario: partial-only run, but reports on disk -> button shows
# --------------------------------------------------------------------------- #
def test_partial_only_run_still_surfaces_reports(tmp_path):
    _write_reports(tmp_path, 1)
    s = Store(":memory:")
    s.append_event({"kind": "run_start", "version": "v1.1", "ts": 100})
    s.append_event({"kind": "verdict", "attempt_id": 1, "category": "prompt_injection",
                    "verdict": "partial", "target_version": "v1.1"})
    s.append_event({"kind": "verdict", "attempt_id": 2, "category": "tool_misuse",
                    "verdict": "partial", "target_version": "v1.1"})
    s.append_event({"kind": "run_end"})

    state = build_state(Observability(s), reports_dir=str(tmp_path))
    assert state["kpis"]["exploits"] == 0     # only partials
    assert state["outcomes"]["partial"] == 2
    assert state["kpis"]["reports"] == 1      # ... but a report exists -> button will show


# --------------------------------------------------------------------------- #
# the button is gated on report availability, not exploit count
# --------------------------------------------------------------------------- #
def test_view_reports_button_gated_on_report_availability():
    html = render_html(build_state(Observability(Store(":memory:"))))
    assert 'id="view-reports"' in html
    assert re.search(r'\.hidden\s*=\s*!\(\s*k\.reports\s*>\s*0\s*\)', html)
    # the old exploit-count gate is gone
    assert not re.search(r'view-reports"\)\s*;\s*if \(vr\) vr\.hidden\s*=\s*!\(\s*k\.exploits', html)


# --------------------------------------------------------------------------- #
# e2e: the live server wires the real reports dir into /api/state
# --------------------------------------------------------------------------- #
def test_api_state_reports_count_end_to_end(tmp_path):
    _write_reports(tmp_path, 3)
    server = make_server(Store(":memory:"), host="127.0.0.1", port=0, reports_dir=str(tmp_path))
    host, port = server.server_address[0], server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/state", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        assert data["kpis"]["reports"] == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
