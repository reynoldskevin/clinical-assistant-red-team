---
id: 043
title: Regression replay wired into the run + "Known vulnerabilities" dashboard panel
status: tests-authored
depends_on: []
branch: feature/regression-known-vulns-panel
base_branch: main
test_command: ".venv/bin/pytest tests/test_regression_panel.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The regression harness can replay a Judge-confirmed exploit and re-judge whether it is still
vulnerable, but the deployed run path (`forge run --suite`) never invokes it, so confirmed
exploits are never re-tested and the dashboard never reflects their status. This ticket wires
`RegressionHarness.validate()` into the run (its `regression_result` events land inside the
run's event-id window so they scope to that run), exposes a `known_vulnerabilities` view from
`build_state`, and adds a "Known vulnerabilities" dashboard panel. The per-run Exploits KPI stays
"what this run found"; the new panel answers "do our known vulns still reproduce?".

## Acceptance criteria
- [ ] `Runner` accepts an optional `regression_harness`; `run_suite` calls its `validate()` after
      the category loop and BEFORE `run_end`, so the emitted `regression_result` events fall within
      the run's event-id window (and are picked up by per-run scoping). A harness error is isolated
      (recorded, does not abort the run or skip `run_end`).
- [ ] The deployed `main()` run path constructs a `RegressionHarness` (over the same store, adapter,
      judge) and passes it to the `Runner`.
- [ ] `build_state` adds `state["known_vulnerabilities"] = {total, vulnerable, fixed, cases}` derived
      from the CURRENT run's `regression_result` events (`cases` = one entry per case with
      `case_id`, `category`, `status`, `verdict`, `reappeared`; vulnerable listed first). It resets
      per run and is JSON-serializable.
- [ ] `render_html` renders a "Known vulnerabilities" panel (id `known-vulns`) and renames the
      findings panel heading to "Current run findings"; the "OWASP coverage" panel spans the height
      of both right-column panels via a dual-row layout, the two right panels each ~50% height.
- [ ] The OWASP heatrow column template stays `400px 1fr 35px`; existing dashboard behavior
      (KPIs, trend, reports modal, run trigger) is unchanged. Full suite stays green.

## Test plan (orchestrator authors these)
- unit: tests/test_regression_panel.py —
  - Runner with a fake harness: `validate()` invoked during `run_suite`; `regression_result` event
    ids fall strictly between `run_start` and `run_end`; a raising harness does not abort the run.
  - `build_state` exposes `known_vulnerabilities` scoped to the latest run (totals + per-case
    entries, vulnerable-first ordering); JSON round-trips; resets across runs.
  - `render_html` carries the "Known vulnerabilities" panel + `id="known-vulns"`, the "Current run
    findings" heading, and the dual-row layout wrapper; heatrow stays `400px 1fr 35px`.
- regression: updated tests/test_dashboard_owasp_label.py, test_dashboard_pill_spans.py,
  test_dashboard_polish.py row-3 assertions to the new layout (superseded design).
