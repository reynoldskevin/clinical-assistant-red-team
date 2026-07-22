---
id: 036
title: Inter-agent contract publication + versioning
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [028]
branch: ticket/036-agent-contracts
base_branch: main
test_command: ".venv/bin/pytest tests/test_agent_contracts.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Publish the versioned inter-agent message schemas (brief #6/#10) as JSON Schema under `contracts/agent/`, exported from the pydantic models via `model_json_schema()`, with a versioning policy (v1; a breaking change requires a version bump + migration note) and a migration-note template. A `forge/contracts.py` module registers every inter-agent message model, exports/loads its published schema, and exposes a drift check so an un-exported model change fails CI. Dual-side conformance is verified by validating a producer payload against the published contract and reconstructing it on the consumer side. Closes the partial cells for brief #4/#6/#10, which previously had versioned pydantic models but no published `/contracts` inter-agent schemas.

## Acceptance criteria
- [ ] Every inter-agent message model has a published `contracts/agent/<name>.schema.json` (valid JSON with a schema_version property).
- [ ] Drift test: the committed schema equals the live `Model.model_json_schema()` for each message.
- [ ] Dual-side conformance: a valid producer payload satisfies the published schema's required fields and reconstructs on the consumer via the model; a payload missing a required field is flagged.
- [ ] `contracts/agent/README.md` documents the v1 versioning + migration-note policy.

## Test plan (orchestrator authors these)
- unit: `tests/test_agent_contracts.py` — registry lists the message models; one published schema file per message; committed schema matches the live model (drift); dual-side conformance per message; missing-required-field flagged; versioning policy doc present.
