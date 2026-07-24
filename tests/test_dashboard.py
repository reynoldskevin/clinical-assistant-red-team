"""Acceptance tests for ticket 029 — live demo dashboard (`forge serve`).

These tests are the FIXED contract for the dashboard seam. They pin:
- `from forge.dashboard import build_state, render_html, handle_path, make_server,
   serve, resolve_bind`.
- `build_state(observability)` — a JSON-serializable state dict: a `kpis` summary plus
  the six 016 views, agreeing with the `Observability` instance.
- `render_html(state)` — ONE self-contained HTML document (no external assets) carrying
  the approved design (title, accent #2968e6, every widget heading), embedding the state
  verbatim in a `#initial-state` JSON script, and polling `/api/state` to re-render.
- `handle_path(path, state_provider)` — the pure router for `/`, `/api/state`, `/health`,
  404; query string ignored; `state_provider` called fresh per request.
- `make_server(...)` — a real `http.server` whose handler serves those routes end-to-end
  (contract test over an actual localhost request), and `resolve_bind` / CLI wiring for
  Railway (`$PORT`, `0.0.0.0`).

Verdict semantics (inherited from 016): verdict "success" = target EXPLOITED; "fail" =
DEFENDED; pass_rate = defended / attempts.
"""

import json
import re
import threading
import urllib.request
from types import SimpleNamespace

import pytest

from forge.store import Store
from forge.observability import Observability


# category -> OWASP mapping (duck-typed like forge.evals.EvalCase), matching 016's fixtures
CASES = [
    SimpleNamespace(category="prompt_injection", owasp_web=[], owasp_llm=["LLM01:Prompt Injection"]),
    SimpleNamespace(
        category="data_exfiltration",
        owasp_web=["A01:2021-Broken Access Control"],
        owasp_llm=["LLM06:Sensitive Information Disclosure"],
    ),
]


