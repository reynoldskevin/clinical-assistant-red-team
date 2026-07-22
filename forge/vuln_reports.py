"""Vulnerability-report generation pipeline (ticket 020).

Turns Judge-confirmed exploits already persisted in the store into distinct,
reproducible Vulnerability Reports by reusing the Documentation agent (015) and
the Regression harness (017). For each DISTINCT confirmed exploit this drafts a
:class:`~forge.schemas.VulnReport`, creates a linked regression case, and writes
``reports/<id>.json`` carrying the report fields plus its ``regression_case_id``
so an absent engineer can reproduce it.

Stdlib + forge imports only.
"""

from __future__ import annotations

import json
from pathlib import Path

from forge.documentation import DataQualityError
from forge.schemas import AttackAttempt, Verdict


def collect_confirmed_exploits(store) -> list[tuple[Verdict, AttackAttempt]]:
    """Reconstruct each confirmed exploit (Verdict + AttackAttempt) from the store."""
    confidence_by_attempt: dict = {}
    for event in store.get_events():
        if event.get("kind") == "verdict" and event.get("verdict") == "success":
            aid = event.get("attempt_id")
            if aid is not None:
                confidence_by_attempt[aid] = event.get("confidence", 0.8)

    pairs: list[tuple[Verdict, AttackAttempt]] = []
    for finding in store.list_findings():
        attempt_id = finding.get("attempt_id")
        attempt_row = store.get_attempt(attempt_id) if attempt_id is not None else None
        if attempt_row is None:
            continue

        attempt = AttackAttempt(
            category=attempt_row.get("category"),
            prompt=attempt_row.get("prompt"),
            target_id=attempt_row.get("target_id"),
            turns=attempt_row.get("turns", 1) or 1,
            transcript=attempt_row.get("transcript") or [],
        )
        verdict = Verdict(
            verdict="success",
            confidence=confidence_by_attempt.get(attempt_id, 0.8),
            rationale=finding.get("rationale")
            or f"Confirmed {attempt.category} exploit against the clinical assistant.",
            owasp_web=finding.get("owasp_web") or [],
            owasp_llm=finding.get("owasp_llm") or [],
            rubric_version="v1",
        )
        pairs.append((verdict, attempt))
    return pairs


def generate_reports(store, *, documentation, harness) -> list[dict]:
    """Draft distinct VulnReports + linked regression cases for confirmed exploits."""
    reports_dir = Path(documentation._reports_dir)
    combined_reports: list[dict] = []

    for verdict, attempt in collect_confirmed_exploits(store):
        # DISTINCTNESS: collapse duplicate attack sequences to a single report.
        if documentation.is_duplicate(attempt):
            continue

        try:
            report = documentation.draft(verdict, attempt)
        except DataQualityError:
            continue

        case = harness.create_case(verdict, attempt)

        combined = report.model_dump()
        combined["regression_case_id"] = case["case_id"]

        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{report.id}.json").write_text(json.dumps(combined, indent=2))

        store.append_event(
            {
                "kind": "vuln_report_link",
                "report_id": report.id,
                "case_id": case["case_id"],
            }
        )

        combined_reports.append(combined)

    return combined_reports
