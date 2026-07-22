---
id: 019b
title: Expand seed corpus depth to >=10 cases per category
status: todo # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [008, 014]
branch: ticket/019b-seed-corpus-depth
base_branch: main
test_command: ".venv/bin/pytest tests/test_seed_corpus_depth.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Reviewer feedback: the live corpus was thin (25 attempts, ~2–9 per category) because the seed suite carried only 2–3 cases per category. Grow `./evals/` so every attack category has **≥10** distinct, OWASP-mapped, schema-valid seed cases (≥60 total, up from 16) so a single live `forge run --suite` yields ≥10 attempts/category. Raise the Orchestrator coverage-sufficiency threshold default from 3 → 10 so its "category is done" rule matches the ≥10 bar. (A fresh live run + `EVAL_RESULTS.md` re-export is a follow-up operational step, not part of this ticket.)

## Acceptance criteria
- [ ] Every attack category in `./evals/` has ≥10 seed cases; total ≥60.
- [ ] All cases remain schema-valid with a non-empty OWASP mapping and globally-unique ids.
- [ ] The new cases add genuine attack variety (distinct subcategories/prompts), not near-duplicates.
- [ ] `Orchestrator` default `coverage_target` is 10.

## Test plan (orchestrator authors these)
- unit: `tests/test_seed_corpus_depth.py` — load_cases() groups by category, every category ≥10, total ≥60, ids unique, each case schema-valid + OWASP-mapped, and prompts within a category are distinct; `Orchestrator(...).coverage_target == 10` by default.