def _seed():
    """A controlled run history: 7 verdicts across 2 categories, findings, cost rows."""
    s = Store(":memory:")
    rid = s.append_event({"kind": "run_start", "target_version": "v1"})
    s.append_event({"kind": "attack", "attempt_id": 1, "category": "prompt_injection", "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 1, "category": "prompt_injection", "verdict": "success", "confidence": 0.9, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 2, "category": "prompt_injection", "verdict": "fail", "confidence": 0.8, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 3, "category": "data_exfiltration", "verdict": "fail", "confidence": 0.7, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 4, "category": "data_exfiltration", "verdict": "fail", "confidence": 0.7, "target_version": "v1"})
    s.append_event({"kind": "verdict", "attempt_id": 5, "category": "prompt_injection", "verdict": "fail", "confidence": 0.8, "target_version": "v2"})
    s.append_event({"kind": "verdict", "attempt_id": 6, "category": "prompt_injection", "verdict": "partial", "confidence": 0.5, "target_version": "v2"})
    s.append_event({"kind": "verdict", "attempt_id": 7, "category": "data_exfiltration", "verdict": "fail", "confidence": 0.7, "target_version": "v2"})
    s.append_event({"kind": "run_end"})
    s.insert_finding({"severity": "high", "attack_category": "prompt_injection", "target_version": "v1", "status": "open", "run_id": rid})
    s.insert_finding({"severity": "medium", "attack_category": "prompt_injection", "target_version": "v1", "status": "in_progress", "run_id": rid})
    s.insert_finding({"severity": "low", "attack_category": "data_exfiltration", "target_version": "v1", "status": "resolved", "run_id": rid})
    s.insert_cost({"category": "prompt_injection", "usd": 0.30, "input_tokens": 100, "output_tokens": 200, "run_id": rid})
    s.insert_cost({"category": "data_exfiltration", "usd": 0.20, "input_tokens": 60, "output_tokens": 40, "run_id": rid})
    return s


def _obs(store=None, cases=CASES):
    return Observability(store or _seed(), cases=cases)


# --------------------------------------------------------------------------- #
# imports
# --------------------------------------------------------------------------- #
def test_imports():
    from forge.dashboard import (  # noqa: F401
        build_state,
        render_html,
        handle_path,
        make_server,
        serve,
        resolve_bind,
    )


# --------------------------------------------------------------------------- #
# build_state
# --------------------------------------------------------------------------- #
def test_build_state_is_json_serializable_and_has_all_sections():
    from forge.dashboard import build_state

    state = build_state(_obs())
    # round-trips through JSON unchanged (must be wire-serializable)
    assert json.loads(json.dumps(state)) == state

    for key in (
        "kpis",
        "coverage",
        "pass_fail",
        "resilience_trend",
        "finding_lifecycle",
        "cost",
        "agent_activity",
    ):
        assert key in state


def test_build_state_views_match_observability():
    from forge.dashboard import build_state

    obs = _obs()
    state = build_state(obs)

    snap = obs.snapshot()
    for key in ("coverage", "pass_fail", "resilience_trend", "finding_lifecycle", "cost", "agent_activity"):
        assert state[key] == snap[key]


def test_build_state_kpis_summarize_the_run():
    from forge.dashboard import build_state

    obs = _obs()
    state = build_state(obs)
    kpis = state["kpis"]

    overall = obs.pass_fail()["overall"]
    cost = obs.cost()
    # 7 verdicts: 1 success (exploit), 5 fail (defended), 1 partial
    assert kpis["attempts"] == 7
    assert kpis["exploits"] == 1
    assert kpis["resilience"] == overall["pass_rate"]
    assert kpis["total_usd"] == cost["total_usd"]
    assert kpis["usd_per_attempt"] == cost["usd_per_attempt"]


# --------------------------------------------------------------------------- #
# render_html
# --------------------------------------------------------------------------- #
def test_render_html_is_self_contained_document():
    from forge.dashboard import build_state, render_html

    html = render_html(build_state(_obs()))
    assert isinstance(html, str)
    assert html.lstrip().lower().startswith("<!doctype html")
    # self-contained: no external scripts or stylesheets
    assert 'src="http' not in html
    assert 'href="http' not in html
    assert "cdn" not in html.lower()


def test_render_html_carries_the_approved_design():
    from forge.dashboard import build_state, render_html

    html = render_html(build_state(_obs()))
    assert "Agent Forge" in html
    assert "#2968e6" in html  # approved accent
    for heading in (
        "Pass / fail by category",
        "Resilience trend",
        "OWASP coverage",
        "Cost",
        "Findings",
        "Live agent activity",
    ):
        assert heading in html


def test_render_html_embeds_initial_state_and_polls_api():
    from forge.dashboard import build_state, render_html

    state = build_state(_obs())
    html = render_html(state)

    # the exact state is embedded for immediate (no-flash) render
    m = re.search(
        r'<script id="initial-state" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert m, "initial-state script block must be present"
    assert json.loads(m.group(1)) == state

    # and the page polls the JSON endpoint on an interval to stay live
    assert "/api/state" in html
    assert "setInterval" in html


# --------------------------------------------------------------------------- #
# handle_path (pure router)
# --------------------------------------------------------------------------- #
def test_handle_path_serves_index_html():
    from forge.dashboard import handle_path, build_state

    state = build_state(_obs())
    for path in ("/", "/index.html"):
        status, ctype, body = handle_path(path, lambda: state)
        assert status == 200
        assert ctype == "text/html; charset=utf-8"
        assert body.lstrip().lower().startswith("<!doctype html")


def test_handle_path_serves_state_json_and_ignores_query():
    from forge.dashboard import handle_path, build_state

    state = build_state(_obs())
    status, ctype, body = handle_path("/api/state?ts=123", lambda: state)
    assert status == 200
    assert ctype == "application/json"
    assert json.loads(body) == state


def test_handle_path_health_and_404():
    from forge.dashboard import handle_path, build_state

    state = build_state(_obs())
    ok_status, _, _ = handle_path("/health", lambda: state)
    assert ok_status == 200

    nf_status, _, _ = handle_path("/does-not-exist", lambda: state)
    assert nf_status == 404


def test_handle_path_calls_state_provider_fresh_each_request():
    from forge.dashboard import handle_path, build_state

    calls = {"n": 0}

    def provider():
        calls["n"] += 1
        return build_state(_obs())

    handle_path("/api/state", provider)
    handle_path("/api/state", provider)
    assert calls["n"] == 2  # live: re-queried every request, not cached


# --------------------------------------------------------------------------- #
# resolve_bind + CLI wiring
# --------------------------------------------------------------------------- #
def test_resolve_bind_precedence():
    from forge.dashboard import resolve_bind

    # explicit --port wins over PORT env
    host, port = resolve_bind(SimpleNamespace(host="127.0.0.1", port=8080), {"PORT": "9999"})
    assert (host, port) == ("127.0.0.1", 8080)

    # PORT env (Railway) used when --port is absent
    host, port = resolve_bind(SimpleNamespace(host=None, port=None), {"PORT": "9999"})
    assert host == "0.0.0.0"
    assert port == 9999

    # default when nothing is set
    host, port = resolve_bind(SimpleNamespace(host=None, port=None), {})
    assert (host, port) == ("0.0.0.0", 8000)


def test_cli_parse_args_serve_and_run_coexist():
    from forge.run import parse_args

    s = parse_args(["serve", "--host", "127.0.0.1", "--port", "8080"])
    assert s.command == "serve"
    assert s.host == "127.0.0.1"
    assert s.port == 8080

    # the existing run subcommand still parses
    r = parse_args(["run", "--suite"])
    assert r.command == "run"
    assert r.suite is True


# --------------------------------------------------------------------------- #
# end-to-end contract: a real server answering real requests
# --------------------------------------------------------------------------- #
def test_make_server_answers_real_requests(tmp_path):
    from forge.dashboard import make_server, build_state

    store = _seed()
    # ticket 070: build_state now counts reports from reports_dir; pin BOTH sides to the same
    # (empty) dir so the router==handler equivalence check is hermetic (independent of repo reports/).
    rd = str(tmp_path)
    expected = build_state(Observability(store, cases=CASES), reports_dir=rd)

    server = make_server(store, host="127.0.0.1", port=0, cases=CASES, reports_dir=rd)
    host, port = server.server_address[0], server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/state", timeout=5) as resp:
            assert resp.status == 200
            payload = json.loads(resp.read().decode("utf-8"))
        # the live wire payload matches the pure build_state (router == http handler)
        assert payload == expected

        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=5) as resp:
            assert resp.status == 200
            page = resp.read().decode("utf-8")
        assert page.lstrip().lower().startswith("<!doctype html")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
