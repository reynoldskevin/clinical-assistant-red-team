---
id: 058
title: Store data-quality checks, SQL indexing, retention batch job
status: todo
depends_on: []
branch: ticket/058-store-data-quality-indexing
base_branch: main
test_command: ".venv/bin/pytest tests/test_store_data_quality.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The SQLite store indexes only `findings(severity|attack_category|target_version)`, yet
the hot read paths scan `events.kind`, `findings.status`, and — the dominant scoping key —
`run_id`, which lives inside the JSON `data` blob and cannot be WHERE-filtered. Inserts do
no validation, so a finding can persist with NULL `severity`/`status`. There is no
retention/maintenance job for the append-only `events`/`cost` tables. This ticket adds a new
store migration that (a) indexes the real hot paths, (b) promotes `run_id` to a native
indexed column on `findings` and `cost`, (c) validates required fields + enums on insert, and
(d) provides a `prune` retention batch job. All additive and behind the existing migration
framework so no mainline read code changes shape.

## Acceptance criteria
- [ ] A new `Migration` adds indexes `idx_events_kind` on `events(kind)` and
      `idx_findings_status` on `findings(status)`, and promotes `run_id` to a native column
      on `findings` and `cost` (backfilled from each row's JSON `data.run_id`) with indexes
      `idx_findings_run_id` / `idx_cost_run_id`. `schema_version()` increases by exactly 1;
      existing rows are preserved and their `run_id` backfilled.
- [ ] `run_id` remains readable through the existing JSON surface (list_findings/get_costs
      rows still expose `run_id`), so `forge/scoping.py` keeps working unchanged.
- [ ] `insert_finding` rejects a row whose `severity` is missing/blank or not one of
      critical/high/medium/low, raising a clear `ValueError` (no such row persisted).
      `append_event` rejects a row whose `kind` is missing/blank. Validation is centralized and
      does not silently coerce. (`status` stays optional — existing callers omit it.)
- [ ] A `prune(before_id=None, keep_last=None)` (or equivalently-named) retention job deletes
      old `events`/`cost` rows by id watermark, returns the count removed, is idempotent, and
      never deletes `findings`/`regression_cases`. Pruning is opt-in (no automatic deletion on
      normal writes).
- [ ] All existing store tests (`tests/test_store.py`) stay green; the three original
      `findings` indexes remain.

## Test plan (orchestrator authors these)
- unit (`tests/test_store_data_quality.py`):
  - migration creates the new indexes (PRAGMA index_list) and native `run_id` columns; version+1.
  - pre-existing findings/cost rows get their `run_id` backfilled from the JSON blob.
  - insert_finding rejects missing/blank/invalid severity; append_event rejects missing/blank kind.
  - valid rows still insert and round-trip; run_id still exposed on read.
  - prune removes only events/cost up to a watermark, returns count, idempotent, leaves findings intact.
