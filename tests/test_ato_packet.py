"""Acceptance tests for ticket 063 — ATO-style evidence packet.

Structural test (repo doc-test pattern): the packet has the required sections, a control
catalog with real mappings, cites only artifacts that actually exist on disk, lists >=3
accepted residual risks, and names the platform's agents.
"""

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PACKET = _ROOT / "ATO_EVIDENCE_PACKET.md"


def _text():
    return _PACKET.read_text()


def test_packet_exists():
    assert _PACKET.exists(), "ATO_EVIDENCE_PACKET.md must exist at the repo root"


def test_required_sections_present():
    t = _text()
    for section in (
        "System Description",
        "Trust Boundaries",
        "Control Catalog",
        "Evidence Artifacts",
        "Residual Risks",
        "Authorization Decision",
    ):
        assert section in t, f"missing required section: {section}"


def test_control_catalog_is_a_real_table():
    # a markdown table: header + separator + at least two mapping rows
    table_lines = [ln for ln in _text().splitlines() if ln.strip().startswith("|")]
    assert len(table_lines) >= 5, "control catalog must be a table with multiple mapping rows"


def test_cited_repo_artifacts_all_exist():
    # every backticked repo-relative path (ending .md/.json/.py/.txt or a dir with trailing /)
    # must resolve to an existing file/dir — no dangling citations.
    tokens = set(re.findall(r"`([\w./-]+(?:\.(?:md|json|py|txt)|/))`", _text()))
    assert tokens, "packet must cite concrete evidence artifacts"
    for tok in tokens:
        assert (_ROOT / tok).exists(), f"cited artifact does not exist: {tok}"


def test_at_least_three_accepted_residual_risks():
    # each residual risk carries an explicit acceptance/mitigation statement
    assert _text().count("Acceptance:") >= 3


def test_named_agents_appear():
    t = _text().lower()
    assert "orchestrator" in t
    assert "red team" in t or "red_team" in t
    assert "judge" in t
    assert "documentation" in t
