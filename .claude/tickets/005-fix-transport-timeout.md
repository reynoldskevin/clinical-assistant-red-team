---
id: 005-fix
title: Adapter transport timeout — raise default + make configurable
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [005]
branch: fix/005-transport-timeout
base_branch: main
test_command: ".venv/bin/pytest tests/test_target_adapter.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 1
---

## Description
The merged Target Adapter (ticket 005) hard-codes the default transport timeout at 30s. Live `/ask` runs a multi-tool agent loop that took 4-27s in measurement (heaviest benign query 26.5s), and red-team attacks are heavier still, so occasional requests would exceed 30s and surface as a spurious `TargetUnreachable` (transport timeout) rather than a real target failure. Fix: raise the default transport timeout to a value with real headroom (>=60s) and make it configurable per `TargetAdapter` via a `timeout` kwarg, so a run can tune it. A caller-injected `transport` still controls its own timeout (the `timeout` kwarg only governs the built-in default transport).

## Acceptance criteria
- [ ] The default transport timeout is >= 60s (was 30s), giving headroom over observed live latency.
- [ ] `TargetAdapter(..., timeout=<s>)` makes the built-in default transport use that timeout (passed to `urlopen`).
- [ ] Existing adapter behavior is unchanged: an injected `transport` is used as-is; all prior 005 tests stay green.

## Test plan (orchestrator authors these)
- unit: `tests/test_target_adapter.py` — a new locked test (monkeypatching `urlopen`) asserts the
  default-transport path passes `_DEFAULT_TIMEOUT` to `urlopen`, that `_DEFAULT_TIMEOUT >= 60`, and
  that a per-adapter `timeout=` kwarg overrides it. The pre-existing 005 tests (wire contract, error
  mapping, token redaction, multi-turn, health/extract) remain unchanged and green.
