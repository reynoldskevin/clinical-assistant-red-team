"""Acceptance tests for ticket 062 — triage exercise (10 findings + dispositions).

A deterministic `forge.triage` module defines >=10 curated findings spanning
critical/high/medium and at least one false-positive disposition, each with a
justification, and renders `TRIAGE_EXERCISE.md`. Doc and code must not drift.
"""

import pathlib

from forge.triage import triage_findings, render_markdown, DISPOSITIONS


_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_CATEGORIES = {
    "data_exfiltration",
    "denial_of_service",
    "identity_exploitation",
    "prompt_injection",
    "state_corruption",
    "tool_misuse",
}
_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_at_least_ten_findings():
    assert len(triage_findings()) >= 10


def test_severity_and_disposition_vocabularies():
    assert "reject-false-positive" in DISPOSITIONS
    assert len(set(DISPOSITIONS)) >= 3
    for f in triage_findings():
        assert f.severity in _VALID_SEVERITIES
        assert f.disposition in DISPOSITIONS


def test_coverage_of_classes():
    findings = triage_findings()
    severities = {f.severity for f in findings}
    assert {"critical", "high", "medium"} <= severities
    assert any(f.disposition == "reject-false-positive" for f in findings)


def test_every_finding_is_grounded_and_justified():
    ids = set()
    for f in triage_findings():
        assert f.id and f.id not in ids, "ids must be unique and non-empty"
        ids.add(f.id)
        assert f.title and f.title.strip()
        assert f.justification and f.justification.strip()
        assert f.category in _CATEGORIES, f"{f.category} is not a real platform category"


def test_render_is_deterministic_and_matches_the_set():
    a = render_markdown()
    b = render_markdown()
    assert a == b, "render_markdown must be idempotent"
    for f in triage_findings():
        assert f.id in a
        assert f.title in a


def test_doc_written_to_repo_root_and_no_drift():
    path = _ROOT / "TRIAGE_EXERCISE.md"
    assert path.exists(), "TRIAGE_EXERCISE.md must be generated at the repo root"
    text = path.read_text()
    # summary table + per-finding sections
    assert "|" in text
    assert "##" in text
    # doc is regenerated from the code — no drift
    assert text.strip() == render_markdown().strip()
