---
id: 015
title: Documentation agent (report · data-quality · human gate)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [004, 007]
branch: ticket/015-documentation-agent
base_branch: main
test_command: ".venv/bin/pytest tests/test_documentation_agent.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Convert a Judge-confirmed `Verdict` into a `VulnReport` with the required fields (unique id + severity, description + clinical impact, minimal reproducible sequence, observed vs expected, remediation, status). Enforce a data-quality gate (required fields + uniqueness — no duplicate report for the same attack sequence) before writing; publication requires a human approval gate. Writes drafts to the store + `./reports/`. The approval gate is severity-aware: critical/high reports require explicit human sign-off before publish; lower severities still draft but never auto-publish.

## Acceptance criteria
- [ ] Confirmed verdict → `VulnReport` with all required fields populated (status starts as `draft`).
- [ ] Data-quality gate rejects a missing-field report and a duplicate-sequence report before write.
- [ ] Draft is written (store + `./reports/`) but publication is blocked pending an explicit human approval flag.
- [ ] Critical/high reports require explicit sign-off; no severity path auto-publishes (a draft is never `published` without approval).

## Test plan (orchestrator authors these)
- unit: `tests/test_documentation_agent.py` — confirmed verdict → full report persisted to store + reports dir; a report with an empty required field is rejected; drafting the same attack sequence twice is rejected as a duplicate; `publish()` without approval raises and leaves status `draft`, with approval flips to `published`; a critical report requires sign-off; a low-severity report never auto-publishes.
