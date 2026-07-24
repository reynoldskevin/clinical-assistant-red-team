---
id: 069
title: Submission self-check + deterministic offline repro harness
status: todo
depends_on: []
branch: ticket/069-submission-selfcheck-repro
base_branch: main
test_command: ".venv/bin/pytest tests/test_submission_repro.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The original plan's ticket 022 (submission packaging & reproducibility) was never built; most of
its intent is covered organically (README run/deployed-URL sections, EVAL_RESULTS reproduce
line, a deterministic test suite), but two pieces are missing: an automated artifact-presence
check that fails if any submission deliverable goes missing, and a one-command deterministic
mock re-run that drives the full four-agent loop against an in-process fake target (no network,
no API key) with a stable, reproducible result. Add `forge/submission.py` providing both plus a
`python -m forge.submission` CLI, and cite the one command in the README.

## Acceptance criteria
- [ ] `forge.submission.REQUIRED_ARTIFACTS` lists the submission deliverables; `missing_artifacts(root=None) -> list[str]`
      returns the repo-relative paths that do not exist (root defaults to the repo root). On this
      repo it returns `[]`; pointed at an empty dir it reports the missing ones.
- [ ] `forge.submission.reproduce(cases=None) -> dict` runs the full deployed loop
      (`build_autonomous_runner` + `run_autonomous`) against BUILT-IN deterministic fakes (a mock
      target adapter, mock Red Team, mock Judge) — no network, no `ANTHROPIC_API_KEY`, no writes to
      the repo `reports/`. It returns a stable summary dict (e.g. `attempts`, `verdicts`,
      `exploits`, `defended`, `findings`, `passed`). Two successive calls return IDENTICAL dicts
      (determinism is the whole point).
- [ ] The mock Judge defends (verdict "fail") so the repro produces `exploits == 0`,
      `findings == 0`, `passed True`, and `attempts > 0` (the loop actually ran).
- [ ] `main(argv=None) -> int`: `--check` prints artifact status and returns non-zero iff any are
      missing; `--reproduce` prints the repro summary and returns 0; no args runs both.
- [ ] `README.md` cites the one-command self-check/repro (`python -m forge.submission`).
- [ ] Additive only; full suite stays green.

## Test plan (orchestrator authors these)
- unit (`tests/test_submission_repro.py`):
  - `missing_artifacts()` == [] on the real repo; `missing_artifacts(tmp_empty)` reports missing (incl. THREAT_MODEL.md).
  - `reproduce()` == `reproduce()` (deterministic); has the documented keys; `attempts > 0`,
    `exploits == 0`, `findings == 0`, `passed is True`; runs offline (no API key set).
  - `main(["--check"])` == 0 (all present); `main(["--reproduce"])` == 0.
  - README cites `forge.submission`.
