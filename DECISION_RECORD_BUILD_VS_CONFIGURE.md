# Build-vs-Configure Decision Record

**Deliverable:** Architecture-Defense record (Optional Engineering Deliverable — "Build-versus-configure decisions")
**Subject:** Agent Forge — an autonomous, multi-agent adversarial red-team platform
**Target under test:** the OpenEMR **AI Clinical Co-Pilot** sidecar (a live LLM clinical assistant)
**Status:** Decided — core roles **Build**; deterministic substrates **Configure/reuse**

## 1. Purpose & context

Before implementing any agent role, a security reviewer is entitled to ask the blunt question:
*"You are attacking an HTTP-fronted LLM — why didn't you just point an existing scanner at it and
configure it?"* This record answers that question honestly. It evaluates the tools the brief names
by hand — **Burp Suite**, **OWASP ZAP**, **Semgrep**, **Garak**, and the category of **commercial
LLM red-team / pentest platforms** — states what each genuinely covers well and where each falls
short for *this* use case, and then records a build-vs-configure verdict for every agent role.

The platform's job shapes the whole analysis. Agent Forge is **not** a static test runner. It is a
coordinated system of agents that *continuously* generates novel adversarial inputs, **mutates**
partially-successful attacks into variant families, stages **multi-turn** sequences, and — critically
— has an **independent LLM Judge** (architecturally separated from the Red Team) decide whether an
attack actually succeeded, using a versioned rubric and calibration set. The target is a **clinical
assistant**: the interesting failures are not just HTTP-layer injection but **PHI leakage,
cross-patient exposure, authorization-boundary bypass, tool misuse, and persona/role hijack** — each
mapped to **OWASP Web Top 10 + OWASP LLM Top 10**. That combination — *adaptive, evidence-driven,
multi-turn, LLM-judged, clinical-context-aware* — is the axis on which the off-the-shelf options are
measured below.

## 2. Evaluation of existing tools

For each tool: **(a)** what it covers well, and **(b)** where it falls short for attacking an
adaptive, multi-turn LLM clinical assistant with an independent LLM judge and OWASP Web+LLM mapping.

### Burp Suite (web app proxy / scanner — commercial)
- **Covers well:** Best-in-class HTTP interception, request tampering, and active scanning of a
  web application's protocol surface — parameter fuzzing, classic injection (SQLi/XSS), auth-token
  manipulation, session handling, and a mature extension ecosystem (BApp). If the Co-Pilot's
  *transport* has a web-app flaw, Burp finds it.
- **Falls short:** Burp reasons about **requests and responses as HTTP artifacts**, not about the
  **semantics of a multi-turn conversation** with an LLM. It has no concept of a "partial jailbreak"
  worth mutating, no independent grader of whether a clinical answer *leaked another patient's PHI*,
  and no notion of a clinical authorization boundary expressed in natural language. Its intruder
  payloads are static lists; the brief explicitly rules static payload lists insufficient. It cannot
  author a novel prompt-injection chain and adapt it based on the model's prior reply.

### OWASP ZAP (web app scanner — open source)
- **Covers well:** The open-source analogue to Burp — spidering, passive/active HTTP scanning,
  fuzzing, scriptable via automation framework. Strong, free coverage of the OWASP **Web** Top 10
  at the protocol layer (injection, broken access control probes on endpoints, misconfig, SSRF-style
  checks), and easy to wire into CI.
- **Falls short:** Same ceiling as Burp — it is **blind to multi-turn LLM semantics** and to
  clinical-context authorization logic. ZAP cannot decide "this response constitutes sensitive
  information disclosure for *this* patient context," cannot mutate a role-play jailbreak, and has no
  independent LLM judge. It addresses the Web Top 10 transport surface but essentially none of the
  **LLM** Top 10 behavioral surface (prompt injection, excessive agency, insecure output handling as
  *content* rather than markup).

### Semgrep (static analysis — open source / commercial)
- **Covers well:** Fast, rule-based **static code analysis** (SAST) and secrets scanning across many
  languages, with a large rule registry and good CI ergonomics. Excellent for **white-box** review of
  the Co-Pilot's *own source* — spotting an unsafe sink, a missing authz check in code, a hardcoded
  credential, or a vulnerable dependency pattern.
- **Falls short:** Semgrep is **static and white-box**; Agent Forge does **black-box behavioral
  red-teaming** against a *running* model whose behavior is emergent and not derivable from source
  patterns. Semgrep cannot observe that a deployed model, at runtime, can be talked across a PHI
  boundary over three conversational turns. It is a valuable *complementary* control (harden the
  code) but not a substitute for adversarially exercising the live endpoint.

