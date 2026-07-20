# Vendored target contracts

JSON-Schema copies of the **OpenEMR AI Clinical Co-Pilot sidecar** HTTP request/response
envelopes — the wire contract the Target Adapter (`forge/target.py`, ticket 005) speaks.

**Provenance (pinned):** derived from `sidecar/openapi.yaml` + `sidecar/contracts.py` in
`ssh://git@labs.gauntletai.com:22022/kevinreynolds/agent-forge.git` at commit
`c847837b63306413a535bc6a498458311d06dc57`. Those two are held identical by the sidecar's own
T60 contract tests, so this is the producer's single source of truth, not our guess.

**Deployed target:** `https://ai-sidecar-production-c492.up.railway.app`

These schemas are the shared fixture for the adapter's contract test: the adapter's emitted request
body must validate against `*_request.schema.json`, and a real response must validate against
`*_response.schema.json`. If the sidecar changes its contract, bump the pinned commit here and
re-vendor — a drift then surfaces as a failing contract test rather than a silent production break.

- Request models are **strict** (`additionalProperties: false` — the sidecar rejects unknown fields).
- Response models **ignore extras** (`additionalProperties: true` — a new server field never breaks us).
