---
id: 012
title: Deploy target to Railway + README (deployed URL hard gate)
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [005]
branch: ticket/012-deploy-target-readme
base_branch: main
test_command: ".venv/bin/pytest tests/test_target_smoke.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Bring the existing Co-Pilot into a deployed, testable state on Railway; document any changes made and the deployed URL in `README.md` (the URL is a hard gate submitted with every checkpoint). Add a smoke check that the Adapter can reach the configured live target. The deployed target MUST be a non-production instance seeded with synthetic patient data only — no real PHI (bounds the blast radius of exfiltration attacks and harmful generated content). Document the data-handling + retention policy for stored transcripts in the README.

## Acceptance criteria
- [ ] `README.md` documents changes made to make the Co-Pilot testable + the deployed target URL.
- [ ] README states the target is non-prod / synthetic-data-only and documents transcript retention.
- [ ] A smoke test confirms the Adapter reaches the configured target (skips cleanly if URL unset).

## Test plan (orchestrator authors these)
- unit: `tests/test_target_smoke.py` — with a mock/live URL, Adapter health/echo succeeds; unset URL → test skips (not fails).
