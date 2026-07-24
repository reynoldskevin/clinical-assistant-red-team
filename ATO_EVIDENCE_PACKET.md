# Authorization-To-Operate (ATO) Evidence Packet — Agent Forge Adversarial Platform

**System:** Agent Forge — Autonomous Multi-Agent Adversarial Evaluation Platform
**Subject under authorization:** the *platform itself* (the red-team system), operating against
the OpenEMR AI Clinical Co-Pilot sidecar (the target under test).
**Packet owner:** Platform engineering
**Date:** 2026-07-23
**Decision requested:** Authority to Operate the platform in continuous / overnight-autonomous
mode against the pre-registered non-production sidecar target.

This packet is the single artifact a security reviewer can read to decide whether the platform is
safe to run autonomously. It states what the system is, where its trust boundaries lie, which
controls enforce those boundaries, where the evidence for each control lives on disk, which risks
remain, and the resulting authorization decision. Every cited artifact is a real file in this
repository; there are no forward-looking or aspirational citations.

---

## System Description

Agent Forge is an autonomous, multi-agent adversarial evaluation platform that continuously
discovers, evaluates, validates, documents, and regression-tests security vulnerabilities in a
live LLM application — the OpenEMR **Clinical Co-Pilot** sidecar. It is *not* a static payload
runner and *not* a single-agent pipeline: it is a coordinated set of agents with distinct roles,
trust levels, and decision authority, backed by deterministic tooling wherever determinism
matters. The authoritative description is `ARCHITECTURE.md`, with the component/data-flow diagram
in `ARCHITECTURE_DIAGRAM.md` and the adversarial surface in `THREAT_MODEL.md`.

Four LLM-backed agents and two deterministic substrates carry the system:

- **Orchestrator** (`forge/orchestrator.py`) — the strategist. Reads the observability
  read-model (coverage gaps, open high-severity findings, recent regressions, spend), chooses
  which attack surface is probed next, enforces per-run and per-directive cost budgets, halts or
  redirects on low signal-per-token, and triggers regression runs when the target changes. It is
  largely deterministic policy with an LLM assist only for ambiguous prioritization.
- **Red Team** (`forge/red_team.py`) — the offensive generator. Given an `AttackDirective`, it
  produces novel adversarial inputs, mutates partial successes into variant families, and stages
  multi-turn sequences. It is **sandboxed**: it may reach the target *only* through the Target
  Adapter and cannot write findings or read the exploit store.
- **Judge** (`forge/judge.py`) — the independent evaluator. It decides whether an attack
  succeeded, whether a defense held, and whether a regression appeared, using a versioned rubric
  and a frozen calibration set. It is architecturally separated from the Red Team — a generator
  that also grades its own attacks is compromised by design — and it is the *sole* producer of a
  "confirmed exploit".
- **Documentation** (`forge/documentation.py`) — the reporter. It converts Judge-confirmed
  exploits into reproducible vulnerability reports and enforces a data-quality gate before
  writing. It may *draft* autonomously, but **publication and any remediation trigger sit behind
  a human approval gate**.
- **Regression & Validation Harness** (`forge/regression.py`) — deterministic. Turns confirmed
  exploits into repeatable cases, replays the exact recorded transcript on each target change,
  and distinguishes a genuine fix (Judge confirms the unsafe behavior is gone) from a mere
  behavior change.
- **Target Adapter** (`forge/target.py`) — the single, deterministic egress to the live sidecar.
  It resolves a target *id* against an allowlist (never a raw URL from an agent), holds
  credentials, and records a redacted transcript of every call.
- **Observability + Exploit Store** (`forge/observability.py`, `forge/store.py`,
  `forge/tracing.py`) — the versioned SQLite domain read-model plus a Langfuse-shaped span tracer;
  the human's window and the Orchestrator's read-model, with an append-only `events` audit trail.

The target is a non-production sidecar seeded exclusively with synthetic Synthea data (no real
PHI); its wire contract is pinned in `contracts/README.md` and the request/response schemas under
`contracts/`.

---

## Trust Boundaries

The design places a hard line between deterministic, trusted machinery and probabilistic,
untrusted machinery. The boundaries below match `ARCHITECTURE.md` and `ARCHITECTURE_DIAGRAM.md`.

1. **Platform ↔ live target (single egress).** All outbound traffic to the Co-Pilot flows through
   one chokepoint, `forge/target.py`. Agents never hold a URL; they name a pre-registered target
   *id* that `forge/access.py` resolves against an allowlist. This forecloses SSRF /
   redirect-the-run: an agent cannot point the platform at a system it must not attack.

