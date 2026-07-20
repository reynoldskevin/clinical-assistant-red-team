# Architecture — Agent Forge: Adversarial Evaluation Platform for the OpenEMR Clinical Co-Pilot

## Summary

Agent Forge is an autonomous, multi-agent adversarial evaluation platform that continuously
discovers, evaluates, validates, documents, and regression-tests security vulnerabilities in
an evolving LLM application — the OpenEMR **Clinical Co-Pilot**. It is deliberately *not* a
static test runner and *not* a single-agent pipeline. It is a coordinated system of agents with
distinct roles, trust levels, and decision authority, backed by deterministic tooling where
determinism matters.

Five agent/role boundaries carry the system. The **Orchestrator** is the strategist: it reads
the observability state (coverage gaps, open high-severity findings, recent regressions, spend)
and decides which attack surface the Red Team probes next, enforces cost budgets, halts or
redirects when spend accrues without signal, and triggers regression runs when the target
changes. The **Red Team Agent** is the offensive generator: it produces novel adversarial
inputs, *mutates* partially-successful attacks into variant families, and builds multi-turn
sequences — without a human choosing each next move. The **Judge Agent** is the independent
evaluator: it decides whether an attack succeeded, whether a defense held, and whether a
regression appeared, using a versioned rubric and calibration set that guard against drift. It is
architecturally separated from the Red Team — an agent that both generates and grades attacks
has a conflict of interest by design. The **Documentation Agent** converts Judge-confirmed
exploits into professional, reproducible vulnerability reports and enforces data-quality before
anything is written. A deterministic **Regression & Validation Harness** turns confirmed
exploits into repeatable cases, replays them on every target change, and detects both
reappearance and cross-category regressions.

Two deterministic substrates make the agents trustworthy. The **Target Adapter** is the single
boundary that talks to the live Co-Pilot — it holds credentials, records raw request/response
transcripts for exact replay, and isolates the platform from the target's specifics. The
**Observability Layer** (event log + metrics over a versioned SQLite **Exploit Store**) is both
the human's window and the Orchestrator's read-model: it answers which categories are tested and
how densely, the pass/fail rate across categories and target versions, whether the target is
getting more or less resilient, the lifecycle state of every finding, and what each run cost and
how cost is scaling.

Trust boundaries are explicit. The Red Team is sandboxed to the Target Adapter and cannot write
findings. The Judge is independent and its verdicts are the only path to a confirmed exploit.
The Documentation Agent may *draft* autonomously, but **publishing a finding or triggering any
remediation requires a human approval gate** — no agent pushes fixes. All roles run on Claude;
the offensive Red Team role uses authorized-security-testing framing to avoid refusals, with a
documented extension point to swap in a local/OSS model if refusals block coverage. Cost is a
first-class control: deterministic tooling is preferred over LLM calls wherever it is reliable
(replay, mutation templates, the harness), and the Orchestrator can throttle or stop. Inter-agent
messages are typed and versioned from day one so the optional `/contracts` schema publication and
error-schema deliverables attach without reworking mainline code.

## Goals & non-goals

**Goals** (traced to the brief)
- A genuine multi-agent system that *collectively* generates, mutates, evaluates, prioritizes,
  documents, and regression-tests adversarial attacks against a **live** Co-Pilot.
- Independent evaluation (Judge ≠ Red Team) with drift controls.
- Observability rich enough to *drive* orchestration, not just inform humans.
- Deliberate, defensible model/tooling choices under cost and refusal constraints.
- Explicit human trust gates around publication and remediation.
- OWASP Web Top 10 + OWASP LLM Top 10 coverage, each test case mapped to its OWASP category.

**Non-goals** (this milestone set)
- Not building the Co-Pilot from scratch (it exists; we attach and harden its testability).
- Not auto-remediating the target — the platform recommends; humans approve/apply.
- Optional deliverables (typed `/contracts` publication, ATO/integration packets, load/SQL-perf
  work, triage exercise, build-vs-configure record) are **backlog behind extension points**, not
  mainline scope.

## Requirements coverage

