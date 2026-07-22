---
id: 028
title: Platform self-regression suite (invariants + novelty)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [018, 024]
branch: ticket/028-platform-selfcheck
base_branch: main
test_command: ".venv/bin/pytest tests/test_platform_selfcheck.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
"Testing the tester": a fixed self-regression suite asserting the *platform* itself hasn't regressed, distinct from target regression. A `forge/selfcheck.py` module provides four check families — the Judge safety invariant (a confirmed exploit is never scored safe), calibration-set stability (the labeled `CALIBRATION_FIXTURES` still classify to their expected verdicts on a healthy Judge), Red Team novelty (a newly generated attack must differ from stored attempts by a similarity threshold, guarding against a stale generator), and inter-agent message-contract conformance (every boundary payload validates against its pydantic schema). These guard the platform against silent regressions that a target-only regression suite would miss.

## Acceptance criteria
- [ ] Judge safety-invariant + calibration-stability checks run and pass on a healthy platform.
- [ ] A near-duplicate generated attack is flagged as non-novel by the similarity check.
- [ ] Message-contract conformance is verified for every inter-agent boundary (valid payloads pass, malformed payloads are flagged).

## Test plan (orchestrator authors these)
- unit: `tests/test_platform_selfcheck.py` — invariant holds when the underlying LLM mis-scores a confirmed exploit; calibration stable on a healthy Judge and broken Judge is caught; a near-duplicate prompt is flagged non-novel while a distinct one is novel; each inter-agent boundary schema conforms for valid payloads and flags malformed ones.
