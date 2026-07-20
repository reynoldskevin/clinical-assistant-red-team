---
id: 001
title: Project scaffold & config
status: ready-for-merge   # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: []
branch: ticket/001-project-scaffold-config
base_branch: main
test_command: ".venv/bin/pytest tests/test_config.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 1
---

## Description
Stand up the Python package (`forge/`), `pyproject.toml`, `pytest`, and a typed config loaded from
env: `ANTHROPIC_API_KEY`, `TARGET_BASE_URL`, `TARGET_AUTH`, `DB_PATH`, per-role model ids, budget
defaults. Foundation for every later ticket.

## Acceptance criteria
- [ ] Package imports; `pytest` runs green on an empty suite.
- [ ] Config loads + validates from env; missing required var raises a typed `ConfigError`.
- [ ] Per-role model ids and budget defaults are configurable with sane fallbacks.

## Test plan (orchestrator authors these)
- unit: `tests/test_config.py` — loads valid env; missing required var → `ConfigError`; per-role
  model defaults + env override; budget defaults + env override; optional vars default cleanly.