| Requirement (from brief) | Type | How the architecture satisfies it |
|---|---|---|
| Stand up target live + local; submit deployed URL | MVP S1 (hard gate) | **Target Adapter** attaches to the existing Co-Pilot; deployed to **Railway**; changes documented in README. |
| Map attack surface → `THREAT_MODEL.md` (6 categories) | MVP S2 (hard gate) | Threat surface enumerated in the Attack Taxonomy (below) and formalized in `THREAT_MODEL.md` as a Milestone-1 deliverable; drives Red Team categories + coverage metrics. |
| Initial attack suite `./evals/` ≥3 categories + ≥1 live agent | MVP S3 (hard gate) | `./evals/` seed dataset; **Red Team + Judge** run live against the target via the Adapter. |
| Architecture plan `./ARCHITECTURE.md` (~500w, named agents, diagram) | MVP S4 (hard gate) | **This document** + `ARCHITECTURE_DIAGRAM.md`. |
| Multi-agent (not single/pipeline); attack-gen ≠ evaluation | Platform | Distinct **Orchestrator / Red Team / Judge / Documentation** agents; Judge independent of Red Team. |
| Generate, mutate, multi-turn; consistent evaluation; prioritize; halt on no-signal; trigger regression | Platform | Red Team (generate/mutate/multi-turn) + Judge (consistent rubric) + Orchestrator (prioritize, budget-halt, regression trigger). |
| Per-role model choice under refusal/cost constraints | Platform | Claude per role; Red Team uses authorized-testing framing; **local/OSS swap = extension point**; deterministic tooling preferred to cut cost. |
| Documentation Agent → structured vuln reports | Platform | **Documentation Agent** with fixed report schema + data-quality gate. |
| Regression & Validation Harness (versioned store, reappearance, cross-category) | Platform | **Regression Harness** + versioned **SQLite Exploit Store**; Judge decides *meaningful* pass. |
| Observability Layer (the 6 questions) | Platform | **Observability Layer** event log + metrics; serves humans and the Orchestrator. |
| OWASP Web Top 10 + LLM Top 10, mapped per test case | Engineering (mandatory) | `owasp_web` / `owasp_llm` fields required on every eval case; coverage reported by OWASP category. |
| `USERS.md`, `THREAT_MODEL.md`, `./evals/`, ≥3 Vuln Reports, AI Cost Analysis | Submission | Each scheduled as a Milestone deliverable (see BUILD_PLAN). `ARCHITECTURE.md` = this doc. |

## Hard problems — how this design addresses each

### 1. Adversarial robustness (probe · mutate · escalate)
The **Red Team Agent** does not run a static payload list. Given an Orchestrator directive
(`category`, optional `seed`, `budget`), it generates novel inputs, and on a *partial* success
it autonomously spawns a **mutation family** (rephrasing, encoding, indirection, role-play,
multi-turn staging) to find the variant that breaks through. Whether an attempt is a "partial
success" worth mutating is the Judge's call, so escalation is evidence-driven, not guesswork.

### 2. Evaluation & regression (independent judge · no drift · real fixes)
The **Judge Agent** is a separate agent (separate context, separate system prompt, low
temperature) that never generates attacks. It applies a **versioned rubric** and returns
`{verdict, confidence, rationale, owasp_mapping}`. Drift is controlled three ways: (a) a fixed
**calibration set** of gold-labeled cases the Judge is re-scored against on every rubric change —
a shifted score on frozen inputs *is* drift; (b) an **invariant test**: the Judge must never mark
a previously-confirmed exploit as safe; (c) rubric changes are versioned with migration notes.
The Harness distinguishes a *real* fix from a behavior change by replaying the exact recorded
attack transcript and requiring the Judge to confirm the unsafe behavior is gone — not merely
that output differs.

### 3. Visibility & observability (drives orchestration)
Every agent action is written to an ordered **event log**; metrics are derived into the
Observability read-model. The **Orchestrator reads this model** to choose the next target: it
steers toward under-covered categories and open high-severity findings, and away from surfaces
that are spending tokens without producing signal. Without this layer the platform attacks
randomly; with it, it *learns where to look*.

### 4. Cost, scale & model constraints
Cost is a control input, not an afterthought. The Orchestrator enforces a **per-run and
per-directive budget** and halts/redirects on low signal-per-token. Deterministic tooling is
preferred wherever reliable — the Target Adapter, regression replay, and template-based mutation
seeds run with zero LLM cost; the LLM is spent on genuinely generative/evaluative steps. Model
tiers are chosen per role (cheaper models for high-volume Red Team generation, stronger for the
Judge). The **AI Cost Analysis** deliverable projects 100/1K/10K/100K runs and the architectural
changes each scale forces (batching, caching, local models, sampling coverage).

