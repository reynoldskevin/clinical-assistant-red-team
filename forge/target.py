"""Target Adapter — the sole egress to the live OpenEMR Co-Pilot sidecar (ticket 005).

All outbound calls to the target under test flow through :class:`TargetAdapter`.
The adapter resolves the target id against the 023 allowlist (no raw URLs), mints
the per-pid bearer via an injected ``token_provider``, persists a redacted
transcript of every call, and maps transport failures / 5xx to a typed
:class:`TargetUnreachable`. A 4xx is returned as a structured observation (an
attack signal, not an error).

Stdlib only.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

_REDACTED_AUTH = "Bearer ***redacted***"
_DEFAULT_TIMEOUT = 90


# --------------------------------------------------------------------------- #
# Transport layer types
# --------------------------------------------------------------------------- #
@dataclass
class TransportResponse:
    """A parsed HTTP response returned by a transport for ANY status."""

    status: int
    body: dict


class TransportError(Exception):
    """A transport-level failure (connection refused, DNS, timeout, TLS)."""


# --------------------------------------------------------------------------- #
# Adapter-level types
# --------------------------------------------------------------------------- #
class TargetUnreachable(Exception):
    """The target could not be reached or returned a server-side failure."""


@dataclass
class TargetResponse:
    """A call result wrapping the parsed HTTP status + body."""

    status: int
    body: dict

    @property
    def ok(self) -> bool:
        return self.status == 200

    @property
    def answer(self):
        return self.body.get("answer")

    @property
    def correlation_id(self):
        return self.body.get("correlation_id")


# --------------------------------------------------------------------------- #
# Default transport (urllib) — used only when no transport is injected
# --------------------------------------------------------------------------- #
def _make_default_transport(timeout: int) -> Callable[..., TransportResponse]:
    """Build a urllib-backed transport closure capturing ``timeout``."""

    def _default_transport(
        method: str, url: str, headers: dict, json_body: Optional[dict]
    ) -> TransportResponse:
        data = json.dumps(json_body).encode() if json_body is not None else None
        req = urllib.request.Request(url, method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
                try:
                    body = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    body = {"raw": text}
                return TransportResponse(status=resp.status, body=body)
        except urllib.error.HTTPError as err:
            # 4xx/5xx are real responses the adapter maps itself.
            text = ""
            try:
                text = err.read().decode("utf-8", "replace")
            except Exception:
                text = ""
            try:
                body = json.loads(text) if text else {}
            except json.JSONDecodeError:
                body = {"raw": text}
            return TransportResponse(status=err.code, body=body)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            raise TransportError(str(err)) from err

    return _default_transport


# --------------------------------------------------------------------------- #
# The adapter
# --------------------------------------------------------------------------- #
class TargetAdapter:
    """Sole egress to a single registered target under test."""

    def __init__(
        self,
        registry,
        target_id: str,
        *,
        token_provider: Callable[[int], str],
        store,
        transport: Optional[Callable[..., TransportResponse]] = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        # Resolve at construction: an unlisted id / raw URL raises TargetNotAllowed
        # (not caught here — construction fails loudly).
        self._target = registry.resolve(target_id)
        self._token_provider = token_provider
        self._store = store
        self._transport = transport if transport is not None else _make_default_transport(timeout)
        # One conversation (session) id, reused across all ask turns.
        self._conversation_id = str(uuid.uuid4())

    @property
    def _base_url(self) -> str:
        return self._target.base_url

    def _auth_headers(self, pid: int) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self._token_provider(pid),
        }

    def _persist(self, endpoint: str, status: int, request_body: dict, response_body: dict) -> None:
        self._store.append_event(
            {
                "kind": "target_call",
                "endpoint": endpoint,
                "status": status,
                "request": request_body,
                "request_headers": {
                    "Content-Type": "application/json",
                    "Authorization": _REDACTED_AUTH,
                },
                "response": response_body,
            }
        )

    def _call(self, method: str, endpoint: str, headers: dict, body: Optional[dict]) -> TransportResponse:
        try:
            return self._transport(method, self._base_url + endpoint, headers, body)
        except TransportError as err:
            raise TargetUnreachable(f"{endpoint} unreachable: {err}") from err

    def _map(self, endpoint: str, resp: TransportResponse) -> TargetResponse:
        if resp.status >= 500:
            raise TargetUnreachable(f"{endpoint} returned {resp.status}")
        return TargetResponse(status=resp.status, body=resp.body)

    def ask(self, pid: int, question: str) -> TargetResponse:
        body = {"pid": pid, "question": question, "conversation_id": self._conversation_id}
        headers = self._auth_headers(pid)
        resp = self._call("POST", "/ask", headers, body)
        self._persist("/ask", resp.status, body, resp.body)
        return self._map("/ask", resp)

    def extract(self, pid: int, document_id: int, doc_type: str) -> TargetResponse:
        body = {"pid": pid, "document_id": document_id, "doc_type": doc_type}
        headers = self._auth_headers(pid)
        resp = self._call("POST", "/extract", headers, body)
        self._persist("/extract", resp.status, body, resp.body)
        return self._map("/extract", resp)

    def health(self) -> TargetResponse:
        # Unauthenticated liveness probe: no Authorization header.
        resp = self._call("GET", "/health", {}, None)
        return self._map("/health", resp)
