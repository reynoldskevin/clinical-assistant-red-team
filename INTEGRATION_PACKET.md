# Integration Packet — Agent Forge Adversarial Evaluation Platform

**Subject:** How the platform's autonomous agents integrate — the typed message
interfaces between them, the versioned contracts that pin those interfaces, the
contract tests that prove producer/consumer agreement, the decision records
behind the design, and a concrete cross-agent execution trace.

**Scope of integration:** Agent Forge is a coordinated multi-agent system, not a
pipeline of function calls. Four LLM-backed agents (Orchestrator, Red Team,
Judge, Documentation) plus deterministic substrates (Target Adapter, Regression
Harness, Observability/Exploit Store, Tracer) cooperate by exchanging **typed,
versioned Pydantic messages**. This packet is the single place that ties the
interface layer, the published schemas, the tests, and the runtime lineage
together. It draws on `ARCHITECTURE.md`, `forge/schemas.py`, `forge/contracts.py`,
`forge/tracing.py`, and `DECISION_RECORD_BUILD_VS_CONFIGURE.md`.

---

## Component Interfaces

Every inter-agent boundary is crossed by exactly one typed message model. The
models are defined in `forge/schemas.py` and registered — snake_case name to
model class — in the `AGENT_MESSAGES` registry in `forge/contracts.py`. The
registry is the authoritative list of interfaces; the platform recognizes six
core inter-agent messages, documented below with their **producer**, their
**consumer(s)**, and their **role**.

| Message model | Registry key | Produced by | Consumed by | Role at the boundary |
|---|---|---|---|---|
| `AttackDirective` | `attack_directive` | Orchestrator | Red Team | Tasking: names the attack `category`, an optional `seed`, and the `max_attempts` / `max_cost_usd` budget the Red Team must stay within. |
| `AttackAttempt` | `attack_attempt` | Red Team | Judge | Evidence: the generated `prompt`, `category`, `target_id`, turn count, and full `transcript` of the exchange with the Co-Pilot, handed to the independent evaluator. |
| `Verdict` | `verdict` | Judge | Documentation, Regression Harness, Observability read-model | Ruling: `success` / `fail` / `partial` with `confidence`, `rationale`, `owasp_web` + `owasp_llm` mapping, and `rubric_version`. The only path to a "confirmed" exploit. Documentation drafts a `VulnReport` from it, the Regression Harness stamps a compromise signature into a new case, and the Orchestrator steers off the persisted verdict events via the Observability read-model (not the typed object directly). |
| `RegressionTrigger` | `regression_trigger` | Orchestrator | Regression & Validation Harness | Control: requests a regression run, tagged with `reason` (`target_version_change` / `time_window` / `manual`), `target_id`, and optional `target_version`. |
| `VulnReport` | `vuln_report` | Documentation | Exploit Store (`./reports/`) | Product: the structured, reproducible finding — `id`, `severity`, `clinical_impact`, `reproduction`, `observed`, `expected`, `remediation`, lifecycle `status`. |
| `ErrorResult` | `error_result` | Any agent | `FailurePolicy` / `CircuitBreaker` (`forge/failure.py`) | Typed failure: an `error_type` from the known set (`target_unreachable`, `budget_exceeded`, `judge_timeout`, `no_findings_in_window`, `regression_detected`) plus `detail`, so failures route to policy rather than crashing a run. |

### The interface flow

The messages compose into the platform's core adversarial loop:

1. **Orchestrator → Red Team** — `AttackDirective`. The strategist reads the
   observability read-model and directs the offensive agent at the next attack
   surface, bounded by budget.
2. **Red Team → Judge** — `AttackAttempt`. The Red Team generates and (on a
   partial success) mutates adversarial inputs against the live Co-Pilot via the
   Target Adapter, and hands the full transcript to the independent Judge. The
   Red Team is sandboxed — it cannot write findings.
