---
id: 020
title: Produce ≥3 distinct Vulnerability Reports
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [018, 015, 017]
branch: ticket/020-vuln-reports
base_branch: main
test_command: ".venv/bin/pytest tests/test_vuln_reports.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Run the platform to confirm ≥3 **distinct** vulnerabilities and emit human-approved reports in the required format under `./reports/`. Reports must be reproducible by an engineer who was not present. This ticket builds the generation pipeline that turns Judge-confirmed exploits already persisted in the store into distinct, reproducible `VulnReport`s — reconstructing each `(Verdict, AttackAttempt)` from the store, drafting a report via the Documentation agent (015, with its dedup gate providing distinctness), creating a linked deterministic regression case via the Regression harness (017), and writing each report to `./reports/<id>.json` with its `regression_case_id` so an absent engineer can reproduce and re-verify it.

## Acceptance criteria
- [ ] ≥3 distinct confirmed-exploit reports exist, each with all required fields + minimal repro.
- [ ] Each report references a stored regression case proving reproducibility.
- [ ] Duplicate attack sequences collapse to a single distinct report (dedup).
- [ ] Confirmed exploits are reconstructed from the store (findings + verdict events + attempts); an empty store yields no reports.

## Test plan (orchestrator authors these)
- unit: `tests/test_vuln_reports.py` — `collect_confirmed_exploits(store)` reconstructs `(Verdict, AttackAttempt)`; `generate_reports(store, documentation, harness)` produces ≥3 distinct reports with complete required fields + minimal repro; each report links a stored `regression_case` and the written `reports/<id>.json` carries that `regression_case_id`; a duplicate exploit does not add a report; an empty store yields `[]`.
