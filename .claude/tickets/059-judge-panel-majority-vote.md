---
id: 059
title: Judge panel (majority vote) for higher-confidence verdicts
status: todo
depends_on: []
branch: ticket/059-judge-panel-majority-vote
base_branch: main
test_command: ".venv/bin/pytest tests/test_judge_panel.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Every attempt is scored by a single Judge LLM call, so a lone mis-score sets the verdict.
Add a `JudgePanel` that duck-types the Judge's `evaluate(attempt, *, ground_truth=None) ->
Verdict` interface but runs N independent judgments and returns the majority verdict, so a
single outlier can't flip the outcome. Because `Runner` and `RegressionHarness` only depend on
`.evaluate(...) -> Verdict`, the panel drops in at the judge construction site in
`forge/run.py` with no mainline changes.

## Acceptance criteria
- [ ] `JudgePanel(members, *, tie_breaker="partial")` (or accepting a factory + `n`) exposes
      `evaluate(attempt, *, ground_truth=None) -> Verdict`, structurally compatible with
      `JudgeAgent` (duck-typed; a `Runner`/`RegressionHarness` given a panel works unchanged).
- [ ] The panel's verdict is the MAJORITY of its members' `verdict` values
      (success/fail/partial). A strict majority wins; on a tie the result is the configured
      tie-breaker (default `partial`, the conservative escalation), never a silent default.
- [ ] The panel's `confidence` is aggregated across members (e.g. mean confidence of the
      members that voted for the winning verdict), in [0,1]. `owasp_web`/`owasp_llm` are the
      UNION of the winning-verdict members' tags (deduped); `rationale` summarizes the vote
      (e.g. "3/3 fail"). `rubric_version`/`schema_version` preserved.
- [ ] The panel calls each member exactly once per `evaluate` and never mutates the attempt.
      A panel of size 1 returns that member's verdict unchanged (degenerate case).
- [ ] `ground_truth` is forwarded to every member (so the confirmed-exploit safety clamp still
      applies per member before the vote).
- [ ] Existing judge tests stay green; no change to `JudgeAgent` behavior.

## Test plan (orchestrator authors these)
- unit (`tests/test_judge_panel.py`):
  - 3 members [fail, fail, success] -> panel verdict "fail"; confidence = mean of the two fails.
  - tie among distinct verdicts -> tie_breaker ("partial").
  - owasp tags of winning members are unioned/deduped; rationale reflects the tally.
  - each member.evaluate called exactly once; ground_truth forwarded to each.
  - size-1 panel is a pass-through; panel duck-types as a judge (has evaluate, returns Verdict).
