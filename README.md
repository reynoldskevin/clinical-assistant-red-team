# Agent Forge Adversarial

`agent-forge-adversarial` is a Python (stdlib-first) autonomous red-team platform
that attacks the **OpenEMR AI Clinical Co-Pilot** sidecar. The attack loop is:
Red Team agent → Target Adapter → Judge (an independent verdict) → SQLite
exploit/event store → observability read-model → live dashboard. You run one
attack category with `forge run --category <c>` (or `python -m forge run
--category <c>`) and serve the dashboard with `forge serve` (or `python -m forge
serve`).

## Contents
Deployed URLs [here](#deployed-urls)\
Target under test [here](#target-under-test)\
How the target is reached / made testable [here](#how-the-target-is-reached--made-testable)\
Data Handling & Retention [here](#data-handling--retention)\
Running instructions [here](#running-instructions)\
Engineering Deliverables [here](#engineering-deliverables)

## Deployed URLs

- **Platform dashboard** (this repo, Railway):
  `https://agent-forge-adversarial-production.up.railway.app`
- **Target under test — the submission hard gate** (must be live):
  `https://ai-sidecar-production-c492.up.railway.app`

## Target under test

The target is the **OpenEMR AI Clinical Co-Pilot sidecar**, a grounded clinical
assistant deployed to Railway at
`https://ai-sidecar-production-c492.up.railway.app`. Its surface:

- `POST /ask` — grounded clinical QA (a slow, 1–4 minute agent loop).
- `POST /extract` — structured extraction.
- `GET /health` and `GET /ready` — unauthenticated liveness/readiness probes.

Behind the sidecar is an OpenEMR instance at
`https://truthful-peace-production-62af.up.railway.app`.

**Non-production, synthetic-data-only, no real PHI.** The deployed instance holds
only synthetic Synthea data (for example, pid=1 is "Brett Cruickshank",
DOB 1925) — there is **no real PHI**. This is a non-prod evaluation target, which
bounds the blast radius of any exfiltration attack or harmful generated content.

## How the target is reached / made testable

Other than a performance issue (documented below) the Co-Pilot's attack surface 
was **not modified**. It was simply deployed to Railway with synthetic data. The platform 
reaches it exclusively through the **Target Adapter** (`forge/target.py`), which is the 
sole egress path:

- It resolves a **target id** against the ticket-023 allowlist — never a raw URL
  — as SSRF protection.
- It mints a per-pid, short-lived, scoped HS256 JWT via an injected **token
  provider** (the OpenEMR `oe-module-ai-agent` `dev_mint.php` dev-mint endpoint,
  enabled only because this is a synthetic instance) and sends that bearer
  **token** to `/ask` / `/extract`.
- It persists a **redacted** transcript of every `/ask` and `/extract` call to
  the SQLite event store, with the `Authorization` header replaced by
  `Bearer ***redacted***` (the unauthenticated `/health` probe carries no token
  and is not recorded).

The `TARGET_BASE_URL` environment variable selects the target; when it is unset,
the live smoke test skips cleanly.

### Performance Improvements

Each patient chart fired ~10,000 MySQL queries, and the database lived in a separate 
Railway service reached over the private-network overlay at ~3.3 ms per round-trip. 
That's 10,000 × 3.3 ms ≈ 33 s per chart — the latency itself was the bottleneck, not 
query complexity or PHP.

The fix was to co-locate the database in the app container instead of talking to a 
remote MySQL service, the app now runs its own MariaDB 11.4 inside the same container, 
reached over the loopback socket at ~0.037 ms/query — roughly 89× faster. Same ~10,000 
queries, but the round-trip cost collapses.

Result: charts went from ~33 s to ~1.5 s (measured on the live demo).

## Data handling & retention

- Every `/ask` and `/extract` call is persisted as an **append-only** event in
  SQLite with the bearer token redacted.
- Transcripts contain only synthetic-patient content — no real PHI.
- **Retention:** transcripts are retained for the life of the evaluation database
  and can be cleared by deleting the SQLite DB file.

## Engineering Deliverables

### MVP

Threat Model [here](THREAT_MODEL.md)\
Architecture [here](ARCHITECTURE.md)\
Architecture Diagram [here](ARCHITECTURE_DIAGRAM.md)\
Eval Suite Results [here](EVAL_RESULTS.md)

### Final Submission

Users [here](USERS.md)\
AI Cost Analysis [here](AI_COST_ANALYSIS.md)\
Vulnerability Reports [here](/reports/)\
Eval Dataset [here](/evals/)\
Resolved Vulnerabilities Documentation [here](RESOLVED.md)