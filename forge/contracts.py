"""Ticket 036 — Inter-agent contract publication + versioning.

Publishes the versioned pydantic message models (see ``forge.schemas``) to JSON
Schema artifacts under ``contracts/agent/``, provides a drift check that ties
each committed schema to the live model, and offers a producer-side conformance
check against the published contract. Stdlib + pydantic only.

Regenerate the artifacts with ``python -m forge.contracts``.
"""

from __future__ import annotations

import json
import pathlib

from forge.schemas import (
    AttackAttempt,
    AttackDirective,
    ErrorResult,
    RegressionTrigger,
    Verdict,
    VulnReport,
)

# Stable snake_case name -> pydantic model class.
AGENT_MESSAGES: dict[str, type] = {
    "attack_directive": AttackDirective,
    "attack_attempt": AttackAttempt,
    "verdict": Verdict,
    "regression_trigger": RegressionTrigger,
    "vuln_report": VulnReport,
    "error_result": ErrorResult,
}

# Repo root is the directory containing ``forge/``.
CONTRACTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "agent"


def schema_path(name: str) -> pathlib.Path:
    """Return the published schema file path for ``name``.

    Raises ``KeyError`` if ``name`` is not a registered message.
    """
    if name not in AGENT_MESSAGES:
        raise KeyError(name)
    return CONTRACTS_DIR / f"{name}.schema.json"


def published_schema(name: str) -> dict:
    """Load and return the committed JSON schema for ``name``."""
    return json.loads(schema_path(name).read_text())


def check_drift() -> list[str]:
    """Return sorted names whose committed schema is missing or stale."""
    drifted: list[str] = []
    for name, model in AGENT_MESSAGES.items():
        path = schema_path(name)
        if not path.exists():
            drifted.append(name)
            continue
        if json.loads(path.read_text()) != model.model_json_schema():
            drifted.append(name)
    return sorted(drifted)


def validate_payload(name: str, payload: dict) -> list[str]:
    """Return sorted required field names absent from ``payload``.

    Checks the producer payload against the PUBLISHED schema's ``required``
    list. Raises ``KeyError`` for an unknown message name.
    """
    if name not in AGENT_MESSAGES:
        raise KeyError(name)
    required = published_schema(name).get("required", [])
    return sorted(field for field in required if field not in payload)


def write_all() -> None:
    """Write each model's JSON schema to its ``schema_path``."""
    CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in AGENT_MESSAGES.items():
        text = json.dumps(model.model_json_schema(), indent=2) + "\n"
        schema_path(name).write_text(text)


if __name__ == "__main__":
    write_all()
