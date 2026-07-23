"""Dashboard vulnerability-reports modal: `load_reports`, the `/api/reports`
route, end-to-end serving, and the header button + modal markup.
"""

import json
import threading
import urllib.request

from forge.store import Store
from forge.dashboard import (
    build_state,
    handle_path,
    load_reports,
    make_server,
    render_html,
)
from forge.observability import Observability


def _write_reports(tmp_path):
    (tmp_path / "VULN-a.json").write_text(json.dumps(
        {"id": "VULN-a", "severity": "high", "description": "d"}))
    (tmp_path / "VULN-b.json").write_text(json.dumps(
        {"id": "VULN-b", "severity": "critical", "description": "e"}))
    return tmp_path


# --------------------------------------------------------------------------- #
# load_reports
# --------------------------------------------------------------------------- #
def test_load_reports_reads_dir(tmp_path):
    _write_reports(tmp_path)
    reports = load_reports(str(tmp_path))
    assert len(reports) == 2
    ids = {r["id"] for r in reports}
    assert ids == {"VULN-a", "VULN-b"}
    for r in reports:
        assert set(("id", "filename", "modified", "content")) <= set(r)
        assert isinstance(r["modified"], float)
        assert r["content"]["id"] == r["id"]
    # JSON-serializable wire payload
    assert json.loads(json.dumps(reports)) == reports


def test_load_reports_missing_dir_is_empty(tmp_path):
    assert load_reports(str(tmp_path / "nope")) == []


def test_load_reports_id_falls_back_to_filename(tmp_path):
    (tmp_path / "orphan.json").write_text(json.dumps({"severity": "low"}))
    reports = load_reports(str(tmp_path))
    assert reports[0]["id"] == "orphan"


def test_load_reports_flags_bad_json(tmp_path):
    (tmp_path / "broken.json").write_text("{not json")
    reports = load_reports(str(tmp_path))
    assert reports[0]["content"] is None
    assert "error" in reports[0]


def test_load_reports_sorted_newest_first(tmp_path):
    import os
    a = tmp_path / "a.json"; a.write_text(json.dumps({"id": "a"}))
    b = tmp_path / "b.json"; b.write_text(json.dumps({"id": "b"}))
    os.utime(a, (1000, 1000))
    os.utime(b, (2000, 2000))
    reports = load_reports(str(tmp_path))
    assert [r["id"] for r in reports] == ["b", "a"]


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #
def test_handle_path_reports_route_uses_provider():
    payload = [{"id": "VULN-x", "filename": "VULN-x.json", "modified": 1.0, "content": {"id": "VULN-x"}}]
    status, ctype, body = handle_path("/api/reports?ts=1", lambda: {}, lambda: payload)
    assert status == 200
    assert ctype == "application/json"
    assert json.loads(body) == {"reports": payload}


def test_handle_path_reports_empty_without_provider():
    status, _, body = handle_path("/api/reports", lambda: {})
    assert status == 200
    assert json.loads(body) == {"reports": []}


# --------------------------------------------------------------------------- #
# end-to-end
# --------------------------------------------------------------------------- #
def test_make_server_serves_reports(tmp_path):
    _write_reports(tmp_path)
    server = make_server(Store(":memory:"), host="127.0.0.1", port=0, reports_dir=str(tmp_path))
    host, port = server.server_address[0], server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/reports", timeout=5) as r:
            assert r.status == 200
            data = json.loads(r.read().decode("utf-8"))
        assert {rep["id"] for rep in data["reports"]} == {"VULN-a", "VULN-b"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --------------------------------------------------------------------------- #
# frontend structure
# --------------------------------------------------------------------------- #
def test_exploits_box_has_view_reports_button():
    html = render_html(build_state(Observability(Store(":memory:"))))
    # button lives inside the Exploits KPI widget
    assert 'id="view-reports"' in html
    assert "View reports" in html
    i_exploit = html.find('id="kpi-exploits"')
    i_btn = html.find('id="view-reports"')
    assert -1 < i_exploit < i_btn


def test_reports_modal_and_client_wiring_present():
    html = render_html(build_state(Observability(Store(":memory:"))))
    assert 'id="reports-modal"' in html
    assert 'id="reports-accordion"' in html
    assert 'id="reports-close"' in html
    assert "/api/reports" in html          # the button fetches the endpoint
    assert "syntaxHighlight" in html        # read-only JSON viewer
    assert "downloadFile" in html           # per-report download
    assert 'role="dialog"' in html
