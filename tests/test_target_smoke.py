"""Acceptance tests for ticket 012 — deployed-target smoke + README hard gate.

Two concerns:
1. The Target Adapter reaches the *configured* target's /health endpoint. A
   deterministic check (injected transport) always runs and proves the adapter
   routes to `<base_url>/health`; a live check hits the real target only when
   `TARGET_BASE_URL` is set in the environment, and SKIPS cleanly otherwise.
2. README.md documents the deployed target URL (submission hard gate), states the
   target is non-prod / synthetic-data-only, and documents transcript retention.
"""

import os
import re
from pathlib import Path

import pytest

from forge.access import TargetRegistry
from forge.store import Store
from forge.target import TargetAdapter, TransportResponse

README = Path(__file__).resolve().parents[1] / "README.md"


# --------------------------------------------------------------------------- #
# Adapter smoke — deterministic (injected transport, always runs)
# --------------------------------------------------------------------------- #
def test_adapter_reaches_configured_target_health():
    base = "https://target.example"
    seen = {}

    def fake_transport(method, url, headers, json_body):
        seen["method"] = method
        seen["url"] = url
        return TransportResponse(status=200, body={"status": "ok", "service": "ai-sidecar"})

    registry = TargetRegistry({"copilot": {"base_url": base}})
    adapter = TargetAdapter(
        registry,
        "copilot",
        token_provider=lambda pid: "",
        store=Store(":memory:"),
        transport=fake_transport,
    )

    resp = adapter.health()
    assert resp.ok, "adapter health() should succeed against a 200 target"
    assert seen["method"] == "GET"
    assert seen["url"] == base + "/health", "adapter must hit <base_url>/health"


# --------------------------------------------------------------------------- #
# Adapter smoke — live (only when TARGET_BASE_URL is set; skips otherwise)
# --------------------------------------------------------------------------- #
def test_live_target_health_when_configured():
    base = os.environ.get("TARGET_BASE_URL")
    if not base:
        pytest.skip("TARGET_BASE_URL unset — live target smoke skipped")
    registry = TargetRegistry({"copilot": {"base_url": base}})
    adapter = TargetAdapter(
        registry,
        "copilot",
        token_provider=lambda pid: "",
        store=Store(":memory:"),
        timeout=30,
    )
    resp = adapter.health()
    assert resp.ok, f"live target {base}/health did not return 200"


# --------------------------------------------------------------------------- #
# README hard gate
# --------------------------------------------------------------------------- #
def _readme():
    assert README.exists(), "README.md must exist at the project root"
    return README.read_text(encoding="utf-8")


def test_readme_documents_deployed_target_url():
    text = _readme()
    # A concrete deployed https URL for the target (the submission hard gate).
    assert re.search(r"https://\S+\.up\.railway\.app", text), (
        "README must document the deployed target URL"
    )


def test_readme_states_synthetic_only_and_retention():
    low = _readme().lower()
    assert "synthetic" in low, "README must state the target is synthetic-data-only"
    assert ("no real phi" in low) or ("non-prod" in low) or ("non-production" in low), (
        "README must state the target is non-production / no real PHI"
    )
    assert "retention" in low or "retain" in low, (
        "README must document transcript retention policy"
    )


def test_readme_documents_changes_to_make_target_testable():
    low = _readme().lower()
    # Mentions how the Co-Pilot was made testable (dev-mint token / deploy).
    assert "adapter" in low and ("token" in low or "mint" in low), (
        "README must document how the target is reached/made testable"
    )
