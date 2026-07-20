# Seed eval suite — OpenEMR Clinical Co-Pilot red-team cases

This directory holds the seed adversarial eval dataset. Each `*.json` file in
this directory (top level only — subdirectories are not scanned) is a case file
loaded by `forge.evals.load_cases()`. A file may contain a single case **object**
or a JSON **list** of case objects. This `README.md` is documentation only and is
not parsed as a case.

## Case schema (`forge.evals.EvalCase`, pydantic v2)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | `str` | no | Defaults to `"v1"`. |
| `id` | `str` | yes | Unique across the entire suite. |
| `category` | `str` | yes | One of the six canonical attack categories (below). |
| `subcategory` | `str \| None` | no | Free-form refinement. |
| `prompt` | `str \| None` | no* | Single-turn attack text. |
| `input_sequence` | `list[str] \| None` | no* | Multi-turn attack; each item is one turn. |
| `expected_behavior` | `str` | yes | What a SAFE target should do (refuse / redact / require authorization). |
| `observed_behavior` | `str \| None` | no | Slot a run fills in later; starts unset. |
| `severity` | `"critical" \| "high" \| "medium" \| "low"` | yes | |
| `add_to_regression` | `bool` | no | Defaults `false`; `true` for crown-jewel cross-patient / exfiltration cases. |
| `owasp_web` | `list[str]` | no** | OWASP Web Top 10 (2021) ids. |
| `owasp_llm` | `list[str]` | no** | OWASP LLM Top 10 ids. |

\* A case must have **either** a `prompt` **or** a non-empty `input_sequence`.

\** At least **one** of `owasp_web` / `owasp_llm` must be non-empty (required
OWASP mapping). Omitting both raises a validation error.

## Validation rules

- At least one OWASP taxonomy (`owasp_web` or `owasp_llm`) must be non-empty.
- A case must provide a `prompt` or a non-empty `input_sequence`.
- `severity` must be one of the four literals.

Invalid case files cause `load_cases()` to raise `EvalCaseError`, naming the
offending file.

## Attack categories

- `prompt_injection`
- `data_exfiltration`
- `state_corruption`
- `tool_misuse`
- `denial_of_service`
- `identity_exploitation`

## OWASP id examples

- Web: `A01:2021-Broken Access Control`, `A03:2021-Injection`,
  `A07:2021-Identification and Authentication Failures`,
  `A10:2021-Server-Side Request Forgery (SSRF)`.
- LLM: `LLM01:Prompt Injection`, `LLM04:Model Denial of Service`,
  `LLM06:Sensitive Information Disclosure`, `LLM07:Insecure Plugin Design`,
  `LLM08:Excessive Agency`.
