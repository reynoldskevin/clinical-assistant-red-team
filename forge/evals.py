"""Seed eval dataset: case schema + loader (ticket 008).

An ``EvalCase`` is one OpenEMR Clinical Co-Pilot red-team scenario with a
required OWASP mapping. ``load_cases`` reads the seed suite under ``./evals/``.
"""

from __future__ import annotations

import json
import pathlib
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator


class EvalCaseError(Exception):
    """Raised by the loader when a case file fails validation."""


class EvalCase(BaseModel):
    schema_version: str = "v1"
    id: str
    category: str
    subcategory: str | None = None
    prompt: str | None = None
    input_sequence: list[str] | None = None
    expected_behavior: str
    observed_behavior: str | None = None
    severity: Literal["critical", "high", "medium", "low"]
    add_to_regression: bool = False
    owasp_web: list[str] = Field(default_factory=list)
    owasp_llm: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "EvalCase":
        if not (self.owasp_web or self.owasp_llm):
            raise ValueError(
                "at least one of owasp_web / owasp_llm must be non-empty"
            )
        if not (self.expected_behavior and self.expected_behavior.strip()):
            raise ValueError("expected_behavior must be non-empty")
        has_prompt = bool(self.prompt and self.prompt.strip())
        has_sequence = bool(self.input_sequence)
        if not (has_prompt or has_sequence):
            raise ValueError("a case must have a prompt or a non-empty input_sequence")
        return self


def load_cases(evals_dir=None) -> list[EvalCase]:
    """Load and validate every ``*.json`` case file in ``evals_dir``.

    Each file may contain a single case object or a JSON list of case objects.
    Raises ``EvalCaseError`` (naming the file) on any validation failure.
    """
    if evals_dir is None:
        evals_dir = pathlib.Path(__file__).resolve().parents[1] / "evals"
    evals_dir = pathlib.Path(evals_dir)

    cases: list[EvalCase] = []
    for path in sorted(evals_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise EvalCaseError(f"{path}: invalid JSON: {exc}") from exc
        records = raw if isinstance(raw, list) else [raw]
        for record in records:
            try:
                cases.append(EvalCase(**record))
            except ValidationError as exc:
                raise EvalCaseError(f"{path}: invalid eval case: {exc}") from exc
    return cases
