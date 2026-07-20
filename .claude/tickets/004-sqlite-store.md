---
id: 004
title: SQLite exploit store + event log + migrations
status: ready-for-merge # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [001]
branch: ticket/004-sqlite-store
base_branch: main
test_command: ".venv/bin/pytest tests/test_store.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 2
---

## Description
Versioned, migration-aware SQLite store: tables `findings`, `regression_cases`, `attack_attempts`,
`events`, `coverage`, `cost`; a `schema_version` row; indexes on severity / attack_category /
target_version. CRUD + ordered event append. Seam for the optional data-quality/SQL-perf work.

## Acceptance criteria
- [ ] Schema creates from scratch; `schema_version` recorded.
- [ ] A sample migration adds a field and preserves existing rows (no data loss).
- [ ] CRUD for attempts/findings; ordered `events` append; indexes exist on the three keys.

## Test plan (orchestrator authors these)
- unit: `tests/test_store.py` — create; insert/query attempts & findings; event ordering;
  migration preserves data; index presence.
