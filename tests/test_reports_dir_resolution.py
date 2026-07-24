"""Acceptance tests for ticket 065 — persist vuln reports on the Railway volume.

A single `resolve_reports_dir()` helper gives the report WRITER (build_autonomous_runner)
and the dashboard READER (make_server) one volume-aware default so they can't drift, and so a
run on a volume-mounted prod writes reports where they survive a redeploy.
"""

import json
import threading
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from forge.config import resolve_reports_dir
from forge.run import build_autonomous_runner, CostMeter
from forge.store import Store
from forge.dashboard import make_server


# --------------------------------------------------------------------------- #
# resolve_reports_dir precedence
# --------------------------------------------------------------------------- #
def test_explicit_env_wins():
    env = {"FORGE_REPORTS_DIR": "/custom/reports", "RAILWAY_VOLUME_MOUNT_PATH": "/data"}
    assert resolve_reports_dir(env) == "/custom/reports"


def test_volume_default_when_no_explicit():
    env = {"RAILWAY_VOLUME_MOUNT_PATH": "/data"}
    assert resolve_reports_dir(env) == "/data/reports"


def test_plain_default_when_neither_set():
    assert resolve_reports_dir({}) == "reports"


def test_blank_explicit_is_treated_as_unset():
    env = {"FORGE_REPORTS_DIR": "  ", "RAILWAY_VOLUME_MOUNT_PATH": "/data"}
    assert resolve_reports_dir(env) == "/data/reports"


# --------------------------------------------------------------------------- #
# WRITER wiring — build_autonomous_runner
# --------------------------------------------------------------------------- #
def _cases():
    return [SimpleNamespace(category=c, owasp_web=[], owasp_llm=[])
            for c in ("prompt_injection", "data_exfiltration")]


def test_writer_uses_resolved_reports_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    monkeypatch.delenv("FORGE_REPORTS_DIR", raising=False)

    runner = build_autonomous_runner(
        Store(":memory:"),
        red_team=object(), judge=object(), adapter=object(),
        cases=_cases(), cost_meter=CostMeter(), pid=1,
    )
    expected = Path(resolve_reports_dir())  # == tmp_path/"reports"
    assert Path(runner._documentation._reports_dir) == expected
    assert expected == tmp_path / "reports"


# --------------------------------------------------------------------------- #
# READER wiring — make_server default
# --------------------------------------------------------------------------- #
def test_reader_default_resolves_to_volume(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    monkeypatch.delenv("FORGE_REPORTS_DIR", raising=False)
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "VULN-vol.json").write_text(json.dumps({"id": "VULN-vol", "severity": "high"}))

    server = make_server(Store(":memory:"), host="127.0.0.1", port=0, reports_dir=None)
    host, port = server.server_address[0], server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/reports", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        assert {rep["id"] for rep in data["reports"]} == {"VULN-vol"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --------------------------------------------------------------------------- #
# contract — writer dir == reader dir for the same env
# --------------------------------------------------------------------------- #
def test_writer_and_reader_agree(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    monkeypatch.delenv("FORGE_REPORTS_DIR", raising=False)

    runner = build_autonomous_runner(
        Store(":memory:"),
        red_team=object(), judge=object(), adapter=object(),
        cases=_cases(), cost_meter=CostMeter(), pid=1,
    )
    writer_dir = Path(runner._documentation._reports_dir)
    reader_dir = Path(resolve_reports_dir())  # what make_server(reports_dir=None) will use
    assert writer_dir == reader_dir
