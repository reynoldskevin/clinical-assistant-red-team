"""Target allowlist + operator auth + append-only audit log (ticket 023).

Standalone safety primitives consumed by the Target Adapter (ticket 005):

- ``TargetRegistry`` — an agent may only name a pre-registered target id, never a
  raw URL (SSRF / redirect-the-run protection).
- ``OperatorAuth`` — triggering a run requires a valid operator token.
- ``AuditLog`` — appends who/what/when to the store's ``events`` table, which is
  made append-only at the DB level (UPDATE/DELETE blocked by triggers).

Stdlib only.
"""

from __future__ import annotations

import datetime
import re
import sqlite3  # noqa: F401  (documented dependency; RAISE(ABORT) surfaces as sqlite3.Error)
from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class AccessError(Exception):
    """Base class for access-control failures."""


class TargetNotAllowed(AccessError):
    """Raised when a target id is not on the allowlist or is not a bare id."""


class AuthError(AccessError):
    """Raised when an operator token is missing or unknown."""


# --------------------------------------------------------------------------- #
# Target allowlist
# --------------------------------------------------------------------------- #
@dataclass
class Target:
    id: str
    base_url: str
    label: str = ""


_BARE_ID = re.compile(r"[A-Za-z0-9_-]+")


class TargetRegistry:
    """Resolve a ``target_id`` against a fixed allowlist of registered targets."""

    def __init__(self, targets: dict):
        self._targets = dict(targets)

    def resolve(self, target_id: str) -> Target:
        # Reject anything that isn't a bare identifier: URLs, host:port, //evil,
        # anything containing ':', '/', '.', etc.
        if not isinstance(target_id, str) or not _BARE_ID.fullmatch(target_id):
            raise TargetNotAllowed(f"invalid target id: {target_id!r}")
        spec = self._targets.get(target_id)
        if spec is None:
            raise TargetNotAllowed(f"target not on allowlist: {target_id!r}")
        return Target(
            id=target_id,
            base_url=spec["base_url"],
            label=spec.get("label", ""),
        )


# --------------------------------------------------------------------------- #
# Operator auth
# --------------------------------------------------------------------------- #
@dataclass
class Operator:
    name: str


class OperatorAuth:
    """Authenticate an operator by opaque token."""

    def __init__(self, tokens: dict):
        self._tokens = dict(tokens)

    def authenticate(self, token) -> Operator:
        if not isinstance(token, str) or token not in self._tokens:
            raise AuthError("invalid operator token")
        return Operator(name=self._tokens[token])


# --------------------------------------------------------------------------- #
# Append-only audit log
# --------------------------------------------------------------------------- #
class AuditLog:
    """Append-only audit trail backed by the store's ``events`` table."""

    def __init__(self, store):
        self._store = store
        # Install DB-level append-only guards. INSERT is still permitted.
        store.conn.execute(
            "CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events "
            "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END"
        )
        store.conn.execute(
            "CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events "
            "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END"
        )

    def record(self, actor: str, action: str, **detail) -> int:
        data = {
            "kind": "audit",
            "actor": actor,
            "action": action,
            "when": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        data.update(detail)
        return self._store.append_event(data)

    def entries(self) -> list[dict]:
        return [e for e in self._store.get_events() if e.get("kind") == "audit"]
