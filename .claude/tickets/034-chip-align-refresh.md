---
id: 034
title: Group status chips + 10s refresh + header spacing
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [033]
branch: ticket/034-chip-align-refresh
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard_chip_align.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Three masthead tweaks. (1) The run-in-progress chip and the auto-refresh pill each carried their own `margin-left:auto`, so flexbox split the free space between them and they drifted apart; wrap both in a single right-aligned `.statusbar` (the only `margin-left:auto`) so they sit adjacent and aligned. (2) Raise the auto-refresh interval from 5s to 10s (`REFRESH_S = 10`, initial countdown `10`). (3) Increase the space under the header before the first row of boxes to match the grid row gap (masthead `margin-bottom` 6px → 14px).

## Acceptance criteria
- [ ] The `runstate` chip and `refresh-pill` are wrapped in one `.statusbar` (before the grid); `.statusbar` is the only element with `margin-left:auto` (neither `.live` nor `.runstate` keeps it).
- [ ] Refresh interval is 10s: `REFRESH_S = 10` and the initial countdown number is `10`.
- [ ] Masthead `margin-bottom` is `14px`, matching the grid `gap`.
- [ ] Full suite stays green; the superseded `5` in the pill test is updated to `10`.

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard_chip_align.py` — asserts the chips are grouped in a single right-aligned `.statusbar` (and the per-chip auto margins are gone), the 10s interval + initial countdown, and the 14px masthead bottom margin matching the grid gap.
