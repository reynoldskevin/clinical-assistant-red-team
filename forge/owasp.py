"""Ticket 019 — OWASP coverage completion.

Defines the canonical set of OWASP Web Top 10 (2021) and OWASP LLM Top 10 (2023)
entries the Co-Pilot red-team suite must cover, and a coverage report that fails
whenever any mandated entry drops to zero mapped eval cases.

Stdlib + typing only. ``coverage_report`` is duck-typed: it accepts any iterable
of objects exposing ``.owasp_web`` and ``.owasp_llm`` list attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

# Canonical mandated labels. Web uses the 2021 numbering; LLM uses the 2023
# numbering. These strings must match exactly how eval cases tag OWASP.
MANDATED_WEB: tuple[str, ...] = (
    "A01:2021-Broken Access Control",
    "A03:2021-Injection",
    "A04:2021-Insecure Design",
    "A06:2021-Vulnerable and Outdated Components",
    "A07:2021-Identification and Authentication Failures",
    "A09:2021-Security Logging and Monitoring Failures",
    "A10:2021-Server-Side Request Forgery (SSRF)",
)

MANDATED_LLM: tuple[str, ...] = (
    "LLM01:Prompt Injection",
    "LLM02:Insecure Output Handling",
    "LLM05:Supply Chain Vulnerabilities",
    "LLM06:Sensitive Information Disclosure",
    "LLM08:Excessive Agency",
)


class _HasOwasp(Protocol):
    owasp_web: list[str]
    owasp_llm: list[str]


@dataclass
class CoverageReport:
    """Coverage of the mandated OWASP entries across a set of eval cases."""

    web: dict[str, int]
    llm: dict[str, int]
    missing: list[str]
    is_complete: bool


def coverage_report(cases: Iterable[_HasOwasp]) -> CoverageReport:
    """Count how many cases map each mandated OWASP entry.

    Counts are scoped to the mandated labels only; non-mandated tags are ignored.
    ``missing`` lists any mandated label (web then llm) with zero coverage.
    """
    web = {label: 0 for label in MANDATED_WEB}
    llm = {label: 0 for label in MANDATED_LLM}

    for case in cases:
        for label in set(case.owasp_web):
            if label in web:
                web[label] += 1
        for label in set(case.owasp_llm):
            if label in llm:
                llm[label] += 1

    missing = [label for label in MANDATED_WEB if web[label] == 0]
    missing += [label for label in MANDATED_LLM if llm[label] == 0]

    return CoverageReport(
        web=web,
        llm=llm,
        missing=missing,
        is_complete=not missing,
    )
