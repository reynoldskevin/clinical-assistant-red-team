"""Ticket 069 — submission self-check + deterministic offline repro harness.

Two capabilities behind one command (``python -m forge.submission``):

1. ``missing_artifacts()`` — an artifact-presence check that fails if any
   submission deliverable goes missing from the repo.
2. ``reproduce()`` — a deterministic, offline "mock re-run" that drives the full
   four-agent deployed loop (`build_autonomous_runner` + `run_autonomous`)
   against in-process fakes: no network, no ``ANTHROPIC_API_KEY``, no writes to
   the repo ``reports/`` dir. Two calls return an IDENTICAL summary dict.
"""

from __future__ import annotations

import argparse
import pathlib
from types import SimpleNamespace

from forge.run import CostMeter, build_autonomous_runner
from forge.schemas import AttackAttempt, Verdict
from forge.store import Store
from forge.target import TargetResponse


# --------------------------------------------------------------------------- #
# artifact-presence check
# --------------------------------------------------------------------------- #
def _repo_root() -> pathlib.Path:
    """The repo root: the directory containing ``forge/``."""
    return pathlib.Path(__file__).resolve().parents[1]


# Submission deliverables named by the brief + key evidence. Every path here
# MUST currently exist in the repo (the self-check asserts an empty result).
REQUIRED_ARTIFACTS: list[str] = [
    "THREAT_MODEL.md",
    "USERS.md",
    "ARCHITECTURE.md",
    "ARCHITECTURE_DIAGRAM.md",
    "AI_COST_ANALYSIS.md",
    "EVAL_RESULTS.md",
    "README.md",
    "evals",
    "reports",
    "contracts/agent",
]


def missing_artifacts(root=None) -> list[str]:
    """Return the REQUIRED_ARTIFACTS whose ``(root / path)`` does not exist.

    ``root`` defaults to the repo root. Pointed at an empty dir it returns every
    listed artifact.
    """
    base = pathlib.Path(root) if root is not None else _repo_root()
    return [p for p in REQUIRED_ARTIFACTS if not (base / p).exists()]


# --------------------------------------------------------------------------- #
# deterministic in-process fakes (the "mock re-run" harness)
# --------------------------------------------------------------------------- #
_REFUSAL = "I can't help with that request."

_CATEGORIES = [
    "data_exfiltration",
    "denial_of_service",
    "identity_exploitation",
    "prompt_injection",
    "state_corruption",
    "tool_misuse",
]


class _MockTarget:
    """Fixed offline target adapter — always refuses."""

    target_id = "copilot"

    def ask(self, pid, question):
        return TargetResponse(
            status=200,
            body={"answer": _REFUSAL, "correlation_id": "c"},
        )


class _MockRedTeam:
    """Emits one fixed attack attempt per directive."""

    def run(self, directive, pid):
        return [
            AttackAttempt(
                category=directive.category,
                prompt="fixed probe",
                transcript=[
                    {"role": "attacker", "content": "probe"},
                    {"role": "target", "answer": _REFUSAL},
                ],
            )
        ]


class _MockJudge:
    """Always defends (verdict "fail") — no exploits, no findings."""

    def evaluate(self, attempt, *, ground_truth=None):
        return Verdict(
            verdict="fail",
            confidence=0.9,
            rationale="defended",
            owasp_web=[],
            owasp_llm=[],
        )


# --------------------------------------------------------------------------- #
# deterministic offline repro
# --------------------------------------------------------------------------- #
def reproduce(cases=None) -> dict:
    """Drive the full deployed loop against the built-in fakes and return a
    STABLE summary dict derived from the store's events/findings.

    Offline: no ``ANTHROPIC_API_KEY``, no network, no repo ``reports/`` writes
    (all verdicts are "fail", so the Documentation agent drafts nothing).
    """
    if cases is None:
        cases = [
            SimpleNamespace(category=c, owasp_web=[], owasp_llm=[])
            for c in _CATEGORIES
        ]

    store = Store(":memory:")
    runner = build_autonomous_runner(
        store,
        red_team=_MockRedTeam(),
        judge=_MockJudge(),
        adapter=_MockTarget(),
        cases=cases,
        cost_meter=CostMeter(),
        pid=1,
    )
    summary = runner.run_autonomous()

    events = store.get_events()
    attacks = [e for e in events if e.get("kind") == "attack"]
    verdicts = [e for e in events if e.get("kind") == "verdict"]
    exploits = [e for e in verdicts if e.get("verdict") == "success"]
    defended = [e for e in verdicts if e.get("verdict") == "fail"]

    return {
        "attempts": len(attacks),
        "verdicts": len(verdicts),
        "exploits": len(exploits),
        "defended": len(defended),
        "findings": len(store.list_findings()),
        "passed": bool(summary.passed),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_check() -> int:
    missing = set(missing_artifacts())
    for path in REQUIRED_ARTIFACTS:
        status = "MISSING" if path in missing else "present"
        print(f"  {path}: {status}")
    return 1 if missing else 0


def _print_reproduce() -> int:
    print(reproduce())
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="forge.submission")
    parser.add_argument("--check", action="store_true", help="artifact-presence check")
    parser.add_argument("--reproduce", action="store_true", help="deterministic offline repro")
    args = parser.parse_args(argv)

    if args.check:
        return _print_check()
    if args.reproduce:
        return _print_reproduce()

    # No flags: run both (check then reproduce); fail iff artifacts are missing.
    rc = _print_check()
    _print_reproduce()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
