"""Ticket 041 — AI-use disclosure (fuller writeup + drifting-judge detection).

Locked acceptance tests for the standalone `AI_USE_DISCLOSURE.md`: every AI role
disclosed with its verification and residual risk, and an explicit drift
detect-and-correct procedure wired to the calibration mechanism.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "AI_USE_DISCLOSURE.md"

ROLES = ["Red Team", "Judge", "Orchestrator", "Documentation"]
CHECK_KEYWORDS = ("deterministic", "human", "invariant", "calibration", "budget", "data-quality", "judge")


def _text() -> str:
    assert DOC.exists(), "AI_USE_DISCLOSURE.md missing at repo root"
    return DOC.read_text()


def test_document_present_and_substantive() -> None:
    assert len(_text()) > 1200, "disclosure is too thin to be a real deliverable"


def test_every_ai_role_disclosed_with_a_check() -> None:
    lines = _text().splitlines()
    for role in ROLES:
        role_lines = [ln for ln in lines if role.lower() in ln.lower()]
        assert role_lines, f"AI role {role} not disclosed"
        assert any(
            any(kw in ln.lower() for kw in CHECK_KEYWORDS) for ln in role_lines
        ), f"role {role} has no deterministic/human check on its line"


def test_residual_risk_section_present() -> None:
    low = _text().lower()
    assert "residual risk" in low or "remaining risk" in low
    # The brief asks specifically what was independently verified vs still risky.
    assert "verif" in low


def test_drifting_judge_detect_and_correct_procedure() -> None:
    low = _text().lower()
    assert "drift" in low, "no drift discussion"
    assert "calibration" in low, "drift procedure must reference the calibration mechanism"
    # Both halves of the procedure: detection AND correction.
    assert any(k in low for k in ("detect", "detection")), "no drift DETECTION described"
    assert any(k in low for k in ("correct", "recalibrat", "remediat", "roll back", "rollback")), \
        "no drift CORRECTION described"


def test_names_the_calibration_fixtures_or_invariant() -> None:
    low = _text().lower()
    # Ties to the real platform mechanism (028 / judge calibration set + invariant).
    assert any(k in low for k in ("calibration set", "calibration_fixtures", "frozen", "invariant"))