3. **Judge → Orchestrator / Documentation** — `Verdict`. The Judge, which never
   generates attacks, rules on the attempt with a versioned rubric. A confirmed
   `success` verdict flows to the Documentation Agent; every verdict informs the
   Orchestrator's next directive.
4. **Documentation → Store** — `VulnReport`. A confirmed verdict plus transcript
   becomes a reproducible report, subject to a data-quality gate and a human
   approval gate before publication.
5. **Orchestrator → Harness** — `RegressionTrigger`. On a target-version change
   (or a time window / manual request) the Orchestrator triggers the
   deterministic harness to replay confirmed exploits.
6. **Any agent → policy** — `ErrorResult`. Known failure modes are typed so the
   Orchestrator can apply retry/redirect/halt policy deterministically.

Every model carries a `schema_version` field (default `"v1"`) and round-trips
losslessly through `model_dump()` / `model_dump_json()`, so a producer's payload
reconstructs exactly on the consumer side.

---

## Contracts & Versioning

The Pydantic models are the live contract; their **published JSON Schema
artifacts** are the wire contract other services and tests validate against.
Both are versioned so an interface change is a deliberate, reviewable event.

**Published schemas.** `python -m forge.contracts` (the `write_all()` entry
point in `forge/contracts.py`) exports each registered model's
`model_json_schema()` to a committed artifact under `contracts/agent/`. One file
per message:

- `contracts/agent/attack_directive.schema.json`
- `contracts/agent/attack_attempt.schema.json`
- `contracts/agent/verdict.schema.json`
- `contracts/agent/regression_trigger.schema.json`
- `contracts/agent/vuln_report.schema.json`
- `contracts/agent/error_result.schema.json`

**Version field.** Every message model declares `schema_version: str = "v1"`, so
the contract version travels *with the payload on the wire* — a consumer can
branch on version without out-of-band coordination. `v1` is the current version.

**Migration policy** (from `contracts/agent/README.md`): a **breaking change
requires a version bump plus a migration note**. The procedure is: bump the
`schema_version` default on the model, document the change and its migration path
in `contracts/agent/README.md`, then regenerate the artifacts with
`python -m forge.contracts` and commit them. Because the published schema is
regenerated from the live model, the two can never silently diverge — the drift
test (below) fails the build if a model changes without a matching re-export.

This layer was designed as an **extension point** in `ARCHITECTURE.md`: the
inter-agent messages were typed and versioned from day one specifically so that
publishing `/contracts` as JSON Schema and adding cross-agent contract tests
would be additive, with no rework of mainline agent code.

---

## Contract-Test Results

The contract between producers and consumers is proven by the locked acceptance
suite `tests/test_agent_contracts.py`. It exercises the registry, the published
schemas, drift, and dual-side conformance. What it proves:

- **Registry completeness** — `test_registry_lists_the_inter_agent_message_models`
  asserts at least the six core inter-agent messages are registered and each maps
  to a `pydantic.BaseModel` subclass.
- **Every message is published and versioned** —
  `test_every_message_has_a_published_schema_file` asserts each registered
  message has a schema file under `contracts/agent/` whose `properties` include
  `schema_version`.
- **Schemas live where the contract says** —
  `test_published_schemas_live_under_contracts_agent` pins the publication
  directory to `contracts/agent/`.
- **No drift (the key guarantee)** —
  `test_no_schema_drift_between_committed_and_live_model` and
  `test_published_schema_matches_model_json_schema_each` assert the committed JSON
  Schema equals what the live Pydantic model emits *now*. If a model changes and
  the artifact is not regenerated, the build fails — doc and code cannot drift.
- **Dual-side conformance** — `test_dual_side_conformance_for_valid_payloads`
  proves both sides of every boundary: the **producer** side (a valid payload has
  no missing required fields per the *published* contract, via `validate_payload`)
  and the **consumer** side (the model reconstructs and round-trips the payload).
- **Required fields are enforced** — `test_missing_required_field_is_flagged`
  shows a dropped required field (`Verdict.rationale`) is both flagged by the
  producer-side check and rejected by Pydantic validation.
