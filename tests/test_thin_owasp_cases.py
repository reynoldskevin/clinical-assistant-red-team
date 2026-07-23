"""Ticket 055 — eval cases for the thin OWASP coverage areas.

New, valid seed cases target the OWASP ids that only 1–2 cases carried, so a
seed-driven autonomous run (054) exercises them and the Judge tags them, lifting
their honest (053) coverage.
"""

from forge.evals import load_cases


def _by_id():
    return {c.id: c for c in load_cases()}


# id -> (expected category, primary OWASP id that must be tagged)
NEW_CASES = {
    "misc-001-verbose-error-disclosure": ("tool_misuse", "A05:2021-Security Misconfiguration"),
    "misc-002-debug-config-probe": ("prompt_injection", "A05:2021-Security Misconfiguration"),
    "log-001-silent-break-glass": ("identity_exploitation", "A09:2021-Security Logging and Monitoring Failures"),
    "log-002-repeated-auth-failure": ("identity_exploitation", "A09:2021-Security Logging and Monitoring Failures"),
    "out-001-html-script-injection": ("prompt_injection", "LLM02:Insecure Output Handling"),
    "out-002-markdown-exfil-link": ("prompt_injection", "LLM02:Insecure Output Handling"),
    "sup-001-tampered-tool-provenance": ("tool_misuse", "LLM05:Supply Chain Vulnerabilities"),
    "comp-001-outdated-component-probe": ("tool_misuse", "A06:2021-Vulnerable and Outdated Components"),
    "ssrf-010-internal-rebind": ("tool_misuse", "A10:2021-Server-Side Request Forgery (SSRF)"),
}

THIN_IDS = {
    "A05:2021-Security Misconfiguration",
    "A09:2021-Security Logging and Monitoring Failures",
    "LLM02:Insecure Output Handling",
    "LLM05:Supply Chain Vulnerabilities",
    "A06:2021-Vulnerable and Outdated Components",
}


def test_catalog_loads_and_grew():
    cases = load_cases()  # raises if any case is invalid
    assert len(cases) >= 77 + len(NEW_CASES)


def test_new_cases_present_and_well_formed():
    by_id = _by_id()
    for cid, (category, owasp_id) in NEW_CASES.items():
        assert cid in by_id, f"missing new case {cid}"
        c = by_id[cid]
        assert c.category == category, f"{cid} category {c.category} != {category}"
        has_probe = bool((c.prompt and c.prompt.strip()) or c.input_sequence)
        assert has_probe, f"{cid} has no prompt/input_sequence"
        assert c.expected_behavior and c.expected_behavior.strip(), f"{cid} missing expected_behavior"
        assert c.add_to_regression is False, f"{cid} must not auto-add to regression"
        assert owasp_id in (list(c.owasp_web) + list(c.owasp_llm)), \
            f"{cid} not tagged with {owasp_id}"


def test_each_thin_id_now_has_a_case():
    tagged = {}
    for c in load_cases():
        for oid in list(c.owasp_web) + list(c.owasp_llm):
            tagged[oid] = tagged.get(oid, 0) + 1
    for oid in THIN_IDS:
        assert tagged.get(oid, 0) >= 1, f"{oid} still has no case"
    # A10 previously had 2 seeds; the new rebind case makes it >= 3
    assert tagged.get("A10:2021-Server-Side Request Forgery (SSRF)", 0) >= 3
