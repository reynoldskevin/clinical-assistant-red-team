"""Acceptance tests for ticket 072 — the vulnerability-report corpus.

Guards the submission requirement of >= 3 DISTINCT, schema-valid vulnerability reports, and pins
the two findings adjudicated from the production `partial` verdicts.
"""

import glob
import json
import pathlib

from forge.schemas import VulnReport

_ROOT = pathlib.Path(__file__).resolve().parents[1]

_NEW = {
    "VULN-data_exfiltration-unverified-role-disclosure": "A01:2021-Broken Access Control",
    "VULN-denial_of_service-broad-query-overdisclosure": "A04:2021-Insecure Design",
}
_REQUIRED = ("id", "severity", "description", "clinical_impact",
             "reproduction", "observed", "expected", "remediation")


def _reports():
    out = {}
    for p in glob.glob(str(_ROOT / "reports" / "*.json")):
        out[pathlib.Path(p).name] = json.loads(pathlib.Path(p).read_text())
    return out


def test_at_least_three_schema_valid_reports():
    reps = _reports()
    assert len(reps) >= 3, "submission needs >= 3 vulnerability reports"
    for name, d in reps.items():
        VulnReport(**d)  # raises on any schema violation


def test_every_report_has_nonempty_required_fields():
    for name, d in _reports().items():
        for field in _REQUIRED:
            assert d.get(field) and str(d[field]).strip(), f"{name}: empty {field}"


def test_two_new_distinct_findings_present_with_owasp():
    by_id = {d["id"]: d for d in _reports().values()}
    for new_id, owasp in _NEW.items():
        assert new_id in by_id, f"missing distinct finding: {new_id}"
        assert owasp in by_id[new_id].get("owasp_web", []), f"{new_id}: expected {owasp}"


def test_corpus_spans_three_distinct_mechanisms():
    ids = {d["id"] for d in _reports().values()}
    # 1) the existing incidental-leak-on-refusal family
    assert any("06edd052" in i or "9a0c65e6" in i for i in ids)
    # 2) unverified-authorization disclosure, 3) minimum-necessary over-answering
    assert "VULN-data_exfiltration-unverified-role-disclosure" in ids
    assert "VULN-denial_of_service-broad-query-overdisclosure" in ids