2. **Red Team ↔ everything else (sandbox).** The Red Team is trust-minimized: it can call the
   target through the Adapter and nothing else. It cannot write findings, cannot read the exploit
   store, and cannot influence the verdict on its own output. This is the primary containment for
   a Red Team that has been prompt-injected by retrieved target content.

3. **Generation ↔ evaluation (independence).** The Judge runs in a separate context with a
   separate system prompt and a versioned rubric, and never generates attacks. Only a Judge
   verdict promotes an attempt to "confirmed exploit". Generator and grader are never the same
   agent.

4. **Autonomy ↔ human authority (approval gate).** Agents may generate, evaluate, and *draft*
   without a human in the loop, but **publishing a finding or triggering any remediation requires
   a human approval gate**. No agent applies a fix. Low-confidence Judge verdicts escalate to
   human review rather than silently passing (false-negative-averse posture).

5. **Real vs synthetic data (blast-radius bound).** The platform runs only against a
   non-production target seeded with synthetic patient data. This bounds the blast radius of both
   exfiltration attacks and any harmful content the Red Team elicits. Transcripts may still
   contain sensitive-looking model output, so the store is access-controlled and traces stay
   in-environment (self-hosted Langfuse, not hosted SaaS).

6. **Operator ↔ platform (authenticated trigger).** A run is initiated by an authenticated
   operator (token via `forge/access.py`); every trigger and every agent action is appended to the
   `events` audit log, which is append-only at the DB level (UPDATE/DELETE blocked by triggers).

7. **Deterministic ↔ AI components.** Determinism is preferred wherever it is reliable: the
   Adapter, regression replay, the compromise-marker check (`forge/phi.py`), the allowlist/audit
   primitives (`forge/access.py`), and message schemas (`forge/schemas.py`, `forge/contracts.py`)
   are deterministic and independently testable. The LLM budget is spent only on genuinely
   generative or evaluative steps.

---

## Control Catalog

Each row names a control, states what it enforces, and points to the concrete code and/or test
that is the evidence for it. All cited paths exist in this repository.

| # | Control | What it enforces | Evidence (code) | Evidence (test) |
|---|---------|------------------|-----------------|-----------------|
| C1 | Target allowlist (no raw URLs) | Agents name a pre-registered target id only; blocks SSRF / redirect-the-run | `forge/access.py`, `forge/target.py` | `tests/test_access_control.py` |
| C2 | Operator authentication for run triggers | Only an authenticated operator can start a run | `forge/access.py` | `tests/test_access_control.py` |
| C3 | Append-only audit trail | Every trigger/agent action is recorded; UPDATE/DELETE blocked at DB level | `forge/access.py`, `forge/store.py` | `tests/test_access_control.py`, `tests/test_observability.py` |
| C4 | Red Team sandbox (single egress) | Red Team reaches only the target, via the Adapter; cannot write findings | `forge/target.py`, `forge/red_team.py` | `tests/test_red_team.py`, `tests/test_orchestrator_run_scope.py` |
| C5 | Independent Judge (generator ≠ grader) | Only a separate Judge promotes an attempt to "confirmed" | `forge/judge.py` | `tests/test_judge.py` |
| C6 | Judge safety invariant | A previously-confirmed exploit is never scored "safe" | `forge/judge.py`, `forge/selfcheck.py` | `tests/test_platform_selfcheck.py`, `tests/test_judge.py` |
| C7 | Judge calibration / drift control | Frozen gold set re-scored on rubric change; shift on frozen inputs = drift | `forge/judge.py`, `forge/selfcheck.py` | `tests/test_platform_selfcheck.py`, `tests/test_judge_escalation.py` |
| C8 | Low-confidence escalation to human | False-negative-averse: uncertain verdicts go to human review, not silent pass | `forge/judge.py` | `tests/test_judge_escalation.py` |
| C9 | Human approval gate before publish/remediate | No autonomous publication; no agent applies a fix | `forge/documentation.py` | `tests/test_documentation_agent.py` |
| C10 | Data-quality gate on reports | Required fields + uniqueness enforced before a report is written | `forge/documentation.py` | `tests/test_documentation_agent.py` |
| C11 | Cost budget + halt-on-no-signal | Per-run/per-directive budget; Orchestrator halts/redirects on low signal-per-token | `forge/orchestrator.py`, `forge/cost_analysis.py` | `tests/test_orchestrator.py`, `tests/test_cost_analysis.py` |
| C12 | Deterministic regression replay | A fix passes only when the Judge confirms unsafe behavior is genuinely absent on replay | `forge/regression.py`, `forge/phi.py` | `tests/test_regression_harness.py`, `tests/test_compromise_aware_replay.py` |
| C13 | Typed, versioned inter-agent contracts | Every agent boundary payload validates against a pinned schema | `forge/schemas.py`, `forge/contracts.py`, `contracts/agent/` | `tests/test_schemas.py`, `tests/test_agent_contracts.py` |
| C14 | Failure handling / circuit breaker | Typed errors map to retry/redirect/halt; a run aborts after K failures | `forge/failure.py`, `forge/orchestrator.py` | `tests/test_failure_handling.py`, `tests/test_refusal_safe_run.py` |
| C15 | Red Team refusal handling | Authorized-testing framing + safe-run path when the model refuses | `forge/red_team.py` | `tests/test_red_team_refusal.py`, `tests/test_refusal_safe_run.py` |
| C16 | OWASP coverage mapping | Every eval case carries its OWASP Web/LLM category; coverage reported per category | `forge/owasp.py`, `forge/evals.py` | `tests/test_owasp_coverage.py`, `tests/test_owasp_coverage_metric.py` |
| C17 | Redacted transcripts / in-environment traces | Auth headers redacted at the Adapter; traces stay in-environment | `forge/target.py`, `forge/tracing.py` | `tests/test_observability.py` |
| C18 | Platform self-regression ("testing the tester") | Judge invariant, calibration stability, Red Team novelty, contract conformance checked each build | `forge/selfcheck.py` | `tests/test_platform_selfcheck.py` |

