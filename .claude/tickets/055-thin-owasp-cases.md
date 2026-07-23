---
id: 055
title: Eval cases for thin OWASP coverage areas
status: todo
depends_on: []
branch: ticket/055-thin-owasp-cases
base_branch: main
test_command: ".venv/bin/pytest tests/test_thin_owasp_cases.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Six OWASP areas are barely exercised because only 1–2 seed cases carry them. Now
that the autonomous loop is seed-driven (054), add well-crafted attack cases for
those areas so real runs elicit them and the Judge tags them, lifting their
(honest, 053) coverage. New cases target: A05 Security Misconfiguration, A09
Logging & Monitoring Failures, LLM02 Insecure Output Handling, LLM05 Supply Chain,
A06 Vulnerable/Outdated Components, and additional A10 SSRF.

## Acceptance criteria
- [ ] `forge.evals.load_cases()` loads the whole catalog without error (every new
      case passes `EvalCase` validation).
- [ ] The catalog contains these new cases (each a valid `EvalCase` with a
      non-empty `prompt` or `input_sequence`, a non-empty `expected_behavior`,
      `add_to_regression: false`, and the given primary OWASP tag), placed in the
      matching category file:
  - `misc-001-verbose-error-disclosure` (tool_misuse) — `A05:2021-Security Misconfiguration`
  - `misc-002-debug-config-probe` (prompt_injection) — `A05:2021-Security Misconfiguration`
  - `log-001-silent-break-glass` (identity_exploitation) — `A09:2021-Security Logging and Monitoring Failures`
  - `log-002-repeated-auth-failure` (identity_exploitation) — `A09:2021-Security Logging and Monitoring Failures`
  - `out-001-html-script-injection` (prompt_injection) — `LLM02:Insecure Output Handling`
  - `out-002-markdown-exfil-link` (prompt_injection) — `LLM02:Insecure Output Handling`
  - `sup-001-tampered-tool-provenance` (tool_misuse) — `LLM05:Supply Chain Vulnerabilities`
  - `comp-001-outdated-component-probe` (tool_misuse) — `A06:2021-Vulnerable and Outdated Components`
  - `ssrf-010-internal-rebind` (tool_misuse) — `A10:2021-Server-Side Request Forgery (SSRF)`
- [ ] After the additions each thin OWASP id is carried by ≥1 case, A10 by ≥3.
- [ ] No existing case is modified or removed; the catalog only grows.

## Test plan (orchestrator authors these)
- unit (`tests/test_thin_owasp_cases.py`):
  - `load_cases()` succeeds; total case count grew.
  - each required new id is present with its expected `category`, a non-empty
    prompt/sequence + expected_behavior, `add_to_regression is False`, and its
    primary OWASP tag in `owasp_web`/`owasp_llm`.
  - each thin OWASP id is now covered by ≥1 case (A10 ≥3).
