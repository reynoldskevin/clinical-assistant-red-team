---
id: 041
title: AI-use disclosure — fuller writeup + drifting-judge detection
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [028]
branch: ticket/041-ai-use-disclosure
base_branch: main
test_command: ".venv/bin/pytest tests/test_ai_use_disclosure.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Promote the ARCHITECTURE.md AI-use section into a standalone `AI_USE_DISCLOSURE.md` (brief #8 stretch): for every AI-powered agent role (Red Team, Judge, Orchestrator, Documentation) disclose exactly where AI is used, the deterministic or human verification that follows each AI decision, and the residual risk that remains. Add an explicit **"detect & correct a drifting Judge"** procedure wired to the platform's calibration-stability check (ticket 028's `run_calibration` over the frozen `CALIBRATION_FIXTURES` + the safety invariant) — stating the detection signal, threshold/cadence, and the correction response.

## Acceptance criteria
- [ ] Every AI-powered agent role is listed with the AI use, its deterministic/human check, and its residual risk.
- [ ] A residual-risk section states what remains risky and what was independently verified.
- [ ] A drift-detection-and-correction procedure references the calibration mechanism (frozen calibration set / invariant) and names both how drift is DETECTED and how it is CORRECTED.

## Test plan (orchestrator authors these)
- unit: `tests/test_ai_use_disclosure.py` — doc present and substantive; each of the four AI roles appears with a check keyword; a residual-risk section exists; the drifting-judge procedure references calibration and covers detect + correct.
