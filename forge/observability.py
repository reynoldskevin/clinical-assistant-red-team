"""Observability read-model + metrics over the SQLite store (ticket 016).

Derives six views from the store's events / findings / cost rows:

    1. coverage          — categories attempted + per-OWASP mapping
    2. pass_fail         — exploited / defended / partial + pass_rate
    3. resilience_trend  — pass_rate over target versions, ordered
    4. finding_lifecycle — open / in_progress / resolved counts
    5. cost              — totals + per-category USD/tokens + per-attempt rate
    6. agent_activity    — ordered, labeled per-agent action log

Verdict semantics: verdict "success" = attack worked = target EXPLOITED;
"fail" = target DEFENDED; "partial" = partial. pass_rate = defended / attempts.

Stdlib-only, defensive: missing keys default sensibly, empty store never crashes.
"""

from __future__ import annotations

# kind -> agent label for the activity log
_AGENT_BY_KIND = {
    "run_start": "orchestrator",
    "run_end": "orchestrator",
    "attack": "red_team",
    "verdict": "judge",
    "target_call": "adapter",
    "audit": "operator",
    "regression_result": "regression",
    "vuln_report": "documentation",
    "vuln_report_link": "documentation",
}


def _empty_bucket() -> dict:
    return {"attempts": 0, "exploits": 0, "defended": 0, "partial": 0, "pass_rate": 0.0}


def _finalize_bucket(bucket: dict) -> dict:
    attempts = bucket["attempts"]
    bucket["pass_rate"] = (bucket["defended"] / attempts) if attempts else 0.0
    return bucket


class Observability:
    """Read-model answering the six required observability questions."""

    def __init__(self, store, *, cases=None):
        self.store = store
        self.cases = list(cases) if cases is not None else None

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #
    def _verdicts(self) -> list[dict]:
        return [e for e in self.store.get_events() if e.get("kind") == "verdict"]

    # ------------------------------------------------------------------ #
    # 1. coverage
    # ------------------------------------------------------------------ #
    def coverage(self) -> dict:
        by_category: dict[str, int] = {}
        for ev in self._verdicts():
            cat = ev.get("category")
            by_category[cat] = by_category.get(cat, 0) + 1

        by_owasp: dict[str, int] = {}
        if self.cases is not None:
            for case in self.cases:
                cat = getattr(case, "category", None)
                owasp_ids = list(getattr(case, "owasp_web", []) or []) + list(
                    getattr(case, "owasp_llm", []) or []
                )
                attempts = by_category.get(cat, 0)
                for owasp_id in owasp_ids:
                    by_owasp[owasp_id] = by_owasp.get(owasp_id, 0) + attempts

        return {"by_category": by_category, "by_owasp": by_owasp}

    # ------------------------------------------------------------------ #
    # 2. pass / fail
    # ------------------------------------------------------------------ #
    def pass_fail(self) -> dict:
        overall = _empty_bucket()
        by_category: dict[str, dict] = {}
        by_version: dict[str, dict] = {}

        for ev in self._verdicts():
            verdict = ev.get("verdict")
            cat = ev.get("category")
            ver = ev.get("target_version")
            cat_bucket = by_category.setdefault(cat, _empty_bucket())
            ver_bucket = by_version.setdefault(ver, _empty_bucket())
            for bucket in (overall, cat_bucket, ver_bucket):
                bucket["attempts"] += 1
                if verdict == "success":
                    bucket["exploits"] += 1
                elif verdict == "fail":
                    bucket["defended"] += 1
                elif verdict == "partial":
                    bucket["partial"] += 1

        _finalize_bucket(overall)
        for bucket in by_category.values():
            _finalize_bucket(bucket)
        for bucket in by_version.values():
            _finalize_bucket(bucket)

        return {"overall": overall, "by_category": by_category, "by_version": by_version}

    # ------------------------------------------------------------------ #
    # 3. resilience trend
    # ------------------------------------------------------------------ #
    def resilience_trend(self) -> list[dict]:
        by_version = self.pass_fail()["by_version"]
        return [
            {
                "version": ver,
                "pass_rate": by_version[ver]["pass_rate"],
                "attempts": by_version[ver]["attempts"],
            }
            for ver in sorted(by_version, key=lambda v: (v is None, v))
        ]

    # ------------------------------------------------------------------ #
    # 4. finding lifecycle
    # ------------------------------------------------------------------ #
    def finding_lifecycle(self) -> dict:
        counts = {"open": 0, "in_progress": 0, "resolved": 0}
        for finding in self.store.list_findings():
            status = finding.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    # ------------------------------------------------------------------ #
    # 5. cost
    # ------------------------------------------------------------------ #
    def cost(self) -> dict:
        total_usd = 0.0
        total_input = 0
        total_output = 0
        by_category: dict[str, float] = {}

        for row in self.store.get_costs():
            usd = row.get("usd", 0) or 0
            total_usd += usd
            total_input += row.get("input_tokens", 0) or 0
            total_output += row.get("output_tokens", 0) or 0
            cat = row.get("category")
            by_category[cat] = by_category.get(cat, 0.0) + usd

        total_attempts = len(self._verdicts())
        usd_per_attempt = (total_usd / total_attempts) if total_attempts else 0.0

        return {
            "total_usd": total_usd,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "by_category": by_category,
            "usd_per_attempt": usd_per_attempt,
        }

    # ------------------------------------------------------------------ #
    # 6. agent activity
    # ------------------------------------------------------------------ #
    def agent_activity(self) -> list[dict]:
        activity = []
        for ev in self.store.get_events():
            kind = ev.get("kind")
            activity.append(
                {
                    "seq": ev.get("id"),
                    "agent": _AGENT_BY_KIND.get(kind, kind),
                    "kind": kind,
                    "category": ev.get("category"),
                    "ts": ev.get("ts"),
                }
            )
        return activity

    # ------------------------------------------------------------------ #
    # agent-level cost from trace spans (ticket 024)
    # ------------------------------------------------------------------ #
    def agent_cost(self) -> dict[str, float]:
        by_agent: dict[str, float] = {}
        for ev in self.store.get_events():
            if ev.get("kind") != "trace_span":
                continue
            agent = ev.get("agent")
            cost = ev.get("cost_usd", 0.0) or 0.0
            by_agent[agent] = by_agent.get(agent, 0.0) + cost
        return by_agent

    # ------------------------------------------------------------------ #
    # combined snapshot
    # ------------------------------------------------------------------ #
    def snapshot(self) -> dict:
        return {
            "coverage": self.coverage(),
            "pass_fail": self.pass_fail(),
            "resilience_trend": self.resilience_trend(),
            "finding_lifecycle": self.finding_lifecycle(),
            "cost": self.cost(),
            "agent_activity": self.agent_activity(),
        }
