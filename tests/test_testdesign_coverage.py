"""Ticket 042 — Test-design coverage matrix.

Locked acceptance tests. Every eval case must exercise a boundary, an invariant,
or a regression risk (brief #1); a coverage report fails if any of the three
classes is unrepresented. An explicit `test_design` tag overrides derivation.
"""

from __future__ import annotations

from forge.evals import load_cases
from forge.testdesign import CLASSES, classify, coverage_report


class _FakeCase:
    """Duck-typed stand-in exposing the attributes `classify` may read."""

    def __init__(self, test_design=None, **kw) -> None:
        if test_design is not None:
            self.test_design = test_design
        self.add_to_regression = kw.get("add_to_regression", False)
        self.category = kw.get("category", "prompt_injection")
        self.subcategory = kw.get("subcategory")
        self.prompt = kw.get("prompt", "attack text")
        self.input_sequence = kw.get("input_sequence")
        self.severity = kw.get("severity", "high")
        self.expected_behavior = kw.get("expected_behavior", "refuse")


def test_classes_are_the_three_mandated() -> None:
    assert set(CLASSES) == {"boundary", "invariant", "regression"}


def test_every_case_exercises_at_least_one_class() -> None:
    for case in load_cases():
        cls = classify(case)
        assert cls, f"{case.id} exercises no boundary/invariant/regression class"
        assert set(cls) <= set(CLASSES), f"{case.id} has an unknown class {cls}"


def test_corpus_covers_all_three_classes() -> None:
    report = coverage_report(load_cases())
    assert report.missing == [], f"unrepresented test-design classes: {report.missing}"
    assert report.is_complete is True
    assert all(report.counts[c] >= 1 for c in CLASSES)


def test_each_class_maps_to_a_real_case() -> None:
    cases = load_cases()
    for cls in CLASSES:
        assert any(cls in classify(c) for c in cases), f"no case exercises {cls}"


def test_explicit_tag_overrides_derivation() -> None:
    # A regression-flagged DoS case would derive {boundary, regression}, but an
    # explicit tag pins it.
    case = _FakeCase(test_design=["invariant"], add_to_regression=True,
                     category="denial_of_service", subcategory="unbounded_generation")
    assert set(classify(case)) == {"invariant"}


def test_missing_class_is_flagged() -> None:
    # Explicit tags covering only boundary + regression → invariant unrepresented.
    cases = [_FakeCase(test_design=["boundary"]), _FakeCase(test_design=["regression"])]
    report = coverage_report(cases)
    assert "invariant" in report.missing
    assert report.is_complete is False


def test_derivation_signals() -> None:
    # A regression-flagged case exercises regression risk.
    assert "regression" in classify(_FakeCase(add_to_regression=True))
    # A DoS / unbounded case exercises a boundary.
    assert "boundary" in classify(
        _FakeCase(category="denial_of_service", subcategory="unbounded_generation")
    )
    # Every attack case falls back to the Judge safety invariant.
    plain = _FakeCase(category="prompt_injection", subcategory="direct_override",
                      add_to_regression=False)
    assert classify(plain), "a plain case must still classify (invariant fallback)"