- **Unknown messages fail closed** — `test_unknown_message_name_raises`.
- **Versioning policy is documented** — `test_versioning_policy_doc_present`
  asserts `contracts/agent/README.md` covers `v1`, versioning, and migration.

Net result: the interfaces documented in this packet are not aspirational — a
green `tests/test_agent_contracts.py` run mechanically proves that every
registered message has a published, version-stamped schema that matches its live
model and accepts/rejects payloads exactly as the producer and consumer expect.

---

## Decision Records

The integration design is grounded in explicit decision records that a reviewer
can cross-check.

**`DECISION_RECORD_BUILD_VS_CONFIGURE.md`** answers the blunt reviewer question —
*"you are attacking an HTTP-fronted LLM; why not just configure an existing
scanner?"* It evaluates Burp Suite, OWASP ZAP, Semgrep, Garak, and commercial
LLM red-team platforms by hand, and records a per-role verdict. The outcome is
**"build the agents, configure the substrate":** the four core roles (Red Team,
Judge, Orchestrator, Documentation) are **Build**, because no off-the-shelf tool
does adaptive mutation of partial successes, multi-turn staging, or independent
versioned/calibrated LLM judgment over clinical PHI/authz boundaries — while the
deterministic substrates (Target Adapter HTTP/replay layer, JSON-Schema/Pydantic
contract validation, Regression Harness, SQLite store) are **Configure/reuse**.
This decision is *why* the integration surface looks the way it does: typed
messages and schema validation are the reused deterministic seams *between* the
custom agents, keeping cost a first-class control.

**`ARCHITECTURE.md`** carries the complementary tradeoffs that shape integration:
the independent-Judge boundary (a self-grading attacker is compromised by design),
the split observability model (self-hosted Langfuse for agent execution traces vs
SQLite for the domain read-model, with LangSmith rejected on data-residency
grounds), and the explicit trust boundaries (Red Team → Target only; human gate
before publish/remediate). The companion diagram is
`ARCHITECTURE_DIAGRAM.md`, and the attack taxonomy driving the message
`category` fields is formalized in `THREAT_MODEL.md`.

---

## Cross-Agent Trace

The message interfaces above describe *what* crosses each boundary. The **Tracer**
in `forge/tracing.py` records *that* the crossings happened, in order, and lets a
confirmed finding be resolved back to the exact ordered sequence of agents that
produced it — the finding→agent lineage.

For a confirmed finding, the ordered lineage is:

`red_team -> judge -> documentation`

This is the concrete integration path a single finding travels: the **Red Team**
produces the `AttackAttempt`, the **Judge** rules it a confirmed `success`
`Verdict`, and the **Documentation** agent turns that into a `VulnReport`. The
Orchestrator directs and budgets the loop, but the finding's *causal* lineage —
the agents whose work is attributable to that specific finding — is exactly these
three steps.

This ordering is not asserted in prose alone; it is what the code yields.
`Tracer.record(agent, trace_id=..., finding_id=...)` emits one `Span` per agent
step (mirroring Langfuse span semantics and, when a store is attached, appending a
`trace_span` event to the append-only event log). `Tracer.lineage(finding_id)`
collects every span on the trace(s) that carry that `finding_id`, in the order
they were recorded. Recording `red_team`, then `judge`, then `documentation`
against one `finding_id` and reading back `[s.agent for s in tr.lineage(fid)]`
therefore reproduces the chain above exactly — the packet's stated order and the
runtime lineage cannot drift apart. The deterministic behavior of this seam is
locked by `tests/test_tracing.py`, and the no-drift assertion between this
document and `Tracer.lineage` is enforced by `tests/test_integration_packet.py`.

`Tracer` also rolls per-agent cost up via `cost_by_agent()`, so the same lineage
that answers "which agents produced this finding" also answers "what did each
agent step cost" — closing the agent-level cost and finding-lineage gaps called
out in `ARCHITECTURE.md`.