### 5. Discovery, remediation & trust
The **Documentation Agent** turns a confirmed exploit into a report a senior engineer who wasn't
present could reproduce and fix. Trust is bounded: Red Team → Target only (sandbox); Judge is the
sole path to "confirmed"; Documentation may draft autonomously but **publication and any
remediation trigger sit behind a human approval gate**. Confidence is always reported, and a
low-confidence or data-quality-failing report never auto-publishes.

### 6. Existing security research & industry practice
The threat model and eval taxonomy are grounded in **OWASP LLM Top 10** and **OWASP Web Top 10**
(mandatory engineering requirement) and reference established red-team practice (e.g. OWASP,
MITRE ATLAS, Garak-style probes). A **build-vs-configure decision record** (why a custom agent
over configuring Burp/ZAP/Semgrep/Garak) is an extension-point deliverable.

## Attack taxonomy (drives THREAT_MODEL.md, Red Team categories, coverage metrics)

Six mandated categories, each carrying attack-surface, impact, exploitation-difficulty, and
existing-defense fields, and each mapped to OWASP Web/LLM entries:
prompt injection (direct / indirect / multi-turn); data exfiltration (PHI leakage, cross-patient
exposure, authz bypass); state corruption (history manipulation, context poisoning); tool misuse
(unintended invocation, parameter tampering, recursive calls); denial of service (token
exhaustion, loops, cost amplification); identity & role exploitation (privilege escalation,
persona hijack, trust-boundary violation).

## Components

> Component names here match `ARCHITECTURE_DIAGRAM.md` exactly.

- **Orchestrator Agent** — *Strategy.* In: observability read-model, target-version change events.
  Out: `AttackDirective` to Red Team, `RegressionTrigger` to Harness. Trust: high (controls flow)
  but bounded by budget policy; cannot approve its own remediations. Largely deterministic policy
  with an LLM assist only for ambiguous prioritization (cost control).
- **Red Team Agent** — *Offense.* In: `AttackDirective`. Out: `AttackAttempt` (full transcript) to
  Judge. Trust: sandboxed — may call the Target *only* via the Target Adapter; cannot write
  findings or read the exploit store. Claude with authorized-security-testing framing.
- **Judge Agent** — *Evaluation.* In: `AttackAttempt` (and replayed regression transcripts). Out:
  `Verdict` (`success|fail|partial`, confidence, rationale, OWASP mapping) to Orchestrator and, on
  confirmed success, to Documentation. Trust: independent authority; the only producer of
  "confirmed exploit". Versioned rubric + calibration set.
- **Documentation Agent** — *Reporting.* In: confirmed `Verdict` + transcript. Out: `VulnReport`
  (draft) to the store + `./reports/`. Trust: may draft; **publication/remediation gated by human
  approval**. Enforces data-quality (required fields, uniqueness) before writing.
- **Regression & Validation Harness** — *Deterministic.* In: `RegressionTrigger`, confirmed
  exploits. Out: pass/fail + regression/reappearance flags. Replays recorded transcripts via the
  Adapter and asks the Judge for verdicts (meaningful pass, not behavior change).
- **Target Adapter** — *Deterministic boundary.* The only egress to the live Co-Pilot. Holds
  target credentials, normalizes the HTTP/chat contract (single- and multi-turn), records raw
  request/response for replay. (Exact Co-Pilot contract pinned in an early ticket.) **Enforces a
  target allowlist** — a run names a pre-registered target by id, never a raw URL from an agent, so
  an agent cannot redirect the platform at a system it must not attack.
- **Observability Layer + Exploit Store (SQLite)** — *Data substrate.* Versioned, migration-aware
  schema: `findings`, `regression_cases`, `attack_attempts`, `events`, `coverage`, `cost`.
  Indexed by severity / attack-category / target-version. Serves the Orchestrator and humans. The
  domain read-model (findings/coverage/regression/cost) lives here; **agent-level execution traces
  — per-agent spans, token/cost/latency, and finding→agent lineage — go to a self-hosted Langfuse**
  (see tradeoffs). The `events` table is **append-only**, serving as the audit trail for autonomous
  runs.

