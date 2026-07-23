---
id: 047
title: Dashboard UI refinements — start-button spinner, scrollable/labeled agent feed with timestamps, known-vulns box layout
status: ready-for-merge
depends_on: [046]
branch: feature/dashboard-ui-refinements
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_ui_047.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Three dashboard UI improvements: (1) the Start-run button should show a disabled spinner from click
until the run is confirmed live, so the click is obvious and duplicate runs are prevented; (2) the
Live agent activity feed should scroll to show ALL of the current run's activity, color-code the
regression + documentation steps (grey, shown in the key) without clipping the chip, and show a
timestamp after each step's hash id; (3) the Known vulnerabilities panel should mirror the "Current
run findings" three-box layout — Known (blue), Unfixed (red), Fixed (green) — dropping the "N of M"
summary line and the per-case list.

## Acceptance criteria
- [ ] **Start button (item 1):** clicking it enters a disabled "busy" state with a spinner and stays
      that way until a live update confirms the run is active (then the header swaps it for the
      run-in-progress pill). On a rejected trigger (401/409/503) it returns to the normal enabled
      state. A `.startbtn.busy` style + `@keyframes spin` exist; the JS tracks a pending-start state
      so a normal idle poll does not prematurely clear the spinner.
- [ ] **Agent feed (item 2):**
  - `Store.append_event` stamps a wall-clock `ts` (epoch seconds) on every event that doesn't
    already carry one; `Observability.agent_activity()` items include that `ts`.
  - `Observability` labels the non-agent steps: `regression_result` → `regression`,
    `vuln_report`/`vuln_report_link` → `documentation` (both render as grey chips).
  - The feed container scrolls (`overflow-y: auto` + a max-height) and renders ALL of the current
    run's activity (no fixed top-N cap); the `regression`/`documentation` chips appear in the feed
    legend/key and are not clipped.
  - Each feed row shows a formatted timestamp after the `#<seq>` hash id.
- [ ] **Known vulnerabilities (item 3):** the `#known-vulns` panel renders as a three-box `pipe`
      (like Current run findings): **Known** (total, accent/blue), **Unfixed** (vulnerable, red),
      **Fixed** (green). A `.stage.known` (blue/accent) style exists. The old "still vulnerable"
      summary line and the `kv-row` case list are removed.
- [ ] Back-compat: `build_state.known_vulnerabilities` shape unchanged (total/vulnerable/fixed/cases
      still emitted); existing dashboard/observability/per-run tests stay green. Full suite green.

## Test plan (orchestrator authors these)
- unit: tests/test_dashboard_ui_047.py —
  - `Store.append_event` stamps `ts`; an explicit `ts` is preserved; `agent_activity()` items carry `ts`.
  - `agent_activity()` labels `regression_result`→`regression` and `vuln_report(_link)`→`documentation`.
  - render_html: `.startbtn.busy` + `@keyframes spin` + a pending-start flag in the JS.
  - render_html: `.feed` rule has `overflow-y: auto`; legend has grey `regression` + `documentation`
    chips; JS renders a timestamp (`toLocaleTimeString`) and no longer caps the feed at 8 rows.
  - render_html/JS: known-vulns is a `pipe` with `Known`/`Unfixed`/`Fixed` boxes + `.stage.known`
    style; `still vulnerable` and `kv-row` are gone.
- regression: full suite green.
