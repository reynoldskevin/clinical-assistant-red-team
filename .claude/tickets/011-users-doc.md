---
id: 011
title: USERS.md deliverable
status: todo # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [001]
branch: ticket/011-users-doc
base_branch: main
test_command: ".venv/bin/pytest tests/test_users_doc.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
`./USERS.md` describing the users the platform serves, their workflows, and specific use cases, with explicit justification for why automation is the right solution.

## Acceptance criteria
- [ ] File exists with users, workflows, use cases, and an automation-justification section.

## Test plan (orchestrator authors these)
- unit: `tests/test_users_doc.py` — file present; required sections/headings exist.