---

## Evidence Artifacts

The following artifacts already exist and constitute the supporting evidence base. Each is a real
file in the repository.

- **Architecture & design:** `ARCHITECTURE.md`, `ARCHITECTURE_DIAGRAM.md`,
  `DECISION_RECORD_BUILD_VS_CONFIGURE.md` (why custom agents over configuring Garak/ZAP/Burp),
  `BUILD_PLAN.md`.
- **Threat & risk:** `THREAT_MODEL.md` — six mandated categories with attack surface, impact,
  exploitation difficulty, existing defenses, and OWASP mapping per category.
- **Evaluation evidence:** `EVAL_RESULTS.md` (measured outcomes), and the seed dataset /
  coverage machinery in `forge/evals.py` with OWASP mapping in `forge/owasp.py`.
- **Interface contracts:** `contracts/README.md` (pinned sidecar wire contract) plus the
  request/response schemas and the inter-agent message schemas under `contracts/agent/`.
- **AI governance:** `AI_USE_DISCLOSURE.md` (where and how Claude is used, and the deterministic /
  human check that follows each AI decision) and `AI_COST_ANALYSIS.md` (100/1K/10K/100K scaling).
- **Users & operations:** `USERS.md`, `README.md`, `DEMO_SCRIPT.md`, `TIME_ESTIMATE.md`.
- **Executable evidence (tests):** the platform-self-regression suite
  `tests/test_platform_selfcheck.py`, the access-control suite `tests/test_access_control.py`, the
  contract suite `tests/test_agent_contracts.py`, the regression suite
  `tests/test_regression_harness.py`, and the documentation-gate suite
  `tests/test_documentation_agent.py`, among others. These are living controls: they re-verify the
  boundaries on every build, not one-time attestations.

---

## Residual Risks

The controls above reduce but do not eliminate risk. The following residual risks are stated
honestly, each with an explicit acceptance/mitigation position. This section is deliberately not
hand-waving — a reviewer should weigh these directly.

