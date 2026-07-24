"""Acceptance tests for ticket 064 — integration packet.

Structural + no-drift test: the packet documents every inter-agent message model, the
contracts/versioning + contract-test results, decision records, and a cross-agent trace
whose order matches what `forge.tracing.Tracer.lineage` actually yields.
"""

import pathlib
import re

from forge.contracts import AGENT_MESSAGES
from forge.tracing import Tracer

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PACKET = _ROOT / "INTEGRATION_PACKET.md"


def _text():
    return _PACKET.read_text()


def test_packet_exists():
    assert _PACKET.exists(), "INTEGRATION_PACKET.md must exist at the repo root"


def test_required_sections_present():
    t = _text()
    for section in (
        "Component Interfaces",
        "Contracts & Versioning",
        "Contract-Test Results",
        "Decision Records",
        "Cross-Agent Trace",
    ):
        assert section in t, f"missing required section: {section}"


def test_every_registered_message_is_documented():
    t = _text()
    for name, model in AGENT_MESSAGES.items():
        assert model.__name__ in t, f"interface not documented: {model.__name__}"


def test_cross_agent_trace_order_matches_tracing():
    tr = Tracer()
    tid = tr.start_trace()
    fid = 1
    for agent in ("red_team", "judge", "documentation"):
        tr.record(agent, trace_id=tid, tokens=1, cost_usd=0.0, latency_s=0.1, finding_id=fid)
    order = [s.agent for s in tr.lineage(fid)]
    chain = " -> ".join(order)
    assert chain in _text(), f"packet must document the real trace chain: {chain}"


def test_cites_contract_test_and_decision_record():
    t = _text()
    assert "tests/test_agent_contracts.py" in t
    assert "DECISION_RECORD_BUILD_VS_CONFIGURE.md" in t


def test_cited_repo_artifacts_all_exist():
    tokens = set(re.findall(r"`([\w./-]+(?:\.(?:md|json|py|txt)|/))`", _text()))
    assert tokens, "packet must cite concrete artifacts"
    for tok in tokens:
        assert (_ROOT / tok).exists(), f"cited artifact does not exist: {tok}"
