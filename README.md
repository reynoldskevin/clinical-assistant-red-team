# agent-forge-adversarial

`agent-forge-adversarial` is a Python (stdlib-first) autonomous red-team platform
that attacks the **OpenEMR AI Clinical Co-Pilot** sidecar. The attack loop is:
Red Team agent → Target Adapter → Judge (an independent verdict) → SQLite
exploit/event store → observability read-model → live dashboard. You run one
attack category with `forge run --category <c>` (or `python -m forge run
--category <c>`) and serve the dashboard with `forge serve` (or `python -m forge
serve`).

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

The Co-Pilot's attack surface was **not modified**. It was simply deployed to
Railway with synthetic data. The platform reaches it exclusively through the
**Target Adapter** (`forge/target.py`), which is the sole egress path:

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

## Data handling & retention

- Every `/ask` and `/extract` call is persisted as an **append-only** event in
  SQLite with the bearer token redacted.
- Transcripts contain only synthetic-patient content — no real PHI.
- **Retention:** transcripts are retained for the life of the evaluation database
  and can be cleared by deleting the SQLite DB file.

## Running

- Run one attack category: `forge run --category <c>` (or
  `python -m forge run --category <c>`).
- Serve the dashboard: `forge serve` (or `python -m forge serve`).
- Point the adapter at a live target by setting `TARGET_BASE_URL`; leave it unset
  to run against the injected transport and skip the live smoke test.
