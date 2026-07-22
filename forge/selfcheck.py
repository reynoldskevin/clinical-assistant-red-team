"""Platform self-regression suite ("testing the tester").

This module guards the *platform* itself against silent regression — it is
distinct from *target* regression (which re-attacks the sidecar under test).
Here the subject under test is the red-team platform's own machinery: the
Judge's safety invariant and calibration, the Red Team's novelty guard, and
the pydantic message contracts that govern every inter-agent boundary.

Four check families:

1. Judge safety invariant — a labeled confirmed exploit is never scored safe.
2. Calibration stability — labeled fixtures classify correctly on a healthy
   Judge, and a broken/stuck Judge is caught.
3. Red Team novelty — a near-duplicate attack is flagged non-novel.
4. Message-contract conformance — every inter-agent boundary payload validates
   against its pinned pydantic schema.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Callable, Iterable

import pydantic

from forge.judge import CALIBRATION_FIXTURES, JudgeAgent
from forge.schemas import (
    AttackAttempt,
    AttackDirective,
    RegressionTrigger,
    Verdict,
    VulnReport,
)


# --------------------------------------------------------------------------- #
# 1 & 2. Judge safety invariant + calibration
# --------------------------------------------------------------------------- #
@dataclass
class CalibrationResult:
    name: str
    expected: str
    actual: str
    ok: bool


def judge_invariant_holds(judge: JudgeAgent) -> bool:
    """True iff the Judge never scores the confirmed-exploit fixture as safe.

    The safety invariant means a labeled ``confirmed_exploit`` is never scored
    ``"fail"``, even when the underlying LLM says so.
    """
    fixture = next(
        fx for fx in CALIBRATION_FIXTURES if fx["label"] == "confirmed_exploit"
    )
    verdict = judge.evaluate(fixture["attempt"], ground_truth="confirmed_exploit")
    return verdict.verdict != "fail"


def run_calibration(
    build_judge: Callable[[dict], JudgeAgent],
) -> list[CalibrationResult]:
    """Evaluate every calibration fixture with a per-fixture Judge."""
    results: list[CalibrationResult] = []
    for fixture in CALIBRATION_FIXTURES:
        judge = build_judge(fixture)
        ground_truth = (
            "confirmed_exploit" if fixture["label"] == "confirmed_exploit" else None
        )
        verdict = judge.evaluate(fixture["attempt"], ground_truth=ground_truth)
        actual = verdict.verdict
        expected = fixture["expected_verdict"]
        results.append(
            CalibrationResult(
                name=fixture["name"],
                expected=expected,
                actual=actual,
                ok=(actual == expected),
            )
        )
    return results


# --------------------------------------------------------------------------- #
# 3. Red Team novelty (word-token similarity)
# --------------------------------------------------------------------------- #
def similarity(a: str, b: str) -> float:
    """Word-level similarity in [0, 1], computed symmetrically.

    Tokenizes each string with ``str.split()`` then takes the max of both
    SequenceMatcher orderings, guaranteeing ``similarity(a, b) ==
    similarity(b, a)`` exactly and ``similarity(a, a) == 1.0``.
    """
    ta = a.split()
    tb = b.split()
    return max(
        difflib.SequenceMatcher(None, ta, tb).ratio(),
        difflib.SequenceMatcher(None, tb, ta).ratio(),
    )


def max_similarity(candidate: str, corpus: Iterable[str]) -> float:
    """Maximum similarity of ``candidate`` against ``corpus``; 0.0 if empty."""
    return max((similarity(candidate, c) for c in corpus), default=0.0)


def is_novel(candidate: str, corpus: Iterable[str], *, threshold: float = 0.8) -> bool:
    """True iff no corpus entry is within ``threshold`` of ``candidate``.

    A near-duplicate of a stored attempt is NOT novel; an empty corpus is
    always novel.
    """
    return max_similarity(candidate, corpus) < threshold


# --------------------------------------------------------------------------- #
# 4. Inter-agent message-contract conformance
# --------------------------------------------------------------------------- #
BOUNDARY_SCHEMAS: dict[str, type] = {
    "orchestrator->red_team": AttackDirective,
    "red_team->judge": AttackAttempt,
    "judge->store": Verdict,
    "documentation->reports": VulnReport,
    "regression->scheduler": RegressionTrigger,
}


@dataclass
class ContractResult:
    boundary: str
    ok: bool
    error: str | None


def check_contract(boundary: str, payload: dict) -> ContractResult:
    """Validate ``payload`` against the schema pinned to ``boundary``.

    A missing boundary raises ``KeyError``; a payload that fails pydantic
    validation yields ``ok=False`` with the error string.
    """
    schema = BOUNDARY_SCHEMAS[boundary]
    try:
        schema(**payload)
    except pydantic.ValidationError as exc:
        return ContractResult(boundary, False, str(exc))
    return ContractResult(boundary, True, None)


def check_all_contracts(samples: dict[str, dict]) -> list[ContractResult]:
    """Check every boundary present in ``samples`` (in BOUNDARY_SCHEMAS order)."""
    return [
        check_contract(boundary, samples[boundary])
        for boundary in BOUNDARY_SCHEMAS
        if boundary in samples
    ]
