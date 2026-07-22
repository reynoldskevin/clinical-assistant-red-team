"""Ticket 018 — the full autonomous loop as a stdlib state-graph.

Wires Orchestrator → Red Team → Judge → Documentation → Regression → Observability
into a checkpointed, resumable state-graph honoring LangGraph node/edge semantics
without the dependency. Each node mutates a JSON-serializable ``LoopState``; after
every node the graph checkpoints completed progress to the event store so a resume
never re-runs a finished node.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from forge.schemas import AttackAttempt, AttackDirective, Verdict

NODES = ["orchestrate", "attack", "judge", "document", "regress", "observe"]


@dataclass
class LoopState:
    cycle: int = 0
    next_index: int = 0
    directive: dict | None = None
    attempts: list = field(default_factory=list)
    verdicts: list = field(default_factory=list)
    report_id: str | None = None
    case_id: str | None = None
    trace: list = field(default_factory=list)
    done: bool = False


class AutonomousLoop:
    def __init__(
        self,
        *,
        orchestrator,
        red_team,
        judge,
        documentation,
        harness,
        store,
        pid=1,
    ):
        self._orchestrator = orchestrator
        self._red_team = red_team
        # NB: stored as ``_judge_agent`` (not ``_judge``) so it does not shadow the
        # ``_judge`` node method that the NODES-driven ``getattr`` dispatch resolves.
        self._judge_agent = judge
        self._documentation = documentation
        self._harness = harness
        self._store = store
        self._pid = pid

    # ------------------------------------------------------------------ #
    # nodes
    # ------------------------------------------------------------------ #
    def _orchestrate(self, state: LoopState) -> None:
        d = self._orchestrator.next_directive()
        if d is None:
            state.done = True
            return
        state.directive = d.model_dump()
        self._store.append_event({"kind": "directive", "category": d.category})

    def _attack(self, state: LoopState) -> None:
        if state.directive is None:
            return
        directive = AttackDirective(**state.directive)
        attempts = self._red_team.run(directive, self._pid)
        for attempt in attempts:
            aid = self._store.insert_attempt(attempt.model_dump())
            self._store.append_event(
                {"kind": "attack", "attempt_id": aid, "category": attempt.category}
            )
        state.attempts = [a.model_dump() for a in attempts]

    def _judge(self, state: LoopState) -> None:
        for d in state.attempts:
            attempt = AttackAttempt(**d)
            v = self._judge_agent.evaluate(attempt)
            self._store.append_event(
                {
                    "kind": "verdict",
                    "category": attempt.category,
                    "verdict": v.verdict,
                    "confidence": v.confidence,
                }
            )
            if v.verdict == "success":
                self._store.insert_finding(
                    {
                        "severity": "high",
                        "attack_category": attempt.category,
                        "status": "open",
                    }
                )
            state.verdicts.append(v.model_dump())

    def _document(self, state: LoopState) -> None:
        for ad, vd in zip(state.attempts, state.verdicts):
            if vd["verdict"] != "success":
                continue
            verdict = Verdict(**vd)
            attempt = AttackAttempt(**ad)
            report = self._documentation.draft(verdict, attempt)
            state.report_id = report.id

    def _regress(self, state: LoopState) -> None:
        for ad, vd in zip(state.attempts, state.verdicts):
            if vd["verdict"] != "success":
                continue
            verdict = Verdict(**vd)
            attempt = AttackAttempt(**ad)
            case = self._harness.create_case(verdict, attempt)
            state.case_id = case["case_id"]

    def _observe(self, state: LoopState) -> None:
        self._store.append_event({"kind": "run_end"})

    # ------------------------------------------------------------------ #
    # checkpointing
    # ------------------------------------------------------------------ #
    def _checkpoint(self, state: LoopState) -> None:
        self._store.append_event(
            {
                "kind": "loop_checkpoint",
                "next_index": state.next_index,
                "state": dataclasses.asdict(state),
            }
        )

    def latest_checkpoint(self) -> LoopState | None:
        latest = None
        for ev in self._store.get_events():
            if ev.get("kind") == "loop_checkpoint":
                latest = ev
        if latest is None:
            return None
        return LoopState(**latest["state"])

    # ------------------------------------------------------------------ #
    # driver
    # ------------------------------------------------------------------ #
    def run(self, state: LoopState | None = None, *, max_steps=None) -> LoopState:
        if state is None:
            state = LoopState()
        steps = 0
        while state.next_index < len(NODES) and not state.done:
            if max_steps is not None and steps >= max_steps:
                break
            node = NODES[state.next_index]
            getattr(self, "_" + node)(state)
            state.trace.append(node)
            state.next_index += 1
            self._checkpoint(state)
            steps += 1
        if state.next_index >= len(NODES):
            state.done = True
        return state
