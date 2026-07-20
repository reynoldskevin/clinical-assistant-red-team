"""Acceptance tests for ticket 023 — target allowlist + operator auth + audit log.

These tests are the FIXED contract for the platform's safety primitives (consumed by the
Target Adapter, 005). They pin:
- `from forge.access import TargetRegistry, OperatorAuth, AuditLog, Target, Operator,
   AccessError, TargetNotAllowed, AuthError`
- A `target_id` resolves ONLY against a pre-registered allowlist; an unlisted id or a raw URL
  is refused with `TargetNotAllowed` (no agent may smuggle a raw URL as the target).
- Triggering requires a valid operator token; otherwise `AuthError`.
- The audit log appends who/what/when to the store's `events`, and events are append-only:
  an UPDATE or DELETE against `events` fails at the DB level.
"""

import sqlite3

import pytest


def _registry():
    from forge.access import TargetRegistry

    return TargetRegistry(
        {
            "copilot": {
                "base_url": "https://copilot.internal.test",
                "label": "OpenEMR Co-Pilot (non-prod)",
            },
            "copilot-staging": {"base_url": "https://staging.copilot.internal.test"},
        }
    )


def _auth():
    from forge.access import OperatorAuth

    return OperatorAuth({"op-secret-123": "kevin"})


def _store():
    from forge.store import Store

    return Store(":memory:")


def test_imports():
    from forge.access import (  # noqa: F401
        TargetRegistry,
        OperatorAuth,
        AuditLog,
        Target,
        Operator,
        AccessError,
        TargetNotAllowed,
        AuthError,
    )


def test_typed_errors_share_base():
    from forge.access import AccessError, TargetNotAllowed, AuthError

    assert issubclass(TargetNotAllowed, AccessError)
    assert issubclass(AuthError, AccessError)
    assert AccessError is not Exception


# --- Allowlist -------------------------------------------------------------

def test_allowlisted_target_resolves():
    reg = _registry()
    t = reg.resolve("copilot")
    assert t.id == "copilot"
    assert t.base_url == "https://copilot.internal.test"


def test_unlisted_target_refused():
    from forge.access import TargetNotAllowed

    reg = _registry()
    with pytest.raises(TargetNotAllowed):
        reg.resolve("evil-target")


def test_raw_url_refused_as_target_id():
    from forge.access import TargetNotAllowed

    reg = _registry()
    # An agent must never be able to name a raw URL in place of a registered id
    # (SSRF / redirect-the-run protection).
    for raw in [
        "https://evil.example.com",
        "http://169.254.169.254/latest/meta-data",
        "copilot.internal.test:8080",
        "//evil",
    ]:
        with pytest.raises(TargetNotAllowed):
            reg.resolve(raw)


# --- Operator auth ---------------------------------------------------------

def test_valid_operator_authenticates():
    op = _auth().authenticate("op-secret-123")
    assert op.name == "kevin"


def test_invalid_operator_rejected():
    from forge.access import AuthError

    a = _auth()
    for bad in ["", None, "wrong-token", "op-secret-124"]:
        with pytest.raises(AuthError):
            a.authenticate(bad)


def test_non_string_token_rejected_with_typed_error():
    """A wrong-typed token (incl. unhashable) must raise the typed AuthError,
    never a raw TypeError/KeyError leaking to the caller."""
    from forge.access import AuthError

    a = _auth()
    for bad in [123, ["op-secret-123"], {"token": "op-secret-123"}, object(), b"op-secret-123"]:
        with pytest.raises(AuthError):
            a.authenticate(bad)


# --- Audit log -------------------------------------------------------------

def test_audit_records_who_what_when_in_order():
    from forge.access import AuditLog

    s = _store()
    audit = AuditLog(s)
    i1 = audit.record(actor="kevin", action="run_triggered", target_id="copilot")
    i2 = audit.record(
        actor="orchestrator", action="directive_selected", category="prompt_injection"
    )

    assert isinstance(i1, int) and isinstance(i2, int)
    assert i1 < i2  # monotonic append order

    entries = audit.entries()
    assert [e["action"] for e in entries] == ["run_triggered", "directive_selected"]

    first = entries[0]
    assert first["actor"] == "kevin"          # who
    assert first["action"] == "run_triggered"  # what
    assert first["target_id"] == "copilot"     # contextual detail
    assert first.get("when")                    # when — a timestamp is recorded


def test_events_are_append_only():
    from forge.access import AuditLog

    s = _store()
    audit = AuditLog(s)
    audit.record(actor="kevin", action="run_triggered")

    # Tampering with the audit trail must fail at the DB level.
    with pytest.raises(sqlite3.Error):
        s.conn.execute("UPDATE events SET kind='tampered' WHERE id=1")
    with pytest.raises(sqlite3.Error):
        s.conn.execute("DELETE FROM events WHERE id=1")

    # The original entry survived intact.
    entries = audit.entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "run_triggered"
