# Threat Model — OpenEMR AI Clinical Co-Pilot Sidecar

Target: the OpenEMR AI Clinical Co-Pilot sidecar deployed at
`https://ai-sidecar-production-c492.up.railway.app`, operating exclusively over
synthetic Synthea data with no real PHI. This document enumerates the adversarial
surface that the agent-forge-adversarial red-team platform attacks.

## Summary / Key Findings

The sidecar exposes two HTTP surfaces to an authenticated caller: `POST /ask`,
a buffered, grounded clinical question-answering endpoint that runs a real
multi-step LLM agent loop (typically 1–4 minutes per request and multi-turn via a
server-held, pid-scoped history keyed by `(conversation_id, pid)`), and
`POST /extract`, which pulls structured facts from a named document. Both sit
above a deterministic access boundary: authentication is an HS256 scoped JWT
minted by the OpenEMR custom module `oe-module-ai-agent`, carrying claims
`{pid, purpose:"treatment", aud:"oe-ai-agent-boundary", exp ~5min, scope:"read"}`.
The sidecar forwards that token to the module's `read.php` chart-read boundary,
which enforces pid↔token binding and fails closed with a 403 on any mismatch.
That single design decision reshapes the entire threat landscape.

The central finding of this model is a sharp asymmetry between two layers. The
deterministic access boundary is strong: because `read.php` binds every chart
read to the pid embedded in a short-lived, audience-scoped, read-only token and
refuses mismatches, the naive cross-patient attack — present a token for patient
A while asking about patient B — is rejected at the boundary rather than by the
model's judgment. Token lifetime is short, scope is read-only, and the corpus is
synthetic, so the classic broken-object-level-authorization pivot is largely
foreclosed at the wire. By contrast, the probabilistic agent/LLM layer sitting
above that boundary is the genuinely exposed surface. The model decides what to
retrieve, how to chain `read.php` operations, and what to place in its natural
language answer, and none of those decisions carry the deterministic guarantees
the boundary does.

Consequently the two highest-risk categories are prompt injection and data
exfiltration, both realized at the agent layer. Instructions embedded in the
`question` field, or indirectly in chart and document content the agent retrieves
(lab PDFs, intake forms, medication lists), can steer the loop; and even when the
boundary constrains which records are readable, the model may over-disclose,
summarize beyond the caller's need, or leak content across conversation turns.
State corruption follows closely: the server-held `(conversation_id, pid)` history
is a poisoning and context-bleed target. Tool misuse (excessive agency in
`read.php` tool-calling), denial of service (the slow agent loop and unbounded
history as resource-exhaustion levers), and identity/role exploitation (token
replay, aud/scope confusion, attempts to defeat the pid binding) round out the
six categories. For identity exploitation specifically, the fail-closed boundary
makes exploitation difficulty high — the interesting residual risk is not
bypassing the check but confusing the layers that feed it.

The overall posture: a well-designed deterministic guardrail protects the data,
while the value-adding LLM reasoning layer above it remains probabilistic and
therefore the primary hunting ground. Defensive investment should concentrate on
input/output mediation around the agent — untrusted-content isolation, output
scoping, per-tenant conversation isolation, and rate and cost limits on the
expensive loop — rather than on the boundary, which already does its job. The
sections below detail each category with its attack surface, potential impact,
exploitation difficulty, existing defenses, and OWASP mapping.

## Prompt Injection

**Attack surface:** The `POST /ask` `question` field is the direct vector, and
the chart/document content the agent retrieves via `read.php`
(`get_document`, `get_results`, `search_chart`) is the indirect vector —
attacker-influenced text inside a lab PDF, intake form, or note that the agent
ingests as trusted context and follows as instructions.

**Impact:** Hijacking the agent loop to ignore its grounding, emit unauthorized
summaries, chain unintended tool calls, or produce misleading clinical output.
Indirect injection is the more severe form because it survives even when the
caller's own prompt is benign.

**Exploitation difficulty:** Medium. Direct injection is trivial to attempt but
constrained downstream by the fail-closed pid boundary — the model cannot read
another patient's chart no matter what it is told. Indirect injection through
retrieved content is harder to seed but bypasses input filters on the question.

**Existing defenses / mitigation:** Grounded-QA design, the read-only scoped
token, the pid-bound boundary that caps blast radius to the authorized chart, and
synthetic-only data. Residual gap: no strong separation between trusted
instructions and untrusted retrieved content inside the loop.

**OWASP mapping:** OWASP LLM01 (Prompt Injection) — both direct and indirect.

## Data Exfiltration

**Attack surface:** The natural-language `answer` returned by `POST /ask` and the
structured output of `POST /extract`. The model is the disclosure channel: even
within one authorized pid it can over-share, and it may be coaxed to restate
content that should stay scoped.

**Impact:** Sensitive-information disclosure — PHI over-disclosure within a chart,
attempts to surface data beyond the caller's treatment need, or leakage of
system/prompt context. Cross-patient PHI is blocked at the boundary, so realized
impact centers on over-disclosure and scope creep rather than wholesale breach.

