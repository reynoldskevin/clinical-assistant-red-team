"""LLM client interface and Claude implementation.

Provides a mockable seam over the Anthropic SDK so provider calls can be
injected in tests (no network, no real `anthropic` package required).
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """Structured result of an LLM completion."""

    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMError(Exception):
    """Raised when an LLM provider call fails (after retries, if applicable)."""


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for an LLM client capable of chat completions."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...


_TRANSIENT_NAME_MARKERS = (
    "RateLimit",
    "Timeout",
    "Connection",
    "APIStatus",
    "Overloaded",
    "InternalServer",
    "ServiceUnavailable",
    "APIConnection",
)


def _default_is_transient(exc: Exception) -> bool:
    """Default policy: is this exception worth retrying?"""
    name = type(exc).__name__
    if any(marker in name for marker in _TRANSIENT_NAME_MARKERS):
        return True

    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
    try:
        if status is not None and int(status) >= 500:
            return True
    except (TypeError, ValueError):
        pass

    return False


class ClaudeClient:
    """Anthropic-backed implementation of the LLMClient protocol."""

    def __init__(
        self,
        api_key: str,
        client: Any = None,
        max_retries: int = 3,
        backoff: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        is_transient: Callable[[Exception], bool] = _default_is_transient,
    ) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        self._api_key = api_key
        self._client = client
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep
        self._is_transient = is_transient

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        attempts = 1 + self._max_retries
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                create_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                }
                if system is not None:
                    create_kwargs["system"] = system
                resp = self._client.messages.create(**create_kwargs)
            except Exception as exc:  # noqa: BLE001 - re-raised as LLMError below
                last_exc = exc
                if not self._is_transient(exc):
                    raise LLMError(
                        f"Non-transient LLM error: {exc}"
                    ) from exc
                if attempt < attempts - 1:
                    self._sleep(self._backoff)
                    continue
                raise LLMError(
                    f"LLM call failed after {attempts} attempts: {exc}"
                ) from exc
            else:
                text: str | None = None
                for block in getattr(resp, "content", None) or []:
                    block_text = getattr(block, "text", None)
                    if block_text is not None:
                        text = block_text
                        break
                if text is None:
                    raise LLMError(
                        "LLM returned an empty/refusal content response "
                        "(no text block in content)"
                    )
                return LLMResponse(
                    text=text,
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                    model=model,
                )

        # Unreachable, but keeps type checkers content.
        raise LLMError(f"LLM call failed: {last_exc}")


def _urllib_transport(
    *, api_key: str | None, timeout: int
) -> Callable[[str, dict], dict]:
    """Build a default urllib-based transport that POSTs JSON and raises on non-2xx.

    Not exercised by tests (they inject a transport), but must be import-safe.
    """

    def transport(url: str, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if not (200 <= int(status) < 300):
                raise LLMError(f"HTTP {status} from {url}")
            return json.loads(resp.read().decode("utf-8"))

    return transport


class OpenAICompatClient:
    """OpenAI-compatible chat client (Ollama / any /v1/chat/completions endpoint)."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        transport: Callable[[str, dict], dict] | None = None,
        path: str = "/v1/chat/completions",
        timeout: int = 30,
    ) -> None:
        self._url = base_url.rstrip("/") + path
        self._api_key = api_key
        if transport is None:
            transport = _urllib_transport(api_key=api_key, timeout=timeout)
        self._transport = transport

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        msgs = list(messages)
        if system is not None:
            msgs = [{"role": "system", "content": system}, *msgs]

        body = {"model": model, "messages": msgs, "max_tokens": max_tokens}

        try:
            data = self._transport(self._url, body)
        except Exception as exc:  # noqa: BLE001 - re-raised as LLMError
            raise LLMError(f"OpenAI-compat transport failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
            input_tokens = data["usage"]["prompt_tokens"]
            output_tokens = data["usage"]["completion_tokens"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Malformed OpenAI-compat response: {exc}"
            ) from exc

        if text is None:
            raise LLMError("OpenAI-compat response contained no content")

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=data.get("model") or model,
        )


def build_llm_client(
    role: str,
    config: Any,
    *,
    transport: Callable[[str, dict], dict] | None = None,
    claude_client: Any = None,
    api_key: str | None = None,
) -> LLMClient:
    """Build the configured LLMClient for a role from ``config.providers``."""
    provider = config.providers.get(role, {}) if config.providers else {}
    if provider.get("kind") == "openai-compat":
        return OpenAICompatClient(
            base_url=provider["base_url"],
            api_key=api_key or config.anthropic_api_key,
            transport=transport,
        )
    return ClaudeClient(api_key=config.anthropic_api_key, client=claude_client)
