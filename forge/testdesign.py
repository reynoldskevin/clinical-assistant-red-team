"""Ticket 042 — Test-design coverage matrix.

Brief #1 mandates that every eval case earn its place by exercising a
deliberate *test-design* class rather than padding a static payload list.
The three mandated classes are:

- ``boundary``   — an edge/limit case (unbounded generation, recursion,
  amplification, length/token limits, enumeration, complexity, multi-turn
  sequences, denial-of-service).
- ``invariant``  — the Judge safety invariant: a confirmed exploit must never
  be approved. This is the guaranteed safety net every adversarial case
  exercises, so it also acts as the fallback class.
- ``regression`` — a case pinned into the regression suite to guard against
  a previously-seen failure recurring.

A static list of attack payloads does *not* satisfy brief #1; this module
classifies each case into the classes above and reports whether the corpus
covers all three. An explicit ``test_design`` tag on a case overrides all
derivation.
"""

from __future__ import annotations

from dataclasses import dataclass

CLASSES = ("boundary", "invariant", "regression")

# Lowercased substrings that signal a boundary/edge case.
_BOUNDARY_SIGNALS = (
    "unbounded",
    "recursi",
    "amplif",
    "length",
    "token",
    "enumerat",
    "exhaust",
    "complexity",
    "multi_turn",
    "multi-turn",
)

_INVARIANT_CATEGORIES = {
    "state_corruption",
    "identity_exploitation",
    "data_exfiltration",
    "tool_misuse",
}


def classify(case) -> set[str]:
    """Return the set of test-design classes a case exercises."""
    # 1. Explicit override wins — no derivation.
    test_design = getattr(case, "test_design", None)
    if test_design:
        return set(test_design) & set(CLASSES)

    # 2. Derive from case fields.
    classes: set[str] = set()

    if getattr(case, "add_to_regression", False):
        classes.add("regression")

    category = getattr(case, "category", None)
    subcategory = getattr(case, "subcategory", None) or ""
    prompt = getattr(case, "prompt", None) or ""
    input_sequence = getattr(case, "input_sequence", None)
    text = f"{subcategory} {prompt}".lower()

    is_boundary = (
        category == "denial_of_service"
        or any(sig in text for sig in _BOUNDARY_SIGNALS)
        or (isinstance(input_sequence, list) and len(input_sequence) > 0)
    )
    if is_boundary:
        classes.add("boundary")

    # invariant as safety net: when no boundary/regression signal fired, and
    # additionally for cases asserting a hard safety invariant.
    severity = getattr(case, "severity", None)
    if not classes or severity in {"critical", "high"} or category in _INVARIANT_CATEGORIES:
        classes.add("invariant")

    # Guarantee: never empty for a real attack case.
    if not classes:
        classes.add("invariant")

    return classes


@dataclass
class CoverageReport:
    counts: dict[str, int]
    missing: list[str]
    is_complete: bool


def coverage_report(cases) -> CoverageReport:
    """Report how many cases exercise each test-design class."""
    counts = {c: 0 for c in CLASSES}
    for case in cases:
        case_classes = classify(case)
        for c in CLASSES:
            if c in case_classes:
                counts[c] += 1
    missing = [c for c in CLASSES if counts[c] == 0]
    return CoverageReport(counts=counts, missing=missing, is_complete=not missing)
