---
id: 005
title: Target Adapter (sole egress to the live Co-Pilot)
status: tests-authored  # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [001, 003, 004, 023]
branch: ticket/005-target-adapter
base_branch: main
test_command: ".venv/bin/pytest tests/test_target_adapter.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The only component that talks to the Co-Pilot. Encodes the sidecar's PINNED HTTP contract
(`sidecar/openapi.yaml` + `contracts.py` @ commit `c847837`, vendored under `contracts/`):
`POST {base}/ask` with `AskRequest{pid:int, question:str, conversation_id:str|null}` →
`AskResponse{answer:str, correlation_id:str}`. Resolves an allowlisted target id via 023 (never a
raw URL). Auth is a pluggable `token_provider(pid) -> JWT` (patient-scoped bearer; static token =
provider ignoring pid). Multi-turn: adapter generates + reuses a `conversation_id` per session.
Records raw request (token redacted) + response transcript to the store for exact replay. Error
mapping: transport failure + HTTP 5xx → typed `TargetUnreachable`; 4xx → returned as a structured
observation (a 401 is an attack signal, not a transport failure); 200 → parsed reply. Also supports
`POST {base}/extract` and the unauth `GET /health` liveness probe.

## Acceptance criteria
- [ ] Sends an `/ask` turn with the exact `AskRequest` shape (HTTP mocked) and returns the parsed `AskResponse`.
- [ ] `Authorization: Bearer <token_provider(pid)>`; provider is per-pid pluggable; unauth on `/health`.
- [ ] Multi-turn: a stable `conversation_id` is generated and carried across turns.
- [ ] Only an allowlisted target id resolves (via 023); a raw URL / unlisted id is refused.
- [ ] Records raw request (token REDACTED) + response transcript to the store.
- [ ] Transport failure + 5xx → typed `TargetUnreachable`; 4xx returned as a structured observation.
- [ ] Emitted request + a real response conform to the vendored `contracts/` schema (wire contract test).

## Test plan (orchestrator authors these)
- unit: `tests/test_target_adapter.py` — mocked-transport `/ask` single-turn shape+parse; multi-turn
  reuses conversation_id; token_provider(pid) drives the bearer header; transcript persisted with
  token redacted; transport/5xx → `TargetUnreachable`; 4xx surfaced; `/health` unauth; `/extract` shape.
- contract: shared fixture = vendored `contracts/ask_*.schema.json` — adapter's emitted request +
  parsed response both conform (reused by 009).
