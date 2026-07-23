"""Ticket 036 — Inter-agent contract publication + versioning.

Locked acceptance tests. The pydantic message models are exported to JSON Schema
under `contracts/agent/`, a drift check ties each committed schema to the live
model, and dual-side conformance validates producer payloads against the
published contract. Stdlib + pydantic only (no jsonschema dependency).
"""

from __future__ import annotations

import json
import pathlib

import pydantic
import pytest

from forge.contracts import (
    AGENT_MESSAGES,
    CONTRACTS_DIR,
    check_drift,
    published_schema,
    schema_path,
    validate_payload,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Minimal valid producer payloads for every registered message.
_VALID = {
    "attack_directive": {"category": "prompt_injection"},
    "attack_attempt": {"category": "prompt_injection", "prompt": "attack text"},
    "verdict": {
        "verdict": "success",
        "confidence": 0.9,
        "rationale": "leaked PHI",
        "owasp_web": ["A01:2021-Broken Access Control"],
        "owasp_llm": ["LLM06:Sensitive Information Disclosure"],
    },
    "regression_trigger": {"reason": "manual", "target_id": "copilot"},
    "vuln_report": {
        "id": "VULN-1",
        "severity": "high",
        "description": "d",
        "clinical_impact": "c",
        "reproduction": "r",
        "observed": "o",
        "expected": "e",
        "remediation": "m",
    },
    "error_result": {"error_type": "target_unreachable"},
}


def test_registry_lists_the_inter_agent_message_models() -> None:
    # At least the six core inter-agent messages are registered.
    assert len(AGENT_MESSAGES) >= 6
    for name, model in AGENT_MESSAGES.items():
        assert isinstance(name, str) and name
        assert issubclass(model, pydantic.BaseModel), name


def test_every_message_has_a_published_schema_file() -> None:
    for name in AGENT_MESSAGES:
        path = schema_path(name)
        assert path.exists(), f"missing published schema for {name}: {path}"
        data = json.loads(path.read_text())
        assert "properties" in data, f"{name} schema has no properties"
        # Versioned contract: schema_version is part of the published shape.
        assert "schema_version" in data["properties"], f"{name} not versioned"


def test_published_schemas_live_under_contracts_agent() -> None:
    assert CONTRACTS_DIR == REPO_ROOT / "contracts" / "agent"
    for name in AGENT_MESSAGES:
        assert schema_path(name).parent == CONTRACTS_DIR


def test_no_schema_drift_between_committed_and_live_model() -> None:
    # The committed schema must equal what the live pydantic model emits now.
    drifted = check_drift()
    assert drifted == [], f"schema drift (re-export needed) for: {drifted}"


def test_published_schema_matches_model_json_schema_each() -> None:
    for name, model in AGENT_MESSAGES.items():
        on_disk = json.loads(schema_path(name).read_text())
        assert on_disk == model.model_json_schema(), f"{name} drifted"
        assert published_schema(name) == on_disk


def test_dual_side_conformance_for_valid_payloads() -> None:
    for name, model in AGENT_MESSAGES.items():
        payload = _VALID[name]
        # Producer side: no missing required fields per the published contract.
        missing = validate_payload(name, payload)
        assert missing == [], f"{name} valid payload flagged missing {missing}"
        # Consumer side: the model reconstructs and round-trips.
        obj = model(**payload)
        assert model(**obj.model_dump()) == obj


def test_missing_required_field_is_flagged() -> None:
    # Verdict.rationale is required — dropping it must be flagged AND rejected.
    bad = {k: v for k, v in _VALID["verdict"].items() if k != "rationale"}
    missing = validate_payload("verdict", bad)
    assert "rationale" in missing
    with pytest.raises(pydantic.ValidationError):
        AGENT_MESSAGES["verdict"](**bad)


def test_unknown_message_name_raises() -> None:
    with pytest.raises(KeyError):
        schema_path("orchestrator_to_mars")
    with pytest.raises(KeyError):
        validate_payload("orchestrator_to_mars", {})


def test_versioning_policy_doc_present() -> None:
    readme = CONTRACTS_DIR / "README.md"
    assert readme.exists(), "contracts/agent/README.md missing"
    text = readme.read_text().lower()
    assert "v1" in text
    assert "migration" in text
    assert "version" in text
