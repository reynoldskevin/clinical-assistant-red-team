"""Acceptance tests for ticket 008 — Seed eval dataset (>=3 categories, OWASP-mapped).

These tests are the FIXED contract for the seed eval suite + loader. They pin:
- `from forge.evals import EvalCase, load_cases, EvalCaseError`
- `EvalCase` — the case schema: category (+ optional subcategory), a prompt OR an input
  sequence, expected (safe) behavior, an observed_behavior slot for a run to fill, severity,
  add_to_regression flag, and a REQUIRED OWASP mapping (`owasp_web` and/or `owasp_llm`
  non-empty). Invalid cases (no OWASP mapping / no prompt-or-sequence / bad severity) are rejected.
- `load_cases(evals_dir=None) -> list[EvalCase]` — reads every case under `./evals/` (default),
  validating each; raises `EvalCaseError` on an invalid case file. A file may hold one case
  (object) or many (list).
- The real seed suite has >=3 distinct attack categories.
"""

import json

import pytest

from forge.evals import EvalCase, EvalCaseError, load_cases

_VALID_SEVERITIES = {"critical", "high", "medium", "low"}


# --- the real seed suite ---------------------------------------------------

def test_imports():
    from forge.evals import EvalCase, EvalCaseError, load_cases  # noqa: F401


def test_seed_suite_has_at_least_three_categories():
    cases = load_cases()
    categories = {c.category for c in cases}
    assert len(categories) >= 3, f"only {len(categories)} categories: {categories}"


def test_loader_returns_all_cases_and_they_are_evalcases():
    cases = load_cases()
    assert len(cases) >= 3
    assert all(isinstance(c, EvalCase) for c in cases)
    # ids are unique across the seed suite
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), f"duplicate case ids: {ids}"


def test_every_seed_case_is_schema_valid_with_required_owasp_mapping():
    for c in load_cases():
        assert c.id and c.category
        assert (c.prompt is not None) or bool(c.input_sequence), \
            f"case {c.id} has neither prompt nor input_sequence"
        assert c.expected_behavior.strip() != ""
        assert c.severity in _VALID_SEVERITIES
        assert isinstance(c.add_to_regression, bool)
        # observed_behavior is a slot a run fills in later
        assert hasattr(c, "observed_behavior")
        # REQUIRED OWASP mapping: at least one taxonomy is populated
        assert c.owasp_web or c.owasp_llm, f"case {c.id} has no OWASP mapping"
        assert c.schema_version == "v1"


# --- schema validation (unit) ----------------------------------------------

def test_case_requires_owasp_mapping():
    with pytest.raises(Exception):
        EvalCase(
            id="x",
            category="prompt_injection",
            prompt="do bad thing",
            expected_behavior="refuse",
            severity="high",
        )  # no owasp_web / owasp_llm


def test_case_requires_prompt_or_input_sequence():
    with pytest.raises(Exception):
        EvalCase(
            id="x",
            category="prompt_injection",
            expected_behavior="refuse",
            severity="low",
            owasp_web=["A03:2021-Injection"],
            owasp_llm=["LLM01:Prompt Injection"],
        )  # neither prompt nor input_sequence


def test_case_rejects_invalid_severity():
    with pytest.raises(Exception):
        EvalCase(
            id="x",
            category="prompt_injection",
            prompt="p",
            expected_behavior="refuse",
            severity="catastrophic",
            owasp_web=["A03:2021-Injection"],
            owasp_llm=[],
        )


def test_input_sequence_case_is_valid():
    c = EvalCase(
        id="seq1",
        category="prompt_injection",
        input_sequence=["turn one", "turn two"],
        expected_behavior="refuse across turns",
        severity="high",
        owasp_web=[],
        owasp_llm=["LLM01:Prompt Injection"],
    )
    assert c.input_sequence == ["turn one", "turn two"]
    assert c.prompt is None


# --- loader behavior -------------------------------------------------------

def test_loader_rejects_invalid_case_file(tmp_path):
    bad = {
        "id": "bad",
        "category": "prompt_injection",
        "prompt": "p",
        "expected_behavior": "refuse",
        "severity": "high",
        # missing OWASP mapping
    }
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    with pytest.raises(EvalCaseError):
        load_cases(tmp_path)


def test_loader_reads_one_or_many_cases_per_file(tmp_path):
    pair = [
        {
            "id": "a",
            "category": "prompt_injection",
            "prompt": "p1",
            "expected_behavior": "refuse",
            "severity": "high",
            "owasp_web": ["A03:2021-Injection"],
            "owasp_llm": ["LLM01:Prompt Injection"],
        },
        {
            "id": "b",
            "category": "data_exfiltration",
            "prompt": "p2",
            "expected_behavior": "refuse",
            "severity": "critical",
            "owasp_web": ["A01:2021-Broken Access Control"],
            "owasp_llm": ["LLM06:Sensitive Information Disclosure"],
        },
    ]
    single = {
        "id": "c",
        "category": "identity_exploitation",
        "prompt": "p3",
        "expected_behavior": "refuse",
        "severity": "high",
        "owasp_web": ["A01:2021-Broken Access Control"],
        "owasp_llm": ["LLM06:Sensitive Information Disclosure"],
    }
    (tmp_path / "pair.json").write_text(json.dumps(pair))
    (tmp_path / "single.json").write_text(json.dumps(single))
    cases = load_cases(tmp_path)
    assert {c.id for c in cases} == {"a", "b", "c"}
