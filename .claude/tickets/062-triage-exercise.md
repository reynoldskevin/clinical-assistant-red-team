---
id: 062
title: Triage exercise — 10 findings across severities + dispositions
status: todo
depends_on: []
branch: ticket/062-triage-exercise
base_branch: main
test_command: ".venv/bin/pytest tests/test_triage_exercise.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The brief asks for a triage exercise: a curated set of at least 10 findings spanning
critical/high/medium and at least one deliberate false-positive, each with a triage
disposition (fix-now / fix-later / accept-risk / reject-false-positive) and justification.
Add a deterministic `forge/triage.py` that defines these findings as structured data and
renders `TRIAGE_EXERCISE.md`, so the deliverable is generated (not hand-maintained) and
test-verifiable. This exercises the Documentation agent's report taxonomy end-to-end,
including the "critical" and "false-positive" classes the live agent does not otherwise emit.

## Acceptance criteria
- [ ] `forge/triage.py` exposes the triage set as structured records (id, title, severity,
      owasp mapping, disposition, justification) and a `render_markdown()` producing
      `TRIAGE_EXERCISE.md` content.
- [ ] The set has >= 10 findings and covers ALL of: at least one `critical`, at least one
      `high`, at least one `medium`, and at least one `false-positive` disposition. Every
      finding has a non-empty justification and a disposition drawn from a fixed vocabulary.
- [ ] Each finding's severity is a valid `VulnReport` severity
      (critical/high/medium/low) and each references a real attack category used elsewhere in
      the platform (so the exercise is grounded, not invented).
- [ ] `TRIAGE_EXERCISE.md` is written to the repo root, contains a summary table plus a
      section per finding, and is regenerable idempotently from `triage.py` (rendering twice
      yields identical content).
- [ ] The generated doc and the structured set agree (the test renders and asserts the counts
      match the data — no drift between code and doc).

## Test plan (orchestrator authors these)
- unit (`tests/test_triage_exercise.py`):
  - triage set has >=10 findings; severity + disposition vocabularies enforced.
  - coverage: >=1 critical, >=1 high, >=1 medium, >=1 false-positive; every finding justified.
  - severities are valid VulnReport severities; categories are real platform categories.
  - render_markdown is deterministic (idempotent) and its counts match the structured set.
  - TRIAGE_EXERCISE.md exists at repo root and contains the summary table + per-finding sections.