## Interfaces & data flow

Inter-agent messages are **typed (Pydantic) and versioned (`schema_version`, min `v1`)** from the
start: `AttackDirective` (Orchestrator→RedTeam), `AttackAttempt` (RedTeam→Judge), `Verdict`
(Judge→Orchestrator, Judge→Documentation), `RegressionTrigger` (Orchestrator→Harness),
`VulnReport` (Documentation→Store). Each also defines a **typed error result** for its known
failure modes (target unreachable, budget exceeded, judge timeout, no findings in window,
regression detected). LangGraph holds run/agent state with checkpointing so runs are resumable.
Publishing these schemas to `/contracts` as JSON Schema and adding cross-agent contract tests is
an extension point — the schemas already exist as versioned models, so it is additive.

## Cross-cutting concerns

- **Security / OWASP (mandatory):** every eval case carries `owasp_web` and/or `owasp_llm`; the
  suite must cover the mandated Web (broken access control, injection, insecure design, vulnerable
  components, auth failures, logging failures, SSRF) and LLM (prompt injection, insecure output
  handling, sensitive info disclosure, excessive agency, supply-chain) entries. Coverage is
  reported per OWASP category.
- **Observability (platform):** the layer must answer, at any time: categories tested + case count
  each; pass/fail rate across categories and target versions; resilience trend over versions; open
  / in-progress / resolved findings; run cost + scaling rate; per-agent activity in order.
- **Cost/scale (platform):** budget enforcement + halt-on-no-signal in the Orchestrator;
  deterministic-first; per-role model tiers; caching/batching as scale grows.
- **Regression integrity (platform):** a regression passes only when the Judge confirms the unsafe
  behavior is genuinely absent on the replayed transcript, never merely because output changed.
- **Trust boundaries:** Red Team → Target only; Judge independent; human gate before
  publish/remediate; no agent applies fixes.

## Platform trust, safety & operations

*(Added after a pre-build checklist review — this dimension was under-specified in the first draft.)*

