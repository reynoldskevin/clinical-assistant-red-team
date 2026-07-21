"""Acceptance tests for ticket 010 — THREAT_MODEL.md deliverable.

Structure/contract validation only: the file exists, opens with a ~500-word
key-findings summary, and documents all six attack categories, each carrying the
four required fields (attack surface, potential impact, exploitation difficulty,
existing defenses) plus an OWASP mapping. Content quality is a human-review
concern; these tests pin the structure the submission gate requires.
"""

import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[1] / "THREAT_MODEL.md"

# Each category: a stable key + the alternative surface-form keywords that may
# appear in its heading. Matching is case-insensitive; any keyword satisfies it.
CATEGORIES = {
    "prompt_injection": ["prompt injection"],
    "data_exfiltration": ["data exfiltration", "exfiltration"],
    "state_corruption": ["state corruption"],
    "tool_misuse": ["tool misuse", "tool abuse"],
    "denial_of_service": ["denial of service", "dos", "denial-of-service"],
    "identity_exploitation": [
        "identity exploitation",
        "identity/role",
        "role exploitation",
        "privilege",
    ],
}

# The four required fields per category (label → accepted surface forms).
REQUIRED_FIELDS = {
    "attack_surface": ["attack surface"],
    "impact": ["impact"],
    "difficulty": ["difficulty", "exploitation difficulty"],
    "defenses": ["defense", "existing defenses", "mitigation"],
}


def _read():
    assert DOC.exists(), "THREAT_MODEL.md must exist at the project root"
    return DOC.read_text(encoding="utf-8")


def _sections(text):
    """Split into ('## heading text', body) blocks keyed by level-2 heading."""
    blocks = {}
    current = None
    buf = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(?!#)(.*)$", line)
        if m:
            if current is not None:
                blocks[current] = "\n".join(buf)
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        blocks[current] = "\n".join(buf)
    return blocks


def _find_section(sections, keywords):
    for heading, body in sections.items():
        low = heading.lower()
        if any(k in low for k in keywords):
            return heading, body
    return None, None


def test_file_exists_and_nontrivial():
    text = _read()
    assert len(text.split()) > 400, "threat model is unexpectedly short"


def test_opens_with_summary_of_key_findings():
    text = _read()
    sections = _sections(text)
    heading, body = _find_section(sections, ["summary", "key findings", "key finding"])
    assert heading is not None, "must have a Summary / Key Findings section"
    # It must be the FIRST level-2 section (the doc opens with it).
    first_heading = next(iter(_sections(text)))
    assert first_heading == heading, "the summary must be the opening section"
    words = len(re.findall(r"\b\w+\b", body))
    assert 400 <= words <= 650, f"summary should be ~500 words, got {words}"


def test_all_six_categories_present():
    sections = _sections(_read())
    for key, keywords in CATEGORIES.items():
        heading, _ = _find_section(sections, keywords)
        assert heading is not None, f"missing category section: {key}"


@pytest.mark.parametrize("key", list(CATEGORIES))
def test_category_carries_required_fields_and_owasp(key):
    sections = _sections(_read())
    _, body = _find_section(sections, CATEGORIES[key])
    assert body is not None, f"missing category section: {key}"
    low = body.lower()
    for field, forms in REQUIRED_FIELDS.items():
        assert any(f in low for f in forms), f"{key} missing field: {field}"
    # OWASP mapping: an explicit OWASP reference with an entry code
    # (LLM Top 10 like LLM01, or Web Top 10 like A01).
    assert "owasp" in low, f"{key} missing OWASP mapping"
    assert re.search(r"\b(llm\d{2}|a\d{2}|api\d{1,2})\b", low), (
        f"{key} OWASP mapping lacks an entry code (e.g. LLM01 / A01)"
    )
