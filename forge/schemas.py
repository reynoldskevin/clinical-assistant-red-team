"""Versioned inter-agent message schemas (v1) + typed errors.

All message models carry a ``schema_version`` field defaulting to ``"v1"`` and
round-trip losslessly through ``model_dump()`` and ``model_dump_json()``.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, Field


class AttackDirective(BaseModel):
    schema_version: str = "v1"
    category: str
    seed: str | None = None
    max_attempts: int = 1
    max_cost_usd: float = 1.0


class AttackAttempt(BaseModel):
    schema_version: str = "v1"
    category: str
    prompt: str
    target_id: str | None = None
    turns: int = 1
    transcript: list[dict] = Field(default_factory=list)


class Verdict(BaseModel):
    schema_version: str = "v1"
    verdict: Literal["success", "fail", "partial"]
    confidence: float = Field(ge=0, le=1)
    rationale: str
    owasp_web: list[str]
    owasp_llm: list[str]
    rubric_version: str = "v1"


class RegressionTrigger(BaseModel):
    schema_version: str = "v1"
    reason: Literal["target_version_change", "time_window", "manual"]
    target_id: str
    target_version: str | None = None


class VulnReport(BaseModel):
    schema_version: str = "v1"
    id: str
    severity: Literal["critical", "high", "medium", "low"]
    description: str
    clinical_impact: str
    reproduction: str
    observed: str
    expected: str
    remediation: str
    status: str = "draft"


class ErrorType(str, enum.Enum):
    target_unreachable = "target_unreachable"
    budget_exceeded = "budget_exceeded"
    judge_timeout = "judge_timeout"
    no_findings_in_window = "no_findings_in_window"
    regression_detected = "regression_detected"


class ErrorResult(BaseModel):
    schema_version: str = "v1"
    error_type: ErrorType
    detail: str = ""
