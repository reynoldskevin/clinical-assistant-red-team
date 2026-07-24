---
id: 064
title: Integration packet — interfaces, ADRs, contract results, cross-agent trace
status: todo
depends_on: []
branch: ticket/064-integration-packet
base_branch: main
test_command: ".venv/bin/pytest tests/test_integration_packet.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Assemble an integration packet documenting how the components fit together: the inter-agent
message interfaces (the versioned Pydantic contracts + published JSON schemas), the
architecture decision records, the contract-test results that prove producer/consumer
agreement, and a concrete cross-agent trace (red_team -> judge -> documentation) drawn from
`forge/tracing.py::Tracer.lineage`. Delivered as `INTEGRATION_PACKET.md` with a structural test
(repo doc-test pattern) that pins its sections, verifies the boundary/contract coverage, and
asserts the documented cross-agent trace order matches what `tracing.lineage` actually yields.

## Acceptance criteria
- [ ] `INTEGRATION_PACKET.md` exists at repo root with sections: Component Interfaces (the
      inter-agent messages + where each is produced/consumed), Contracts & Versioning (schema
      files + version policy), Contract-Test Results (which tests prove agreement), Decision
      Records (ADR links/summaries), and Cross-Agent Trace (an ordered lineage example).
- [ ] The Component Interfaces section covers every registered inter-agent message model (the
      names in `forge.contracts` registry) — the test asserts each registered message name is
      documented.
- [ ] The Cross-Agent Trace section documents the ordered lineage
      `red_team -> judge -> documentation`; the test builds a trace via `forge.tracing` and
      asserts the packet's stated order equals `Tracer.lineage(...)` agents (no drift between
      doc and code).
- [ ] The Contract-Test Results section names the actual contract test(s)
      (`tests/test_agent_contracts.py`) and those test IDs exist; the Decision Records section
      cites `DECISION_RECORD_BUILD_VS_CONFIGURE.md`, which exists on disk.
- [ ] Every repo-relative artifact the packet cites resolves to an existing file.

## Test plan (orchestrator authors these)
- unit (`tests/test_integration_packet.py`):
  - all required sections present.
  - every registered message model name (forge.contracts registry) appears in the interfaces section.
  - packet's cross-agent trace order == agents from a real forge.tracing lineage (red_team->judge->documentation).
  - cited contract test file + decision record + other cited paths all exist on disk.
