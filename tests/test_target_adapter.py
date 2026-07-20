"""Acceptance tests for ticket 005 — Target Adapter (sole egress to the live Co-Pilot).

These tests are the FIXED contract for the adapter. They pin:
- `from forge.target import TargetAdapter, TargetResponse, TargetUnreachable,
   TransportResponse, TransportError`
- `TargetAdapter(registry, target_id, *, token_provider, store, transport)` — resolves the
  target id via the 023 allowlist (a raw URL / unlisted id is refused with `TargetNotAllowed`).
- `transport(method, url, headers, json_body) -> TransportResponse` is the injected, mockable
  egress. A transport raising `TransportError` OR an HTTP 5xx maps to `TargetUnreachable`; a 4xx is
  returned as a structured observation; a 200 is parsed.
- The emitted `/ask` body conforms to the vendored `contracts/ask_request.schema.json`, and a real
  `AskResponse` conforms to `contracts/ask_response.schema.json` (wire contract test).
- The persisted transcript never contains the raw bearer token.
"""

import json
import pathlib

import jsonschema
import pytest

CONTRACTS = pathlib.Path(__file__).resolve().parents[1] / "contracts"


def _registry():
    from forge.access import TargetRegistry

    return TargetRegistry({"copilot": {"base_url": "https://copilot.test"}})


class FakeTransport:
    """Records every egress call; returns a canned TransportResponse or raises."""

    def __init__(self, response=None, error=None):
        self.calls = []
        self._response = response
        self._error = error

    def __call__(self, method, url, headers, json_body):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "json_body": json_body}
        )
        if self._error is not None:
            raise self._error
        return self._response


def _store():
    from forge.store import Store

    return Store(":memory:")


def _adapter(transport, *, store=None, token_provider=None, target_id="copilot"):
    from forge.target import TargetAdapter

    return TargetAdapter(
        _registry(),
        target_id,
        token_provider=token_provider or (lambda pid: "SECRET-JWT"),
        store=store or _store(),
        transport=transport,
    )


def _ok(body):
    from forge.target import TransportResponse

    return TransportResponse(status=200, body=body)


ASK_OK = {"answer": "grounded answer", "correlation_id": "corr-123"}


# --- imports & allowlist ---------------------------------------------------

def test_imports():
    from forge.target import (  # noqa: F401
        TargetAdapter,
        TargetResponse,
        TargetUnreachable,
        TransportResponse,
        TransportError,
    )


def test_unlisted_or_raw_url_target_refused():
    from forge.access import TargetNotAllowed

    for bad in ["https://evil.example.com", "evil-target", "copilot.test:8080"]:
        with pytest.raises(TargetNotAllowed):
            _adapter(FakeTransport(_ok(ASK_OK)), target_id=bad)


# --- /ask happy path -------------------------------------------------------

def test_ask_sends_askrequest_and_parses_response():
    t = FakeTransport(_ok(ASK_OK))
    a = _adapter(t)
    resp = a.ask(pid=7, question="what meds is the patient on?")

    assert resp.status == 200
    assert resp.ok is True
    assert resp.answer == "grounded answer"
    assert resp.correlation_id == "corr-123"

    call = t.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://copilot.test/ask"
    body = call["json_body"]
    assert body["pid"] == 7
    assert body["question"] == "what meds is the patient on?"
    assert "conversation_id" in body  # present (generated session id)


def test_bearer_header_uses_token_provider_per_pid():
    tokens = {1: "jwt-for-1", 2: "jwt-for-2"}
    t = FakeTransport(_ok(ASK_OK))
    a = _adapter(t, token_provider=lambda pid: tokens[pid])
    a.ask(pid=2, question="q")
    assert t.calls[0]["headers"]["Authorization"] == "Bearer jwt-for-2"


def test_multi_turn_reuses_conversation_id():
    t = FakeTransport(_ok(ASK_OK))
    a = _adapter(t)
    a.ask(pid=1, question="turn one")
    a.ask(pid=1, question="turn two")
    cid1 = t.calls[0]["json_body"]["conversation_id"]
    cid2 = t.calls[1]["json_body"]["conversation_id"]
    assert cid1 is not None
    assert cid1 == cid2


