---
id: 019
title: OWASP coverage completion (mandatory engineering)
status: todo # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [008, 016]
branch: ticket/019-owasp-coverage
base_branch: main
test_command: ".venv/bin/pytest tests/test_owasp_coverage.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Expand the eval suite so every mandated OWASP Web Top 10 and OWASP LLM Top 10 entry relevant to the Co-Pilot has at least one mapped eval case, and add a coverage report that enforces it. The mandated Web entries are broken access control, injection, insecure design, vulnerable/outdated components, authentication failures, security logging & monitoring failures, and SSRF; the mandated LLM entries are prompt injection, insecure output handling, sensitive information disclosure, excessive agency, and supply-chain. A `forge/owasp.py` module pins the canonical mandated label set and computes a coverage report over the loaded cases; a coverage test fails if any mandated entry has zero mapped cases. Four new seed cases (A06 vulnerable components, A09 logging failures, LLM02 insecure output handling, LLM05 supply chain) close the current gaps.

## Acceptance criteria
- [ ] `forge/owasp.py` defines the canonical mandated Web + LLM label sets and a `coverage_report(cases)` computing per-entry counts and the missing set.
- [ ] Every mandated OWASP Web + LLM entry has ≥1 eval case mapped to it (loader-visible).
- [ ] The coverage report/test fails if any mandated entry has zero cases (removing a case for an entry surfaces it as missing).
- [ ] New seed cases are valid `EvalCase`s (load via `load_cases()` without error) and Co-Pilot-relevant.

## Test plan (orchestrator authors these)
- unit: `tests/test_owasp_coverage.py` — mandated sets are non-empty and use canonical labels; `coverage_report(load_cases())` reports zero missing (full coverage); dropping every case that maps a given mandated entry makes `coverage_report` list that entry as missing / `is_complete` False; each mandated entry maps to ≥1 real loaded case.
