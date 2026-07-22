"""Ticket 037 — Build-vs-configure decision record.

Locked acceptance tests for the standalone `DECISION_RECORD_BUILD_VS_CONFIGURE.md`
deliverable: every reviewer-named tool is evaluated (coverage + shortfall), and
each agent role carries an explicit build-vs-configure verdict.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "DECISION_RECORD_BUILD_VS_CONFIGURE.md"

TOOLS = ["Burp", "ZAP", "Semgrep", "Garak"]
ROLES = ["Red Team", "Judge", "Orchestrator", "Documentation"]


def _text() -> str:
    assert DOC.exists(), "DECISION_RECORD_BUILD_VS_CONFIGURE.md missing at repo root"
    return DOC.read_text()


def test_document_present_and_substantive() -> None:
    text = _text()
    assert len(text) > 1200, "decision record is too thin to be a real deliverable"


def test_named_tools_are_evaluated() -> None:
    low = _text().lower()
    for tool in TOOLS:
        assert tool.lower() in low, f"{tool} not evaluated"
    assert "commercial" in low, "commercial red-team platforms not addressed"
    # Coverage + shortfall language present (the brief demands both).
    assert "cover" in low, "no discussion of what tools cover"
    assert any(s in low for s in ("falls short", "fall short", "shortfall", "shortcoming")), \
        "no discussion of where tools fall short"


def test_each_agent_role_has_a_build_or_configure_verdict() -> None:
    lines = _text().splitlines()
    for role in ROLES:
        role_lines = [ln for ln in lines if role.lower() in ln.lower()]
        assert role_lines, f"role {role} not mentioned"
        assert any(re.search(r"\b(build|configure)\b", ln, re.I) for ln in role_lines), \
            f"role {role} has no build/configure verdict on its line"


def test_justifies_custom_over_configuring_a_tool() -> None:
    low = _text().lower()
    assert "custom agent" in low
    # The core justification: adaptive / multi-turn / LLM-judged work off-the-shelf
    # scanners don't do.
    assert any(k in low for k in ("adaptive", "multi-turn", "multi turn", "llm-judged", "judged"))
