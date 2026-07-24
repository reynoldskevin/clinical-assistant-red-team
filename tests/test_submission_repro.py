"""Acceptance tests for ticket 069 — submission self-check + deterministic repro.

`missing_artifacts()` fails CI if any submission deliverable disappears; `reproduce()` drives the
full four-agent loop against in-process fakes (offline, no API key) with a stable, identical
result across runs — the "deterministic mock re-run".
"""

import os
import pathlib

from forge.submission import REQUIRED_ARTIFACTS, missing_artifacts, reproduce, main

_ROOT = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# artifact-presence check
# --------------------------------------------------------------------------- #
def test_required_artifacts_all_present_in_repo():
    assert REQUIRED_ARTIFACTS  # non-empty manifest
    assert missing_artifacts() == [], "a submission artifact is missing from the repo"


def test_missing_artifacts_detected_in_empty_dir(tmp_path):
    missing = missing_artifacts(root=str(tmp_path))
    assert "THREAT_MODEL.md" in missing
    assert set(missing) == set(REQUIRED_ARTIFACTS)  # nothing exists in an empty dir


# --------------------------------------------------------------------------- #
# deterministic offline repro
# --------------------------------------------------------------------------- #
def test_reproduce_is_deterministic_and_offline(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # must not need a key
    a = reproduce()
    b = reproduce()
    assert a == b, "reproduce() must be deterministic"
    for key in ("attempts", "verdicts", "exploits", "defended", "findings", "passed"):
        assert key in a, f"missing summary key: {key}"


def test_reproduce_defends_and_actually_runs():
    r = reproduce()
    assert r["attempts"] > 0        # the loop actually drove attacks
    assert r["exploits"] == 0       # mock judge defends
    assert r["findings"] == 0
    assert r["passed"] is True


def test_reproduce_does_not_write_repo_reports():
    before = set(p.name for p in (_ROOT / "reports").glob("*.json"))
    reproduce()
    after = set(p.name for p in (_ROOT / "reports").glob("*.json"))
    assert before == after, "reproduce() must not write into the repo reports/ dir"


# --------------------------------------------------------------------------- #
# CLI + README
# --------------------------------------------------------------------------- #
def test_main_check_and_reproduce_return_zero():
    assert main(["--check"]) == 0        # all artifacts present -> success
    assert main(["--reproduce"]) == 0


def test_readme_cites_the_one_command():
    assert "forge.submission" in (_ROOT / "README.md").read_text()