### Garak (LLM vulnerability scanner — open source)
- **Covers well:** The closest fit — Garak is purpose-built to **probe LLMs**, with a library of
  probes for prompt injection, jailbreaks, toxicity, data leakage, encoding tricks, and more, plus
  detectors that score outputs. For a first-pass, breadth-oriented LLM scan it is genuinely useful and
  we treat its probe taxonomy as prior art.
- **Falls short:** Garak's probes are largely **static / templated** and its detectors are
  pattern/heuristic or fixed-classifier based — it runs a catalog, it does not **adaptively mutate a
  partial success into a variant family** guided by an evaluator, and it does not carry a
  **clinical-context, rubric-versioned independent LLM judge** that rules on PHI/cross-patient/authz
  outcomes with calibration and drift controls. It has no orchestration read-model steering coverage
  toward under-tested categories or open high-severity findings, and no notion of the OpenEMR
  clinical authorization boundaries the Co-Pilot must enforce. It informs our taxonomy; it does not
  do the adaptive, evidence-driven, clinically-judged core.

### Commercial LLM red-team / pentest platforms (COTS/SaaS category)
- **Covers well:** Emerging **commercial red-team / LLM-security platforms** (the category of hosted
  automated pentest and AI-red-team products) offer polished dashboards, curated attack libraries,
  managed scale, and reporting — real value if the goal were a turnkey generic scan.
- **Falls short:** Three decisive gaps here. **(1) Fit:** they are generic; they do not model the
  OpenEMR Co-Pilot's specific clinical authorization and PHI boundaries or our six-category taxonomy
  and dual OWASP Web+LLM mapping. **(2) Data residency:** they are typically **hosted SaaS**, so
  attack transcripts — which contain sensitive-looking clinical model output — would **leave our
  environment**, which is unacceptable against a healthcare target (the same reason we self-host
  Langfuse and rejected LangSmith for mainline). **(3) Extensibility & cost control:** they are closed;
  we cannot insert our independent versioned Judge, our mutation/multi-turn logic, our budget-halting
  Orchestrator, or our regression harness. Building *is* the deliverable here — the brief asks us to
  demonstrate a multi-agent system, not to procure one.

### Comparison summary

| Capability needed | Burp | ZAP | Semgrep | Garak | Commercial LLM RT | Agent Forge (custom) |
|---|---|---|---|---|---|---|
| HTTP/protocol fuzzing & web injection | ✅ strong | ✅ strong | ⚪ n/a (static) | ⚪ limited | ✅ | reuses via Target Adapter |
| Static/white-box code review | ⚪ | ⚪ | ✅ strong | ⚪ | ⚪ | complementary, out of scope |
| LLM prompt-injection / jailbreak probing | ⚪ | ⚪ | ⚪ | ✅ (static probes) | ✅ (library) | ✅ generative |
| **Adaptive mutation of partial successes** | ❌ | ❌ | ❌ | ❌ | ⚪ partial | ✅ core |
| **Multi-turn attack staging** | ❌ | ❌ | ❌ | ⚪ limited | ⚪ varies | ✅ core |
| **Independent LLM judge (versioned rubric + calibration)** | ❌ | ❌ | ❌ | ❌ heuristic | ⚪ opaque | ✅ core |
| **Clinical-context PHI / cross-patient / authz reasoning** | ❌ | ❌ | ❌ | ❌ | ❌ generic | ✅ core |
| OWASP Web + LLM mapping per case | partial (Web) | partial (Web) | ⚪ | partial (LLM) | varies | ✅ both, per case |
| Orchestration steered by coverage/severity read-model | ❌ | ❌ | ❌ | ❌ | ⚪ | ✅ |
| Data stays in-environment (healthcare) | ✅ local | ✅ local | ✅ local | ✅ local | ❌ SaaS | ✅ self-hosted |

Legend: ✅ strong · ⚪ partial/limited · ❌ absent.

## 3. Build-vs-configure verdict per agent role

The honest outcome: the four core agent roles are **Build**, because the adaptive / multi-turn /
LLM-judged behavior is exactly what the off-the-shelf tools above do not do — while we deliberately
**Configure/reuse** deterministic tooling *inside* each role wherever determinism is cheaper and more
reliable than an LLM call.