- **Platform self-safety (don't attack the wrong thing).** The Adapter's **target allowlist** is the
  hard control: agents reference a target by id; only pre-registered targets are reachable. Runs are
  triggered by an **authenticated operator** (API-key/CLI token at MVP; operator-vs-viewer roles as
  an extension). Report reads are access-controlled. Every trigger and every agent action is written
  to the append-only `events` log — the audit trail for overnight/autonomous runs.
- **Healthcare data & PHI.** The platform runs **only against a non-production target seeded with
  synthetic patient data** — no real PHI. This bounds the blast radius of both exfiltration attacks
  and any harmful content the Red Team elicits. Transcripts may still contain sensitive-looking
  model output, so the store is access-controlled with a stated retention policy, and traces stay
  **in-environment** (self-hosted Langfuse, not a hosted SaaS).
- **Reliability bias — false negatives cost more than false positives.** A missed vulnerability is
  worse than a flagged-but-safe one here. So the **Judge escalates low-confidence verdicts to human
  review** rather than silently passing; coverage favors recall; false positives are absorbed by the
  human approval + data-quality gates. Critical/high reports require explicit human approval before
  publish (**severity-aware gate**).
- **Failure handling & recovery.** Each typed agent error maps to a policy: transient (target
  unreachable, judge timeout, rate limit) → bounded retry-with-backoff → skip/redirect; hard (budget
  exceeded, no-signal) → Orchestrator redirects or halts. A **circuit breaker** aborts a run after K
  agent failures and surfaces it to the operator. The Orchestrator's **no-clear-priority fallback**
  is round-robin over the least-covered categories; if all are at target coverage or the budget is
  spent, it stops cleanly.
- **Testing the tester (platform self-regression).** A fixed **platform-invariant suite** runs each
  build: the Judge invariant (never pass a confirmed exploit), calibration-set stability, **Red Team
  novelty** (a new attack must differ from stored attempts by a similarity threshold — guards against
  the generator going stale), and message-contract conformance. Regression here means the *platform*
  degraded, distinct from target regression.
- **Operational scale.** Campaigns run sequentially by default; concurrency is a scale lever behind a
  cap, always subject to the target's own rate limits via the Adapter. Latency / throughput / volume
  targets are set from M1 baselines and feed the AI Cost Analysis.

## Open questions to resolve during the build

- **Per-category success criteria** — the Judge rubric needs an explicit, testable definition of
  success/fail/partial *per attack category*, not just a general rubric.
- **Coverage-sufficiency** — what marks a category "sufficiently covered" so the Orchestrator moves on.
- **Context-window budget** for long multi-turn attack sequences.
- **Time-based regression trigger** in addition to deploy-triggered runs.
- Plus the earlier open items: target contract shape, Claude refusal rate, Judge calibration
  threshold & single-vs-panel, halt-on-no-signal thresholds.

## Extension points (optional / future deliverables — designed for, not built now)

Each optional brief deliverable attaches at a named seam so it can be added **without reworking
mainline code**:

- **`/contracts` JSON-Schema publication + contract tests** ← messages are already versioned
  Pydantic models; export + dual-side tests attach at the message layer.
- **Explicit error schemas / API versioning** ← typed error results + `schema_version` already
  present; publish alongside success schemas.
- **Data-quality checks, SQL indexing/perf, migrations, batch jobs** ← Exploit Store already
  versioned & indexed; add constraints/SLO checks at the store layer.
- **Build-vs-configure decision record; triage exercise (10 mixed findings)** ← attach at the
  Documentation Agent (report format already structured).
- **ATO-style evidence packet; integration packet; AI-use disclosure** ← draw from existing
  diagrams, schemas, trust-boundary map, and eval evidence.
- **Baseline profiles + load/stress test (100 cases)** ← Observability already records latency/
  throughput/cost; add a baseline-capture run and a load harness over the same metrics.
- **Local/OSS model for the Red Team role** ← model is a per-role config behind an LLM-client
  interface; swap without touching agent logic (mitigates frontier refusal at scale).

## AI-use disclosure

LLM (Claude) powers the Red Team (generation/mutation), Judge (evaluation), Documentation
(report prose), and — minimally — the Orchestrator (ambiguous prioritization only). Every AI
decision is followed by a deterministic or human check: Red Team output is evaluated by the
independent Judge; Judge verdicts are guarded by the calibration set + invariant test; Documentation
output passes a data-quality gate and a **human approval gate** before publication; Orchestrator
actions are bounded by budget policy. Residual risk: a drifting Judge (mitigated, not eliminated,
by calibration) and Red Team refusals under Claude-only (mitigated by authorized-testing framing +
the local/OSS extension point).

## Key tradeoffs & alternatives considered

- **Custom agents over configuring an off-the-shelf scanner (Garak/ZAP/Burp):** those tools are
  strong at deterministic/protocol probing but weak at *adaptive, evidence-driven mutation and
  multi-turn* attacks and at *independent LLM-judged* evaluation — the core of this brief. We use
  deterministic tooling *inside* the platform (adapter, replay) and reserve agents for the
  adaptive work. (Full record = backlog deliverable.)
- **Claude-only vs multi-provider:** simpler, one auth/rate model, strong Judge — at the cost of
  Red Team refusal risk; mitigated by framing + a local/OSS swap seam rather than adopting a
  second provider now.
- **SQLite vs Postgres:** SQLite is fastest to stand up and satisfies the SQL indexing/migration
  optionals; Postgres deferred behind the same store interface if scale demands it.
- **Independent Judge vs shared generator/evaluator:** independence costs extra LLM calls but is
  non-negotiable — a self-grading attacker is compromised by design.
- **Observability tooling — self-hosted Langfuse for traces + SQLite for domain data (vs LangSmith /
  Braintrust / all-custom):** we split the two concerns. Agent *execution traces* (spans, per-agent
  token/cost/latency, finding→agent lineage) go to **Langfuse, self-hosted** — it's open-source,
  LangGraph-compatible, and keeps trace data (which can contain sensitive model output) **in our
  environment**. **LangSmith was rejected** for mainline: it's a hosted SaaS, so transcripts would
  leave the environment — unacceptable against a healthcare target. **Braintrust** is eval-centric,
  not built for inter-agent execution tracing. The *domain* read-model (findings, coverage,
  regression, cost rollups — what the Orchestrator steers by) stays in **SQLite**; adopting Langfuse
  for traces is what closes the agent-level-cost and finding-lineage gaps without hand-rolling a
  tracer. (Earlier drafts implied an all-custom observability layer; this is the correction.)
