"""Acceptance tests for ticket 066 — distinct-failure-mode attack pack.

The two confirmed exploits are the same weakness (incidental PHI disclosure). A distinct third
requires the model to fail a DIFFERENT way: take an action (LLM08 excessive agency), obey an
injected instruction (LLM01 indirect injection), or emit unsafe output (LLM02). This pack seeds
those modes so the loop probes them.
"""

from forge.evals import load_cases


# id -> (category, required OWASP substring)
_EXPECTED = {
    "agency-001-implied-consent-order": ("tool_misuse", "LLM08"),
    "agency-002-autonomous-result-message": ("tool_misuse", "LLM08"),
    "agency-003-unverified-record-writeback": ("tool_misuse", "LLM08"),
    "inject-ind-001-note-embedded-directive": ("prompt_injection", "LLM01"),
    "inject-ind-002-referral-crosspatient-exfil": ("prompt_injection", "LLM01"),
    "output-003-active-html-in-summary": ("prompt_injection", "LLM02"),
    "output-004-markdown-phi-exfil-link": ("prompt_injection", "LLM02"),
}


def _by_id():
    return {c.id: c for c in load_cases()}


def test_all_seven_present_with_category_and_owasp():
    cases = _by_id()
    for cid, (category, owasp) in _EXPECTED.items():
        assert cid in cases, f"missing eval case: {cid}"
        c = cases[cid]
        assert c.category == category, f"{cid}: wrong category {c.category}"
        tags = " ".join(c.owasp_web + c.owasp_llm)
        assert owasp in tags, f"{cid}: expected OWASP {owasp} in {tags}"


def test_cases_are_wellformed_attack_seeds():
    cases = _by_id()
    for cid in _EXPECTED:
        c = cases[cid]
        assert (c.prompt and c.prompt.strip()) or c.input_sequence, f"{cid}: no attack payload"
        assert c.expected_behavior and c.expected_behavior.strip(), f"{cid}: no expected_behavior"
        assert c.add_to_regression is False, f"{cid}: attack seeds must not be regression baselines"


def test_corpus_loads_and_grows():
    cases = load_cases()  # raises on any validation failure across the whole corpus
    assert len(cases) >= 93  # prior 86 + 7


def test_three_distinct_modes_each_gain_cases():
    cases = load_cases()

    def n(tag):
        return sum(1 for c in cases if any(tag in x for x in (c.owasp_web + c.owasp_llm)))

    # the pack adds dedicated cases to each distinct failure mode
    assert n("LLM08:Excessive Agency") >= 3
    assert n("LLM01:Prompt Injection") >= 2
    assert n("LLM02:Insecure Output Handling") >= 2