1. **The Judge is itself an LLM and can drift or err.** Independence and a versioned rubric reduce
   conflict-of-interest, but the grader remains probabilistic; it can mislabel a novel attack or
   drift silently between rubric versions.
   *Mitigation:* frozen calibration set re-scored on every rubric change, a hard safety invariant
   (a confirmed exploit is never scored safe), and low-confidence escalation to human review
   (`forge/judge.py`, `forge/selfcheck.py`, `tests/test_platform_selfcheck.py`).
   **Acceptance:** accepted — the false-negative-averse design (escalate-don't-pass) plus the
   invariant and calibration checks bound the downside to over-reporting and human triage load,
   which is the deliberately preferred failure direction for a security tool.

2. **Coverage is synthetic-data-only and non-production.** The platform attacks a sidecar seeded
   with synthetic Synthea data. Findings therefore evidence *classes* of weakness in the agent
   layer, not proof that a production deployment with real PHI behaves identically.
   *Mitigation:* the synthetic-only boundary (`THREAT_MODEL.md`, `ARCHITECTURE.md`) is an
   intentional blast-radius control; findings are written as reproducible transcripts
   (`forge/documentation.py`) that transfer to a production-representative environment.
   **Acceptance:** accepted for this authorization — the ATO covers the non-production target
   only; extending to any environment with real PHI requires a fresh authorization and is
   explicitly out of scope here.

3. **The Red Team can refuse (Claude-only offensive role).** Frontier-model safety filtering can
   suppress genuinely adversarial generation, silently *under*-covering categories and masquerading
   as "no findings".
   *Mitigation:* authorized-security-testing framing plus a safe-run refusal path
   (`forge/red_team.py`, `tests/test_red_team_refusal.py`, `tests/test_refusal_safe_run.py`), a
   novelty guard against a stale generator (`forge/selfcheck.py`), and a documented local/OSS
   model swap seam behind the LLM-client interface.
   **Acceptance:** accepted — refusals surface as an observable coverage gap the Orchestrator can
   report rather than a silent pass, and the swap seam is the escape hatch if refusal rate blocks
   coverage at scale.

4. **Confirmed-exploit reports and traces are operationally ephemeral in the deployed
   environment.** The production `reports/` directory and trace store on the hosted deploy are
   ephemeral; durable evidence lives in the versioned SQLite store and the in-repo artifacts.
   *Mitigation:* the append-only `events` audit trail and the versioned exploit store
   (`forge/store.py`, `forge/observability.py`) are the source of truth; reports are regenerable
   from stored transcripts.
   **Acceptance:** accepted — treat the deployed filesystem as a cache, not a system of record;
   evidence integrity rests on the store and the committed artifacts, not on ephemeral disk.

5. **A prompt-injected Red Team could attempt lateral action.** Untrusted target content the Red
   Team retrieves could try to steer the agent beyond its role.
   *Mitigation:* the sandbox (C4) means the worst a compromised Red Team can do is send more
   crafted requests through the single Adapter egress against the one allowlisted target — it
   cannot write findings, read the store, or redirect the run
   (`forge/target.py`, `forge/access.py`, `tests/test_access_control.py`).
   **Acceptance:** accepted — containment is by construction (single egress + allowlist +
   no-store-write), so injection escalates to noisier attacks against the intended target, not to
   platform compromise.

---

## Authorization Decision

**Decision: Authorized to Operate (ATO granted) for continuous / overnight-autonomous operation
against the pre-registered non-production OpenEMR Co-Pilot sidecar, subject to the conditions
below.**

Basis for the decision:

- The system description, trust boundaries, and control catalog above are grounded in and
  consistent with `ARCHITECTURE.md`, `ARCHITECTURE_DIAGRAM.md`, and `THREAT_MODEL.md`.
- Every control C1–C18 maps to concrete code and to an executable test that re-verifies it on each
  build, so the controls are living and continuously evidenced rather than one-time attestations.
- The residual risks are enumerated honestly and each is accepted with a stated, defensible
  rationale that keeps failure biased toward over-reporting and human review.
- The blast radius is bounded by construction: synthetic-only data, a single allowlisted egress,
  a sandboxed Red Team, an independent Judge, and a human approval gate before any
  publication or remediation.

**Conditions of authorization:**

1. **Scope lock:** this ATO covers the non-production, synthetic-data target only. Any target with
   real PHI, or any change to the egress/allowlist model, voids this authorization and requires a
   fresh packet.
2. **Human gate stays closed:** the publication/remediation approval gate (C9) must remain enabled;
   no agent may be granted authority to apply fixes.
3. **Self-regression must stay green:** the platform-self-regression suite
   (`tests/test_platform_selfcheck.py`) and the access-control suite
   (`tests/test_access_control.py`) must pass on every build; a failure suspends autonomous
   operation until remediated.
4. **Re-authorization trigger:** a material change to the Judge rubric, the trust-boundary model,
   or the target contract (`contracts/README.md`) requires this packet to be revisited.

**Reviewer sign-off:** _____________________  **Date:** ____________
