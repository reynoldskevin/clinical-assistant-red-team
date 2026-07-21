---
id: 010
title: THREAT_MODEL.md deliverable
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [001]
branch: ticket/010-threat-model-doc
base_branch: main
test_command: ".venv/bin/pytest tests/test_threat_model_doc.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
`./THREAT_MODEL.md` mapping the full attack surface across the six categories (prompt injection, data exfiltration, state corruption, tool misuse, DoS, identity/role exploitation). Each category documents attack surface, potential impact, exploitation difficulty, and whether existing defenses address it, with OWASP mapping. Begins with a ~500-word key-findings summary (hard gate).

## Acceptance criteria
- [ ] File exists with all six categories, each carrying the four required fields + OWASP mapping.
- [ ] Opens with a ~500-word summary section of key findings + highest-risk categories.

## Test plan (orchestrator authors these)
- unit: `tests/test_threat_model_doc.py` — file present; six category headings; required fields per category; summary section present and within word-count band.
