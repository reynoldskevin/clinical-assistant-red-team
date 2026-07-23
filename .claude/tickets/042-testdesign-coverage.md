---
id: 042
title: Test-design coverage matrix (boundary / invariant / regression)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [008, 017]
branch: ticket/042-testdesign-coverage
base_branch: main
test_command: ".venv/bin/pytest tests/test_testdesign_coverage.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Formalize brief #1 ("every adversarial test case must exercise a boundary, an invariant, or a regression risk — static payload lists do not satisfy this"). A `forge/testdesign.py` module classifies each eval case into one or more of `boundary` / `invariant` / `regression` — honoring an explicit `test_design` tag when present, otherwise deriving from existing case signals (a regression-flagged case exercises regression risk; DoS / amplification / unbounded / length / enumeration / multi-turn-sequence cases exercise a boundary; every attack case exercises the Judge safety invariant as the fallback class) — and a coverage report that fails if any of the three classes is unrepresented. Mirrors the ticket-019 OWASP-coverage pattern.

## Acceptance criteria
- [ ] Every eval case classifies to ≥1 of {boundary, invariant, regression}.
- [ ] A coverage report asserts all three classes appear across the corpus and fails on a gap.
- [ ] An explicit `test_design` tag overrides derivation (so a class can be pinned per case).

## Test plan (orchestrator authors these)
- unit: `tests/test_testdesign_coverage.py` — CLASSES are the three mandated; every loaded case classifies to ≥1 class; the corpus covers all three; each class maps to a real case; a case list missing a class is flagged (report.is_complete False, class in report.missing); explicit tags override derivation.
