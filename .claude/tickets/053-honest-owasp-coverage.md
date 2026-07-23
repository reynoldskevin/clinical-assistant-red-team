---
id: 053
title: Honest OWASP coverage from Judge-observed tags
status: todo
depends_on: []
branch: ticket/053-honest-owasp-coverage
base_branch: main
test_command: ".venv/bin/pytest tests/test_owasp_coverage_metric.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
OWASP coverage is currently the static case-catalog cross-product: `by_owasp[id]
+= attempts_in_category` for every EvalCase tagged with `id`. Since every category
is floored at the same attempt count, the score just rewards how many seed cases
carry a tag — not what was actually exercised. Make it honest: persist the Judge's
per-attempt `owasp_web`/`owasp_llm` on the verdict event (today they're dropped for
non-exploits) and count distinct verdicts per OWASP id from THOSE tags. Coverage
then reflects what the run genuinely elicited, independent of the catalog.

## Acceptance criteria
- [ ] The `verdict` event written by the Runner carries `owasp_web` and `owasp_llm`
      (the Judge's tags for that attempt) in addition to its existing fields.
- [ ] `Observability.coverage()` computes `by_owasp` by counting, per OWASP id, the
      number of `verdict` events whose `owasp_web`/`owasp_llm` include that id. An id
      present in BOTH lists of one verdict counts ONCE for that verdict. `by_category`
      is unchanged (verdict count per category).
- [ ] `by_owasp` no longer depends on the `cases` catalog — the result is identical
      with or without `cases` passed to `Observability`.
- [ ] A verdict with no OWASP tags contributes to `by_category` only.
- [ ] Contract/round-trip: driving the Runner (Red Team → Judge) with a Judge that
      returns specific tags yields verdict events carrying those tags AND a
      `coverage().by_owasp` that counts them.
- [ ] The obsolete `test_observability.py` coverage tests are updated to the new
      semantics (done by the orchestrator when authoring tests, not the implementer).

## Test plan (orchestrator authors these)
- unit (`tests/test_owasp_coverage_metric.py`):
  - `coverage().by_owasp` counts verdicts per id from verdict-event tags; distinct
    ids per verdict counted once; untagged verdict → category only.
  - `by_owasp` independent of the `cases` catalog.
  - producer + round-trip: a `Runner.run_autonomous` cycle with a tagging Judge
    writes `owasp_web`/`owasp_llm` on the verdict event, and `coverage()` reflects them.
- update `tests/test_observability.py`: replace the static-catalog `by_owasp`
  assertions with Judge-tag-based expectations (tags seeded on the verdict events).
