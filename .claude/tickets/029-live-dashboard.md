---
id: 029
title: Live demo dashboard (forge serve) over the 016 read-model
status: tests-authored # todo | tests-authored | implementing | reviewing | regression | ready-for-merge | blocked
depends_on: [016]
branch: ticket/029-live-dashboard
base_branch: main
test_command: ".venv/bin/pytest tests/test_dashboard.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
The MVP needs a visible demo UI. This ticket adds `forge serve`: a stdlib-only HTTP dashboard that renders the merged 016 observability read-model live and auto-refreshes, deployable to Railway. It is zero-new-dependency (Python `http.server`), so it stays consistent with the stdlib-first codebase and needs no async test harness. The page is the design approved in the gallery mockup — a bento widget grid (KPIs; pass/fail by category; resilience trend; OWASP coverage; cost; findings; live agent activity) with accent `#2968e6`, theme-aware. A JSON endpoint `GET /api/state` serves the current `Observability.snapshot()` (plus a small `kpis` summary); the HTML shell embeds the initial state and polls that endpoint to re-render, so the dashboard reflects the store live without a rebuild. The dashboard reads only the store (no Anthropic API key required to run), and binds to `$PORT`/`0.0.0.0` for Railway.

## Acceptance criteria
- [ ] `from forge.dashboard import build_state, render_html, handle_path, make_server, serve, resolve_bind` works.
- [ ] `build_state(observability)` returns a JSON-serializable dict with a `kpis` block (`resilience`, `attempts`, `exploits`, `total_usd`, `usd_per_attempt`) plus the six 016 views (`coverage`, `pass_fail`, `resilience_trend`, `finding_lifecycle`, `cost`, `agent_activity`), whose values match the `Observability` instance.
- [ ] `render_html(state)` returns a single self-contained HTML document (no external `src=`/`href=` URLs) that: declares `<!doctype html>`; sets an `Agent Forge` title; uses accent `#2968e6`; contains every widget heading (`Pass / fail by category`, `Resilience trend`, `OWASP coverage`, `Cost`, `Findings`, `Live agent activity`); embeds the passed state verbatim in a `<script id="initial-state" type="application/json">` block; and polls `GET /api/state` on an interval (`setInterval`) to re-render.
- [ ] `handle_path(path, state_provider)` routes: `/` and `/index.html` → `(200, "text/html; charset=utf-8", <html>)`; `/api/state` (query string ignored) → `(200, "application/json", <json>)` where the body JSON-decodes to `state_provider()`; `/health` → `200` JSON; anything else → `404`. `state_provider` is invoked fresh per request (live view).
- [ ] `make_server(store, *, host, port, cases=None)` returns a bound `http.server` server whose handler serves the same routes end-to-end (a real localhost request to `/api/state` returns the live state; `/` returns the page). `serve(...)` is `make_server(...)` + `serve_forever()`.
- [ ] `resolve_bind(args, env)` resolves the bind address: explicit `--port` wins; else `PORT` env (Railway); else default `8000`; host is `args.host` or `0.0.0.0`. `forge.run.parse_args(["serve", ...])` yields `command="serve"` with `--host`/`--port`, without breaking the existing `run` subcommand.
- [ ] Deployable: a `Procfile` starts the dashboard (`web: forge serve`); `forge serve` needs only the store (no `ANTHROPIC_API_KEY`).

## Test plan (orchestrator authors these)
- unit: `tests/test_dashboard.py` — pins `build_state` shape + JSON-serializability + value agreement with `Observability`; `render_html` self-containment, title/accent/headings, embedded `initial-state` round-trip, and `/api/state` polling; `handle_path` routing + query-strip + 404 + per-request-fresh `state_provider`; `resolve_bind` precedence (arg > PORT env > default); and the `serve`/`run` CLI wiring.
- e2e/contract: a threaded `make_server` on an ephemeral port answered by a real `urllib` request to `/api/state` and `/` — proving the `http.server` handler and the pure `handle_path` router agree on the wire (no independent fakes).
