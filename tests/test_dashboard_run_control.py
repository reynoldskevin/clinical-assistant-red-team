"""Dashboard run-control redesign: header timers, Start-run button, and the
token-gated ``POST /api/run`` trigger.

- ``build_state`` exposes ``run_started_at`` / ``last_run_ended`` (epoch seconds).
- ``handle_run_trigger`` is the pure, token-gated trigger handler.
- ``make_server`` answers ``POST /api/run`` end-to-end, invoking the injected
  launcher only on an authorized, idle request.
- the header carries a plain-text status slot + a Start-run button.
"""

import json
import re
import threading
import urllib.error
import urllib.request

from forge.store import Store
from forge.observability import Observability
from forge.dashboard import (
    build_state,
    handle_run_trigger,
    make_server,
    render_html,
)


def _obs(events=()):
    s = Store(":memory:")
    for ev in events:
        s.append_event(ev)
    return Observability(s)


# --------------------------------------------------------------------------- #
# build_state timestamps
# --------------------------------------------------------------------------- #
def test_build_state_exposes_run_timestamps():
    state = build_state(_obs([
        {"kind": "run_start", "ts": 1000.0},
        {"kind": "run_end", "ts": 1050.0},
    ]))
    assert state["run_started_at"] == 1000.0
    assert state["last_run_ended"] == 1050.0
    assert state["run_active"] is False
    assert json.loads(json.dumps(state)) == state  # wire-serializable


def test_build_state_timestamps_none_when_untimestamped():
    # Since ticket 047 the store auto-stamps ``ts`` on every event, so an
    # "untimestamped" (legacy) run_start is expressed as an explicit ``ts: None``
    # — build_state must still surface it as None rather than a bogus time.
    state = build_state(_obs([{"kind": "run_start", "ts": None}]))
    assert state["run_started_at"] is None
    assert state["last_run_ended"] is None
    assert state["run_active"] is True


# --------------------------------------------------------------------------- #
# handle_run_trigger (pure)
# --------------------------------------------------------------------------- #
def test_trigger_503_when_not_configured():
    calls = []
    status, _, _ = handle_run_trigger(
        "x", configured_token="", run_active=False, launcher=lambda: calls.append(1))
    assert status == 503
    assert calls == []


def test_trigger_401_on_missing_or_wrong_token():
    calls = []
    for tok in ("", "wrong"):
        status, _, _ = handle_run_trigger(
            tok, configured_token="secret", run_active=False, launcher=lambda: calls.append(1))
        assert status == 401
    assert calls == []


def test_trigger_409_when_a_run_is_active():
    calls = []
    status, _, _ = handle_run_trigger(
        "secret", configured_token="secret", run_active=True, launcher=lambda: calls.append(1))
    assert status == 409
    assert calls == []


def test_trigger_202_launches_when_authorized_and_idle():
    calls = []
    status, ctype, body = handle_run_trigger(
        "secret", configured_token="secret", run_active=False, launcher=lambda: calls.append(1))
    assert status == 202
    assert calls == [1]
    assert json.loads(body)["status"] == "started"


# --------------------------------------------------------------------------- #
# end-to-end POST /api/run
# --------------------------------------------------------------------------- #
def test_post_api_run_end_to_end():
    calls = []
    store = Store(":memory:")
    server = make_server(store, host="127.0.0.1", port=0,
                         run_launcher=lambda: calls.append(1), run_token="secret")
    host, port = server.server_address[0], server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    try:
        # authorized + idle → 202 and the launcher fires
        req = urllib.request.Request(base + "/api/run", method="POST",
                                     headers={"X-Run-Token": "secret"})
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 202
        assert calls == [1]

        # wrong token → 401, launcher not fired again
        req = urllib.request.Request(base + "/api/run", method="POST",
                                     headers={"X-Run-Token": "nope"})
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected 401")
        except urllib.error.HTTPError as e:
            assert e.code == 401
        assert calls == [1]

        # an active run → 409
        store.append_event({"kind": "run_start", "ts": 1.0})
        req = urllib.request.Request(base + "/api/run", method="POST",
                                     headers={"X-Run-Token": "secret"})
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected 409")
        except urllib.error.HTTPError as e:
            assert e.code == 409
        assert calls == [1]

        # GET routes still work
        with urllib.request.urlopen(base + "/health", timeout=5) as r:
            assert r.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --------------------------------------------------------------------------- #
# header structure
# --------------------------------------------------------------------------- #
def test_header_has_statusmeta_and_start_button():
    html = render_html(build_state(_obs([{"kind": "run_start", "ts": 1.0}])))
    assert 'id="statusmeta"' in html          # plain-text status slot
    assert 'id="start-run"' in html           # start-run button
    # button starts hidden (JS reveals it when idle)
    assert re.search(r'<button[^>]*id="start-run"[^>]*hidden', html)
    assert 'id="runstate"' in html
    assert 'id="refresh-pill"' in html
    # the button POSTs to the token-gated endpoint
    assert "/api/run" in html
    assert "X-Run-Token" in html
    assert "forge_run_token" in html          # localStorage token key


def test_header_meta_is_plain_text_not_a_pill():
    html = render_html(build_state(_obs([{"kind": "run_start", "ts": 1.0}])))
    # .statusmeta styled as plain text (no pill border/background/radius rule)
    m = re.search(r"\.statusmeta \{([^}]*)\}", html)
    assert m, "statusmeta style missing"
    assert "border-radius" not in m.group(1)
    assert "border:" not in m.group(1)
