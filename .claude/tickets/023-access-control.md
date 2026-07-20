---
id: 023
title: Target allowlist + operator auth + audit log
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [004]
branch: ticket/023-access-control
base_branch: main
test_command: ".venv/bin/pytest tests/test_access_control.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 2
---

## Description
Make the platform safe to point, as standalone safety primitives the Adapter (005) then consumes:
a **target allowlist/registry** resolving a pre-registered `target_id` → its config (base_url, …),
refusing any unlisted id or raw URL; an **operator auth** check (API-key/CLI token at MVP) gating who
may trigger a run; and an **append-only audit log** over the store's `events` table (who / what /
when) with a DB-level guard so events cannot be updated or deleted.

## Acceptance criteria
- [ ] A run naming an allowlisted target id resolves to its config; an unlisted id/raw URL is refused with a typed error.
- [ ] Triggering a run requires a valid operator token; an unauthenticated/invalid trigger is rejected with a typed error.
- [ ] Each trigger + agent action is written append-only to `events` (who/what/when); attempted UPDATE/DELETE on events fails.

## Test plan (orchestrator authors these)
- unit: `tests/test_access_control.py` — allowlisted vs unlisted target id vs raw URL; authed vs
  unauthed trigger; audit record appends who/what/when in order; events are append-only (UPDATE/DELETE raises).
