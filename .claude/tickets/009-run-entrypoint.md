---
id: 009
title: MVP run entrypoint (live Red Team -> Adapter -> Judge)
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [004, 006, 007, 008]
branch: ticket/009-run-entrypoint
base_branch: main
test_command: ".venv/bin/pytest tests/test_run_entrypoint.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
`forge run --category <c>` (and `--suite`) drives Red Team -> Target Adapter -> Judge against the target, persisting attempts, verdicts, events, and cost to the store, and printing a per-category pass/fail summary. This is the S3 live-loop deliverable. The live token provider is the OpenEMR module `dev_mint.php` (POST `{pid}` -> pid-scoped scoped-JWT); the sidecar forwards it and `read.php` enforces the pid binding.

## Acceptance criteria
- [ ] End-to-end run (mock target in tests) persists attempts + verdicts + events + cost to the store.
- [ ] Prints a per-category pass/fail summary (target passes a category when no attack succeeds).
- [ ] A contract test pins the Adapter<->target payload shape used by the run (shared fixture with 005).

## Test plan (orchestrator authors these)
- unit/integration: `tests/test_run_entrypoint.py` — a run over a mock target (real Red Team +
  Judge + Adapter + Store; only the HTTP transport and the LLM are faked) persists attempts,
  verdict events, cost rows, and ordered run events; the per-category summary counts
  exploited/defended/partial and marks a category passed iff no exploit succeeded; a successful
  exploit writes a finding; cost is metered from the LLM calls (Red Team + Judge) and persisted;
  `format_summary` renders per-category PASS/FAIL + total cost; the run can be seeded from the
  008 eval dataset; the CLI parses `run --category` / `run --suite`.
- contract: the run's emitted `/ask` request conforms to the vendored `contracts/ask_request.schema.json`
  (shared producer fixture with 005), and is rejected when an unknown field is injected (strict).
