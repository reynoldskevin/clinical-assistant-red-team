# Inter-agent message contracts

These are the **versioned inter-agent message contracts** exchanged between the
platform's agents. Each message model lives in `forge/schemas.py` and is
published here as a JSON Schema artifact (`<name>.schema.json`).

## Versioning

- The current contract **version** is **v1**. Every message carries a
  `schema_version` field (defaulting to `"v1"`), so the version travels with the
  payload on the wire.
- A **breaking change requires a version bump plus a migration note**. Bump the
  `schema_version` default on the model, document the change and its
  **migration** path here, and regenerate the artifacts.

## Regenerating

Regenerate the published schemas with:

```
python -m forge.contracts
```

This writes each model's `model_json_schema()` to `contracts/agent/`. The drift
test (`tests/test_agent_contracts.py`) enforces that the committed schemas match
the live models — if it fails, re-run the command above and commit the result.
