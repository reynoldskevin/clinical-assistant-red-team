---
id: 070
title: View-reports button reflects report availability (shows on partial-only runs)
status: todo
depends_on: []
branch: ticket/070-reports-button-availability
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_partial_reports.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The Exploits-panel "View reports" button is gated on the current run's `exploits` count
(`vr.hidden = !(k.exploits > 0)`), but the reports modal shows ALL vulnerability reports on
disk (not run-scoped) and confirmed exploits are the only source of reports. So a run that
produces only `partial` verdicts (exploits == 0) hides the button even when there ARE reports to
view. Fix: gate the button on report AVAILABILITY — expose the count of available reports in the
state and show the button whenever that count > 0, independent of the exploit/partial split.

## Acceptance criteria
- [ ] `build_state(observability, *, reports_dir=None)` gains a `reports_dir` keyword; the state's
      `kpis` includes `reports` = the number of available reports (`len(load_reports(reports_dir))`
      when `reports_dir` is given, else `0`). No other state fields change; existing callers that
      don't pass `reports_dir` still work (reports == 0).
- [ ] The dashboard's live server wires the real reports dir into the state (`make_server`'s
      `state_provider` passes its resolved `reports_dir` to `build_state`), so `kpis.reports`
      reflects the reports actually on disk.
- [ ] The Exploits-panel "View reports" button visibility is driven by report availability:
      `renderKpis` sets `view-reports`.hidden = `!(k.reports > 0)` (no longer `!(k.exploits > 0)`).
      So a partial-only run with reports on disk SHOWS the button; a run with no reports hides it.
- [ ] The Known-vulnerabilities-panel button (`view-reports-kv`) is unchanged (still tied to the
      unfixed/vulnerable count); both buttons still open the same modal.
- [ ] The obsolete 052 assertion (button toggled by `k.exploits > 0`) is updated to the new
      report-availability condition.

## Test plan (orchestrator authors these)
- unit (`tests/test_dashboard_partial_reports.py`):
  - `build_state(obs, reports_dir=<dir with 2 reports>)` -> `kpis.reports == 2`; `reports_dir=None` -> 0.
  - the rendered JS gates `view-reports` on `!(k.reports > 0)` and no longer on `!(k.exploits > 0)`.
  - user scenario: a run with only `partial` verdicts + a report on disk -> `kpis.exploits == 0`
    but `kpis.reports == 1` (so the button shows).
  - e2e: `make_server(reports_dir=<dir with reports>)` -> `GET /api/state` -> `kpis.reports` matches.
- update `tests/test_dashboard_report_buttons.py::test_exploits_report_button_toggled_by_exploit_count`
  to assert the new `!(k.reports > 0)` condition.
