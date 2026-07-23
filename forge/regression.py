"""Regression & Validation Harness (ticket 017).

Turns a Judge-confirmed exploit into a deterministic regression case, then on a
trigger replays the recorded probe through the Adapter and asks the Judge whether
the unsafe behavior is *genuinely* gone. The pass/fail is a MEANINGFUL judgment
made entirely by the Judge — never an output diff against the recorded transcript.
The harness also detects reappearance of a previously-fixed vuln and flags
cross-category regressions.

Cases and replay outcomes are persisted as events (kinds ``regression_case`` and
``regression_result``) since there is no dedicated case-table accessor.

Stdlib + forge imports only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from forge.judge import JudgeError
from forge.phi import extract_markers
from forge.schemas import AttackAttempt, Verdict

# Worst-first ranking used to pick a representative verdict across replays:
# the most-compromised outcome wins.
_VERDICT_RANK = {"success": 3, "partial": 2, "error": 1, "fail": 0}


@dataclass
class RegressionResult:
    """The outcome of replaying one regression case."""

    case_id: str
    category: str
    verdict: str
    passed: bool
    reappeared: bool = False
    cross_category: bool = False
    reproduction_rate: str = ""
    repro_count: int = 0
    replays: int = 0
    detected_markers: list = field(default_factory=list)


class RegressionHarness:
    """Creates, lists, and replays Judge-confirmed regression cases."""

    def __init__(self, store, adapter, judge, *, pid: int = 1, replays: int = 3):
        self._store = store
        self._adapter = adapter
        self._judge = judge
        self._pid = pid
        self._replays = replays

    # ------------------------------------------------------------------ #
    # case identity
    # ------------------------------------------------------------------ #
    def _case_key(self, attempt: AttackAttempt) -> str:
        """Stable id from category + attacker-turn contents + prompt."""
        attacker_contents = [
            str(t.get("content", ""))
            for t in attempt.transcript
            if t.get("role") == "attacker"
        ]
        material = "\x00".join([attempt.category, *attacker_contents, attempt.prompt])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ #
    # compromise signature (ticket 049)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _target_answers(transcript) -> list[str]:
        return [
            str(t.get("answer", ""))
            for t in (transcript or [])
            if t.get("role") == "target"
        ]

    def _compromise_signature(self, transcript, verdict: Verdict) -> dict:
        material = self._target_answers(transcript) + [verdict.rationale]
        markers = extract_markers("\n".join(material))
        return {
            "markers": markers,
            "rationale": verdict.rationale,
            "owasp_web": list(verdict.owasp_web),
            "owasp_llm": list(verdict.owasp_llm),
        }

    def _derive_signature(self, transcript) -> dict:
        answers = self._target_answers(transcript)
        if not answers:
            return {"markers": [], "rationale": "", "owasp_web": [], "owasp_llm": []}
        return {
            "markers": extract_markers("\n".join(answers)),
            "rationale": "",
            "owasp_web": [],
            "owasp_llm": [],
        }

    # ------------------------------------------------------------------ #
    # case creation / listing
    # ------------------------------------------------------------------ #
    def create_case(self, verdict: Verdict, attempt: AttackAttempt) -> dict:
        if verdict.verdict != "success":
            raise ValueError(
                "only confirmed exploits (verdict='success') become regression cases"
            )
        signature = self._compromise_signature(attempt.transcript, verdict)
        case = {
            "case_id": self._case_key(attempt),
            "category": attempt.category,
            "prompt": attempt.prompt,
            "target_id": attempt.target_id,
            "transcript": attempt.transcript,
            "compromise_signature": signature,
        }
        self._store.append_event(
            {
                "kind": "regression_case",
                "case_id": case["case_id"],
                "category": case["category"],
                "status": "active",
                **case,
            }
        )
        return case

    def list_cases(self) -> list[dict]:
        cases: dict[str, dict] = {}
        for ev in self._store.get_events():
            if ev.get("kind") != "regression_case":
                continue
            cid = ev.get("case_id")
            if cid in cases:
                continue
            transcript = ev.get("transcript", [])
            signature = ev.get("compromise_signature")
            if signature is None:
                signature = self._derive_signature(transcript)
            cases[cid] = {
                "case_id": cid,
                "category": ev.get("category"),
                "prompt": ev.get("prompt"),
                "target_id": ev.get("target_id"),
                "transcript": transcript,
                "compromise_signature": signature,
            }
        return list(cases.values())

    # ------------------------------------------------------------------ #
    # replay helpers
    # ------------------------------------------------------------------ #
    def _attacker_prompts(self, case: dict) -> list[str]:
        prompts = [
            str(t.get("content", ""))
            for t in case.get("transcript", [])
            if t.get("role") == "attacker"
        ]
        return prompts or [case["prompt"]]

    def _last_status(self, case_id: str) -> str:
        status = "active"
        for ev in self._store.get_events():
            if ev.get("case_id") != case_id:
                continue
            if ev.get("kind") not in ("regression_case", "regression_result"):
                continue
            if ev.get("status") is not None:
                status = ev["status"]
        return status

    # ------------------------------------------------------------------ #
    # replay / validate
    # ------------------------------------------------------------------ #
    def replay(self, case: dict, *, changed_category=None) -> RegressionResult:
        prior = self._last_status(case["case_id"])

        prompts = self._attacker_prompts(case)
        markers = case.get("compromise_signature", {}).get("markers", [])

        repro_count = 0
        rationales: list[str] = []
        verdicts_seen: list[str] = []
        detected: set[str] = set()
        # The Judge is a pure function of the replayed attempt, so identical
        # replies (the common deterministic case) are evaluated once and reused.
        # This also preserves the ticket-017 back-compat contract where a
        # single Verdict is expected per replay() of a deterministic target.
        judge_cache: dict[str, tuple[str, str]] = {}

        for _ in range(self._replays):
            transcript: list[dict] = []
            for prompt in prompts:
                resp = self._adapter.ask(self._pid, prompt)
                transcript.append({"role": "attacker", "content": prompt})
                transcript.append(
                    {
                        "role": "target",
                        "answer": resp.answer,
                        "correlation_id": resp.correlation_id,
                        "status": resp.status,
                        "body": resp.body,
                    }
                )

            reply = "".join(
                str(t.get("answer", ""))
                for t in transcript
                if t.get("role") == "target"
            )
            reply_lower = reply.lower()
            seen = [m for m in markers if str(m).lower() in reply_lower]
            detected.update(seen)
            marker_hit = bool(seen)

            if reply in judge_cache:
                run_verdict, run_rationale = judge_cache[reply]
            else:
                replayed = AttackAttempt(
                    category=case["category"],
                    prompt=case["prompt"],
                    target_id=case.get("target_id"),
                    turns=len(prompts),
                    transcript=transcript,
                )
                try:
                    verdict = self._judge.evaluate(replayed)
                    run_verdict, run_rationale = verdict.verdict, verdict.rationale
                except JudgeError as exc:
                    run_verdict, run_rationale = "error", f"JudgeError: {exc}"
                judge_cache[reply] = (run_verdict, run_rationale)

            rationales.append(run_rationale)
            verdicts_seen.append(run_verdict)
            if run_verdict != "fail" or marker_hit:
                repro_count += 1

        passed = repro_count == 0
        reproduction_rate = f"{repro_count}/{self._replays}"
        detected_markers = sorted(detected)
        reappeared = (prior == "fixed") and (not passed)
        cross_category = bool(
            reappeared
            and changed_category is not None
            and case["category"] != changed_category
        )
        verdict_repr = max(
            verdicts_seen, key=lambda v: _VERDICT_RANK.get(v, -1), default="fail"
        )

        self._store.append_event(
            {
                "kind": "regression_result",
                "case_id": case["case_id"],
                "category": case["category"],
                "status": "fixed" if passed else "vulnerable",
                "verdict": verdict_repr,
                "passed": passed,
                "reappeared": reappeared,
                "cross_category": cross_category,
                "reproduction_rate": reproduction_rate,
                "replays": self._replays,
                "repro_count": repro_count,
                "detected_markers": detected_markers,
                "rationales": rationales,
            }
        )

        return RegressionResult(
            case_id=case["case_id"],
            category=case["category"],
            verdict=verdict_repr,
            passed=passed,
            reappeared=reappeared,
            cross_category=cross_category,
            reproduction_rate=reproduction_rate,
            repro_count=repro_count,
            replays=self._replays,
            detected_markers=detected_markers,
        )

    def validate(self, changed_category=None) -> list[RegressionResult]:
        return [
            self.replay(case, changed_category=changed_category)
            for case in self.list_cases()
        ]
