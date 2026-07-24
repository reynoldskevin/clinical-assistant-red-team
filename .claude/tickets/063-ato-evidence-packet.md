---
id: 063
title: ATO-style evidence packet
status: todo
depends_on: []
branch: ticket/063-ato-evidence-packet
base_branch: main
test_command: ".venv/bin/pytest tests/test_ato_packet.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Assemble an Authorization-To-Operate-style evidence packet that a reviewer could use to sign
off the platform: system description, trust-boundary map, control catalog, the evidence
artifacts already produced (threat model, architecture diagram, contract schemas, eval
results, AI-use disclosure), and residual-risk acceptance. Following the repo's established
doc-deliverable pattern (`test_threat_model_doc.py`, `test_decision_record.py`), the packet is
`ATO_EVIDENCE_PACKET.md` with a structural test that pins its required sections and that every
cited evidence artifact actually exists on disk (no dangling citations).

## Acceptance criteria
- [ ] `ATO_EVIDENCE_PACKET.md` exists at the repo root with, at minimum, sections: System
      Description, Trust Boundaries, Control Catalog (mapping controls to evidence), Evidence
      Artifacts (with links), Residual Risks & Acceptance, and Authorization Decision.
- [ ] The Control Catalog maps each named control to at least one concrete evidence artifact
      or code location; the test asserts the mapping is non-empty and well-formed.
- [ ] Every evidence artifact the packet cites as a repo file (e.g. `THREAT_MODEL.md`,
      `ARCHITECTURE_DIAGRAM.md`, `contracts/agent/`, `EVAL_RESULTS.md`, `AI_USE_DISCLOSURE.md`)
      actually exists on disk — the test resolves each cited path and fails on any missing one.
- [ ] The Residual Risks section lists at least three residual risks, each with an explicit
      acceptance/mitigation statement (honest limitations, not hand-waving).
- [ ] The packet is self-consistent with the platform (component/agent names match
      ARCHITECTURE.md) — the test spot-checks that the named agents appear.

## Test plan (orchestrator authors these)
- unit (`tests/test_ato_packet.py`):
  - all required sections present (headings).
  - control catalog table has >=1 control->evidence mapping rows.
  - every cited repo-relative artifact path resolves to an existing file.
  - >=3 residual risks each with an acceptance/mitigation line.
  - named agents (orchestrator/red_team/judge/documentation) appear in the packet.
