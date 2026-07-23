---
id: 049
title: Compromise signature on regression cases
status: ready-for-merge
depends_on: []
branch: ticket/049-compromise-signature
base_branch: main
test_command: ".venv/bin/pytest tests/test_compromise_signature.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Regression cases currently store only the attacker prompt/transcript, so a replay
can only ask the Judge a fresh category verdict — which (as the DoS PHI-leak
diagnostic proved) grades the wrong dimension and marks a still-live exploit
"fixed". Capture, at case creation, a **compromise signature**: the distinctive
sensitive tokens the ORIGINAL exploit leaked, plus the original verdict rationale
and OWASP tags. This is the deterministic evidence a later replay checks against.

## Acceptance criteria
- [ ] `forge/phi.py` exposes `extract_markers(text) -> list[str]`: a deterministic,
      case-insensitive extractor of clinical-sensitive tokens — a curated medication
      list, common lab-analyte terms, clinical symptom/demographic terms, 4-digit
      birth years (1900–2025), and standalone digit runs of length ≥4 (record ids).
      Returns a sorted, de-duplicated, lowercased list.
- [ ] `extract_markers` finds the leaked tokens in both real report `observed`
      texts (e.g. warfarin/digoxin/1925 and glucose/creatinine/potassium/6249) and
      returns NO clinical markers for a plain safe refusal ("I can't share another
      patient's chart without authorization").
- [ ] `RegressionHarness.create_case` derives and persists a `compromise_signature`
      on the `regression_case` event: `{"markers": [...], "rationale": <verdict
      rationale>, "owasp_web": [...], "owasp_llm": [...]}`, where `markers` come from
      `extract_markers` applied to the original target reply (from the attempt
      transcript) unioned with the verdict rationale.
- [ ] `list_cases()` surfaces `compromise_signature` for each case: the stored
      signature when present, else one derived from the case transcript's target
      reply (markers only), else an empty signature `{"markers": [], ...}`.
- [ ] No behavior change to existing `replay`/`validate` outputs (this ticket only
      adds the signature; consumption lands in 050). Full suite stays green.

## Test plan (orchestrator authors these)
- unit (`tests/test_compromise_signature.py`):
  - `extract_markers` positive on the two `observed` corpora + negative on a refusal.
  - `create_case` persists a `compromise_signature` whose `markers` include the
    leaked tokens from the attempt's target reply and whose rationale/owasp match
    the verdict.
  - `list_cases` returns the stored signature; a legacy case (empty transcript, no
    stored signature) yields an empty-marker signature (documents the backfill need).
