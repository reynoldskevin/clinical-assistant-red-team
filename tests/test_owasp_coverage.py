"""Ticket 019 — OWASP coverage completion.

Locked acceptance tests: every mandated OWASP Web Top 10 and LLM Top 10 entry
relevant to the Co-Pilot must have at least one mapped eval case, and the
coverage report must FAIL (surface a missing entry) if any mandated entry drops
to zero cases.
"""

from __future__ import annotations

import pytest

from forge.evals import load_cases
from forge.owasp import (
    MANDATED_LLM,
    MANDATED_WEB,
    coverage_report,
)


# The four entries that closed the historical gaps — the suite MUST cover these.
_GAP_WEB = {
    "A06:2021-Vulnerable and Outdated Components",
    "A09:2021-Security Logging and Monitoring Failures",
}
_GAP_LLM = {
    "LLM02:Insecure Output Handling",
    "LLM05:Supply Chain Vulnerabilities",
}


def test_mandated_sets_are_canonical() -> None:
    assert MANDATED_WEB, "mandated Web set must be non-empty"
    assert MANDATED_LLM, "mandated LLM set must be non-empty"
    assert all(isinstance(x, str) and x for x in MANDATED_WEB)
    assert all(isinstance(x, str) and x for x in MANDATED_LLM)
    assert all(x.startswith("A") and ":2021-" in x for x in MANDATED_WEB)
    assert all(x.startswith("LLM") for x in MANDATED_LLM)
    # No duplicates.
    assert len(set(MANDATED_WEB)) == len(MANDATED_WEB)
    assert len(set(MANDATED_LLM)) == len(MANDATED_LLM)
    # The historically-missing entries are part of the mandate.
    assert _GAP_WEB <= set(MANDATED_WEB)
    assert _GAP_LLM <= set(MANDATED_LLM)


def test_seed_suite_has_full_coverage() -> None:
    report = coverage_report(load_cases())
    assert report.missing == [], f"uncovered mandated entries: {report.missing}"
    assert report.is_complete is True


def test_report_is_scoped_to_the_mandated_entries() -> None:
    report = coverage_report(load_cases())
    assert set(report.web) == set(MANDATED_WEB)
    assert set(report.llm) == set(MANDATED_LLM)


def test_every_mandated_entry_maps_to_a_real_case() -> None:
    cases = load_cases()
    for label in MANDATED_WEB:
        assert any(label in c.owasp_web for c in cases), f"no case maps {label}"
    for label in MANDATED_LLM:
        assert any(label in c.owasp_llm for c in cases), f"no case maps {label}"


def test_coverage_counts_are_positive() -> None:
    report = coverage_report(load_cases())
    assert all(v >= 1 for v in report.web.values())
    assert all(v >= 1 for v in report.llm.values())


@pytest.mark.parametrize("label", sorted(MANDATED_WEB))
def test_dropping_a_web_entry_is_detected(label: str) -> None:
    cases = load_cases()
    # Strip the entry from every case that maps it → that mandated entry now
    # has zero coverage and MUST be reported missing.
    stripped = [
        c.model_copy(update={"owasp_web": [w for w in c.owasp_web if w != label]})
        for c in cases
    ]
    report = coverage_report(stripped)
    assert label in report.missing
    assert report.is_complete is False


@pytest.mark.parametrize("label", sorted(MANDATED_LLM))
def test_dropping_an_llm_entry_is_detected(label: str) -> None:
    cases = load_cases()
    stripped = [
        c.model_copy(update={"owasp_llm": [l for l in c.owasp_llm if l != label]})
        for c in cases
    ]
    report = coverage_report(stripped)
    assert label in report.missing
    assert report.is_complete is False
