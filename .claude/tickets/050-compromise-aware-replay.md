---
id: 050
title: Compromise-aware multi-replay regression
status: todo
depends_on: [049]
branch: ticket/050-compromise-aware-replay
base_branch: ticket/049-compromise-signature
test_command: ".venv/bin/pytest tests/test_compromise_aware_replay.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
A single replay judged only on the attack category flips a still-live exploit to
"fixed" (the DoS diagnostic: PHI leaked 3/5 yet the Judge scored every replay
"defended"). Make replay compromise-aware and repeat it: a replay REPRODUCES the
exploit if the Judge scores it non-safe OR the case's recorded compromise markers
reappear in the target reply. Run N replays; if the exploit reproduces on ANY of
them the case is still `vulnerable` (a security tool must not call an
intermittently-live vuln "fixed"). Record the reproduction rate and per-replay
rationale for audit.

## Acceptance criteria
- [ ] `RegressionHarness(store, adapter, judge, *, pid=1, replays=3)` — `replays`
      is configurable and defaults to 3.
- [ ] Within one `replay(case, ...)`, the recorded prompts are re-asked `replays`
      times. A single run is REPRODUCED when `verdict != "fail"` OR any marker in
      the case's `compromise_signature.markers` appears (case-insensitive) in that
      run's target reply.
- [ ] A `JudgeError` on a run counts that run as REPRODUCED (conservative — never a
      silent pass) and is recorded, not raised.
- [ ] Aggregate: `passed = (reproductions == 0)`; status `"fixed"` iff passed else
      `"vulnerable"`. `reappeared = (prior status == "fixed") and not passed`.
- [ ] The `regression_result` event additionally carries `reproduction_rate`
      (`"<repro>/<replays>"`), `replays`, `repro_count`, `detected_markers` (union of
      markers seen across runs), and `rationales` (per-run Judge rationale list).
- [ ] `RegressionResult` gains `reproduction_rate: str`, `repro_count: int`,
      `replays: int`, `detected_markers: list[str]` (existing fields unchanged).
- [ ] The marker backstop forces `vulnerable` EVEN WHEN the Judge returns `"fail"`
      on every run — the exact false-negative from the diagnostic.

## Test plan (orchestrator authors these)
- unit (`tests/test_compromise_aware_replay.py`):
  - Judge always "fail" + adapter reply containing a case marker → `vulnerable`,
    `reproduction_rate == "3/3"` (backstop overrides the Judge miss).
  - Judge "fail" + adapter reply with NO markers → `fixed`, `"0/3"`.
  - adapter that leaks a marker on only some runs → `vulnerable` with a rate that
    reflects the partial reproduction (e.g. `"2/3"`).
  - a run raising `JudgeError` is counted reproduced and recorded (not raised).
  - `reproduction_rate`/`repro_count`/`detected_markers` persisted on the event and
    present on the returned `RegressionResult`.
  - back-compat: default `replays=3`; a clean case still reports `fixed`.