### Red Team Agent — **Build**
Custom agent. No configured tool generates *novel* adversarial inputs and then **mutates** a
partial success into a variant family (rephrase, encode, indirection, role-play, multi-turn staging)
under an Orchestrator directive. Garak's static probes and Burp/ZAP's payload lists cannot do
evidence-driven escalation. **Reuse underneath:** the deterministic **Target Adapter** HTTP layer
(the single egress to the live Co-Pilot, with credential handling, allowlist, and raw transcript
recording), template-based **mutation seeds** (zero-LLM), and **JSON-schema/Pydantic contract
validation** on every `AttackAttempt`.

### Judge Agent — **Build**
Custom agent, and non-negotiably so. The independent evaluator must rule on whether a *clinical*
attack succeeded — PHI leak, cross-patient exposure, authz bypass — against a **versioned rubric**
with a **calibration set** and drift/invariant controls. No scanner ships a clinical-context LLM
judge, and Garak's fixed detectors cannot be versioned/calibrated to our per-category success
criteria. Architectural separation from the Red Team (a self-grading attacker is compromised by
design) is a property only a purpose-built role provides. **Reuse underneath:** low-temperature
deterministic invocation, **schema-validated `Verdict`** objects, the frozen calibration harness, and
the invariant test that runs as ordinary deterministic tooling.

### Orchestrator Agent — **Build** (thin custom agent over deterministic policy)
Custom agent, but deliberately **mostly deterministic policy** with an LLM assist only for ambiguous
prioritization. It reads the observability read-model to steer toward under-covered categories and
open high-severity findings, enforces **cost budgets**, halts on low signal-per-token, and triggers
regression on target change. No configured tool offers this coverage-and-cost-aware strategy loop.
**Reuse underneath:** the **SQLite** read-model, deterministic budget/halt thresholds, round-robin
fallback, and LangGraph checkpointed state — all configured, not LLM-driven.

### Documentation Agent — **Build**
Custom agent. It converts a Judge-confirmed exploit into a reproducible, structured vulnerability
report and enforces a data-quality gate before anything is written; publication sits behind a human
approval gate. A scanner's canned report template cannot synthesize our transcript-plus-verdict
lineage into remediation-grade prose. **Reuse underneath:** the fixed **report schema**
(schema-validated required fields + uniqueness), **SQLite** persistence to the Exploit Store, and the
deterministic **Regression & Validation Harness** (replay + reappearance/cross-category flags) that
the reporting flow leans on.

### Decisions summary table

| Agent role | Verdict | Core rationale | Configured / reused underneath |
|---|---|---|---|
| Red Team | **Build** | Adaptive, multi-turn, mutation-driven generation no scanner does | Target Adapter HTTP layer, replay, template mutation seeds, schema validation |
| Judge | **Build** | Independent, clinical-context, versioned-rubric LLM judgment with calibration | Low-temp determinism, JSON-schema Verdict, calibration + invariant harness |
| Orchestrator | **Build** | Coverage/severity/cost-steered strategy loop | SQLite read-model, deterministic budget/halt policy, LangGraph state |
| Documentation | **Build** | Reproducible, data-quality-gated vuln reporting from verdict lineage | Report schema validation, SQLite Exploit Store, deterministic regression harness |

*(Deterministic, non-agent components — Target Adapter, Regression Harness, Observability/Exploit
Store — are **Configure/reuse-and-build-thin**: standard HTTP, replay, JSON-schema contracts, and
SQLite rather than any LLM.)*

## 4. Verdict & justification

Building **custom agents** is warranted — over configuring Burp, ZAP, Semgrep, Garak, or a
commercial platform — precisely for the **adaptive, multi-turn, LLM-judged** core of this brief.
The existing tools are strong where they are strong: Burp/ZAP for HTTP protocol and web-injection
fuzzing, Semgrep for static white-box code review, Garak for breadth-first LLM probing, and
commercial platforms for turnkey scale. But every one of them **falls short** on the same axis — none
adaptively mutates a partial success into a variant family, stages evidence-driven multi-turn
attacks, or carries an **independent, versioned, calibrated LLM judge** that reasons about
clinical-context PHI, cross-patient, and authorization boundaries and maps each case to OWASP Web +
LLM. That is the deliverable, and it is exactly what off-the-shelf scanners do not do.

The decision is therefore **not** "custom everything." It is: **build the agents, configure the
substrate.** We reserve LLM-backed custom agents for the genuinely generative and evaluative work,
and we **reuse deterministic tooling** — the Target Adapter's HTTP/replay layer, JSON-schema/Pydantic
contract validation, the regression harness, and SQLite — wherever determinism is cheaper, more
reliable, and easier to audit than a model call. This keeps cost a first-class control while ensuring
the adaptive, multi-turn, LLM-judged capability that no configured tool provides is the part we
actually own.
