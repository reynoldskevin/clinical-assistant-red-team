"""Acceptance tests for ticket 019b — seed corpus depth >=10 cases per category.

Reviewer feedback closed here: the live corpus was thin because the seed suite was
thin (2-3 cases/category). This pins a floor of >=10 distinct, OWASP-mapped,
schema-valid cases per category so a single live `forge run --suite` yields >=10
attempts/category, and it pins the Orchestrator's coverage-sufficiency default to
match that bar.
"""

from collections import Counter

from forge.evals import EvalCase, load_cases
from forge.observability import Observability
from forge.orchestrator import Orchestrator
from forge.store import Store

MIN_PER_CATEGORY = 10


def _by_category():
    cases = load_cases()
    buckets = {}
    for c in cases:
        buckets.setdefault(c.category, []).append(c)
    return cases, buckets


def test_every_category_has_at_least_ten_cases():
    _, buckets = _by_category()
    thin = {cat: len(v) for cat, v in buckets.items() if len(v) < MIN_PER_CATEGORY}
    assert not thin, f"categories below the >=10 floor: {thin}"


def test_total_corpus_is_at_least_sixty():
    cases, _ = _by_category()
    assert len(cases) >= 60, f"corpus is only {len(cases)} cases"


def test_all_case_ids_globally_unique():
    cases, _ = _by_category()
    ids = [c.id for c in cases]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    assert not dupes, f"duplicate case ids: {dupes}"


def test_every_case_schema_valid_with_owasp_mapping():
    cases, _ = _by_category()
    for c in cases:
        assert isinstance(c, EvalCase)
        assert c.id and c.category
        assert (c.prompt and c.prompt.strip()) or c.input_sequence, f"{c.id}: no prompt/sequence"
        assert c.expected_behavior.strip(), f"{c.id}: empty expected_behavior"
        assert c.severity in {"critical", "high", "medium", "low"}
        assert c.owasp_web or c.owasp_llm, f"{c.id}: no OWASP mapping"


def test_prompts_within_a_category_are_distinct():
    """Depth must be real variety, not the same probe copied ten times."""
    _, buckets = _by_category()
    for cat, cases in buckets.items():
        texts = [
            (c.prompt or " ".join(c.input_sequence or [])).strip().lower()
            for c in cases
        ]
        assert len(set(texts)) == len(texts), f"{cat} has duplicate prompts"


def test_orchestrator_coverage_target_defaults_to_ten():
    orch = Orchestrator(Observability(Store(":memory:")), categories=["prompt_injection"])
    assert orch.coverage_target == MIN_PER_CATEGORY, (
        "the coverage-sufficiency default must match the >=10-per-category bar"
    )