# --- error mapping ---------------------------------------------------------

def test_4xx_returned_as_structured_observation():
    from forge.target import TransportResponse

    t = FakeTransport(TransportResponse(status=401, body={"error": "missing bearer token"}))
    a = _adapter(t)
    resp = a.ask(pid=1, question="q")
    assert resp.status == 401
    assert resp.ok is False
    assert resp.body["error"] == "missing bearer token"


def test_5xx_raises_target_unreachable():
    from forge.target import TransportResponse, TargetUnreachable

    t = FakeTransport(TransportResponse(status=502, body={"error": "upstream llm"}))
    a = _adapter(t)
    with pytest.raises(TargetUnreachable):
        a.ask(pid=1, question="q")


def test_transport_error_raises_target_unreachable():
    from forge.target import TransportError, TargetUnreachable

    t = FakeTransport(error=TransportError("connection refused"))
    a = _adapter(t)
    with pytest.raises(TargetUnreachable):
        a.ask(pid=1, question="q")


# --- transcript persistence (token redaction) ------------------------------

def test_transcript_persisted_with_token_redacted():
    s = _store()
    t = FakeTransport(_ok(ASK_OK))
    a = _adapter(t, store=s, token_provider=lambda pid: "SUPER-SECRET-JWT")
    a.ask(pid=1, question="q")

    calls = [e for e in s.get_events() if e.get("kind") == "target_call"]
    assert len(calls) == 1
    rec = calls[0]
    # the raw token must NOT appear anywhere in the persisted transcript
    assert "SUPER-SECRET-JWT" not in json.dumps(rec)
    # but the request + response are captured for replay
    assert rec["endpoint"] == "/ask"
    assert rec["status"] == 200
    assert rec["request"]["pid"] == 1
    assert rec["response"]["correlation_id"] == "corr-123"


# --- health & extract ------------------------------------------------------

def test_health_is_unauthenticated_get():
    t = FakeTransport(_ok({"status": "ok", "service": "ai-sidecar"}))
    a = _adapter(t)
    resp = a.health()
    assert resp.ok is True
    call = t.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://copilot.test/health"
    assert call["headers"].get("Authorization") is None  # no bearer on the liveness probe


def test_health_transport_error_is_unreachable():
    from forge.target import TransportError, TargetUnreachable

    t = FakeTransport(error=TransportError("down"))
    a = _adapter(t)
    with pytest.raises(TargetUnreachable):
        a.health()


def test_extract_sends_extractrequest_shape():
    body = {
        "ok": True,
        "doc_type": "lab_pdf",
        "confidence": 0.9,
        "low_confidence": False,
        "unsupported_fields": [],
        "fact": {},
        "correlation_id": "c",
    }
    t = FakeTransport(_ok(body))
    a = _adapter(t)
    resp = a.extract(pid=1, document_id=5, doc_type="lab_pdf")
    assert resp.status == 200
    assert t.calls[0]["url"] == "https://copilot.test/extract"
    assert t.calls[0]["json_body"] == {"pid": 1, "document_id": 5, "doc_type": "lab_pdf"}


# --- wire contract test (anchored to the vendored producer spec) -----------

def test_emitted_ask_request_conforms_to_vendored_contract():
    schema = json.loads((CONTRACTS / "ask_request.schema.json").read_text())
    t = FakeTransport(_ok(ASK_OK))
    a = _adapter(t)
    a.ask(pid=3, question="hello")
    body = t.calls[0]["json_body"]

    jsonschema.validate(body, schema)  # emitted request must conform to the sidecar's spec
    # the sidecar's request model is strict (extra=forbid) → an unknown field must be rejected
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**body, "injected_field": "x"}, schema)


def test_response_parsing_matches_vendored_contract():
    schema = json.loads((CONTRACTS / "ask_response.schema.json").read_text())
    jsonschema.validate(ASK_OK, schema)  # the canonical response conforms
    t = FakeTransport(_ok(ASK_OK))
    a = _adapter(t)
    resp = a.ask(pid=1, question="q")
    assert resp.answer == ASK_OK["answer"]
    assert resp.correlation_id == ASK_OK["correlation_id"]
