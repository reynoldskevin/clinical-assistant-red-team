"""Acceptance tests for ticket 011 — USERS.md deliverable.

Structure/contract validation: the file exists and documents the users the
platform serves, their workflows, concrete use cases, and an explicit
justification for why automation is the right solution. Content quality is a
human-review concern; these tests pin the structure the submission gate requires.
"""

import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[1] / "USERS.md"

# Required sections: key → accepted heading keywords (case-insensitive, any match).
REQUIRED_SECTIONS = {
    "users": ["user", "persona", "who"],
    "workflows": ["workflow", "how they work", "process"],
    "use_cases": ["use case", "use-case", "scenario"],
    "automation_justification": [
        "why automation",
        "automation",
        "why automate",
        "why a platform",
    ],
}


def _read():
    assert DOC.exists(), "USERS.md must exist at the project root"
    return DOC.read_text(encoding="utf-8")


def _headings(text):
    """All markdown headings (## or ###) as their lower-cased text."""
    return [
        m.group(2).strip().lower()
        for m in re.finditer(r"^(#{2,3})\s+(?!#)(.*)$", text, re.MULTILINE)
    ]


def _has_section(headings, keywords):
    return any(any(k in h for k in keywords) for h in headings)


def test_file_exists_and_nontrivial():
    text = _read()
    assert len(text.split()) > 150, "USERS.md is unexpectedly short"


@pytest.mark.parametrize("key", list(REQUIRED_SECTIONS))
def test_required_section_present(key):
    headings = _headings(_read())
    assert _has_section(headings, REQUIRED_SECTIONS[key]), (
        f"USERS.md missing a section for: {key}"
    )


def test_names_at_least_one_concrete_user_role():
    """The doc must describe an actual user, not just abstract headings."""
    low = _read().lower()
    roles = ["security", "red team", "engineer", "researcher", "operator", "analyst"]
    assert any(r in low for r in roles), "no concrete user role named"


def test_automation_justification_is_argued():
    """The automation section must contain reasoning, not just a heading."""
    text = _read()
    # Grab the body under the automation-justification heading.
    m = re.search(
        r"^#{2,3}\s+(?!#).*(?:why automat|automation|why a platform).*$",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    assert m, "no automation-justification heading found"
    body = text[m.end():]
    nxt = re.search(r"^#{2,3}\s+(?!#)", body, re.MULTILINE)
    if nxt:
        body = body[: nxt.start()]
    assert len(body.split()) > 40, "automation justification is too thin to be an argument"