**Exploitation difficulty:** Medium. The fail-closed boundary makes true
cross-patient exfiltration hard, but nudging the model to summarize or reveal more
than intended within the authorized record is comparatively easy.

**Existing defenses / mitigation:** pid-bound fail-closed JWT, read-only scope,
short token lifetime, synthetic Synthea data (no real PHI at risk), and grounded
retrieval. Residual gap: no output-side PHI minimization or answer scoping.

**OWASP mapping:** OWASP LLM06 (Sensitive Information Disclosure), with LLM02
(Insecure Output Handling) relevant to the response channel.

## State Corruption

**Attack surface:** The server-held multi-turn conversation history keyed by
`(conversation_id, pid)`. An attacker who influences earlier turns — or who can
collide/guess a `conversation_id` — poisons the context the agent trusts on later
turns.

**Impact:** Integrity loss. Poisoned history can bias or corrupt subsequent
answers, and cross-turn context bleed can carry content from one turn into an
unrelated response, degrading grounding and trustworthiness.

**Exploitation difficulty:** Medium. Poisoning one's own history is easy; forcing
bleed across pids is constrained because history is pid-scoped and reads remain
pid-bound at the boundary, so corruption is largely confined within a tenant.

**Existing defenses / mitigation:** pid-scoped history keying, the fail-closed
read boundary that limits what poisoned context can actually retrieve, and
read-only tokens. Residual gap: history is server-trusted with no per-turn
provenance or integrity check on accumulated context.

**OWASP mapping:** OWASP LLM01 (Prompt Injection via persisted context) and
OWASP A01 (Broken Access Control) where conversation isolation is at issue.

## Tool Misuse

**Attack surface:** The agent's tool-calling over the `read.php` operation set —
summary, list_encounters, get_encounter, get_results, get_medications,
search_chart, get_documents, get_document — invoked autonomously inside the loop.

**Impact:** Excessive agency: the agent chaining more operations than a question
warrants, enumerating documents or encounters unnecessarily, or being steered
(via injection) to reach data through tools it did not need. Impact is bounded to
the authorized pid but can still broaden disclosure within it.

**Exploitation difficulty:** Medium. Inducing extra tool calls is feasible through
crafted questions, but every call is still gated by the pid-bound, read-only
boundary, so tools cannot reach another patient or perform writes.

**Existing defenses / mitigation:** Read-only scoped token, pid-bound fail-closed
`read.php`, a fixed and enumerated tool set (no write ops, no arbitrary calls),
and synthetic data. Residual gap: no per-request budget on tool-call count or
least-privilege gating of individual operations.

**OWASP mapping:** OWASP LLM08 (Excessive Agency), with LLM06 relevant where tool
chaining widens disclosure.

## Denial of Service

**Attack surface:** The `POST /ask` agent loop itself — a slow, expensive
1–4 minute multi-step LLM run — plus the unbounded server-held conversation
history that grows per `(conversation_id, pid)`.

**Impact:** Availability loss and cost amplification. A modest volume of concurrent
or repeated `/ask` calls, or deliberately complex questions that force long tool
chains, can exhaust model/compute capacity; ever-growing history inflates context
size, latency, and token cost per turn.

**Exploitation difficulty:** Low-to-Medium. No special access beyond a valid
short-lived token is required to launch expensive requests; the main limiter is
token issuance and any upstream rate limiting rather than the sidecar itself.

**Existing defenses / mitigation:** Short token lifetime (caps sustained abuse per
token), buffered single-response design, and read-only scope. Residual gap: no
documented per-caller rate limit, concurrency cap, request timeout, or history
size bound on the expensive loop.

**OWASP mapping:** OWASP LLM04 (Model Denial of Service), with OWASP A05
(Security Misconfiguration) where resource limits are absent.

## Identity / Role Exploitation (Privilege Escalation)

**Attack surface:** The HS256 scoped JWT and the pid↔token binding enforced at
`read.php` — targeted via token replay within the ~5-minute window, aud/scope
confusion (`aud:"oe-ai-agent-boundary"`, `scope:"read"`), or attempts to present a
token for one pid while requesting another patient's data.

**Impact:** If the binding could be defeated, cross-patient PHI access and
privilege escalation beyond read-only treatment scope. In practice this is the
crown-jewel target because success would collapse the whole boundary.

**Exploitation difficulty:** High. The boundary fails closed (403) on any pid
mismatch, tokens are short-lived, audience- and scope-restricted, and read-only;
the naive cross-patient attack is refused deterministically. Residual risk lives
in layer-confusion and replay rather than in defeating the check directly.

**Existing defenses / mitigation:** pid-bound fail-closed JWT boundary, short
`exp`, audience and read-only scope claims, HS256 signature verification, and
synthetic-only data. Residual gap: replay within the token window and reliance on
correct aud/scope validation at every consumer.

**OWASP mapping:** OWASP A01 (Broken Access Control) and OWASP API2
(Broken Authentication), with LLM06 where the model layer mediates disclosure.
