---
id: 037
title: Build-vs-configure decision record
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: []
branch: ticket/037-decision-record
base_branch: main
test_command: ".venv/bin/pytest tests/test_decision_record.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
`DECISION_RECORD_BUILD_VS_CONFIGURE.md` (brief #2 — also a required Architecture-Defense deliverable): for each agent role (Red Team, Judge, Orchestrator, Documentation), evaluate the existing tools a reviewer would ask about — Burp Suite, OWASP ZAP, Semgrep, Garak, and commercial red-team platforms — documenting what each covers, where it falls short for adaptive multi-turn LLM-judged attacks against a clinical Co-Pilot, and the build-vs-configure verdict (build a custom agent vs configure an existing tool) with rationale. A machine-checkable decisions summary table records one verdict per agent role.

## Acceptance criteria
- [ ] Doc present; each named tool (Burp, ZAP, Semgrep, Garak) and commercial platforms are evaluated with coverage + shortfall.
- [ ] Each of the four agent roles carries a build-vs-configure verdict with rationale.
- [ ] The record justifies custom agents over configuring an existing tool for the adaptive/LLM-judged core.

## Test plan (orchestrator authors these)
- unit: `tests/test_decision_record.py` — file present and substantive; every named tool discussed with coverage/shortfall language; each of the four agent roles appears on a line carrying a Build/Configure decision; the "custom agent" justification is present.
