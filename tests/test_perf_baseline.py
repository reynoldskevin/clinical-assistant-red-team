"""Acceptance tests for ticket 068 — perf baseline artifact + regression SLO.

`baseline_run` profiles the platform under a 100-case offline load (wall/CPU/memory +
throughput); `REGRESSION_SLO_SECONDS` + a deterministic scan test gate the full-DB regression
overhead in CI; `PERF_BASELINE.md` is the committed evidence artifact.
"""

import pathlib
import time

from forge.perf import baseline_run, REGRESSION_SLO_SECONDS
from forge.regression import RegressionHarness
from forge.schemas import AttackAttempt, Verdict
from forge.store import Store
from forge.target import TargetResponse

_ROOT = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# baseline_run
# --------------------------------------------------------------------------- #
def test_baseline_run_returns_profiled_metrics():
    b = baseline_run(cases=20)  # small N for test speed; offline, no API key
    for key in ("cases", "wall_s", "cpu_s", "peak_mem_kb", "throughput_cps", "load_summary"):
        assert key in b, f"missing baseline key: {key}"
    assert b["cases"] == 20
    assert b["wall_s"] >= 0.0
    assert b["cpu_s"] >= 0.0
    assert b["peak_mem_kb"] >= 0.0
    assert b["throughput_cps"] >= 0.0
    assert b["load_summary"]["cases"] == 20
    assert b["load_summary"]["successes"] == 20  # offline stub returns 200


# --------------------------------------------------------------------------- #
# regression SLO (CI gate)
# --------------------------------------------------------------------------- #
class _FakeAdapter:
    target_id = "copilot"

    def ask(self, pid, question):
        return TargetResponse(status=200, body={"answer": "defended now", "correlation_id": "c"})


class _FakeJudge:
    def evaluate(self, attempt, *, ground_truth=None):
        return Verdict(verdict="fail", confidence=0.9, rationale="defended",
                       owasp_web=[], owasp_llm=[])


def _attempt(i):
    p = f"reveal patient {i} meds"
    return AttackAttempt(
        category="data_exfiltration", prompt=p, target_id="copilot", turns=1,
        transcript=[
            {"role": "attacker", "content": p},
            {"role": "target", "answer": "Patient meds: lisinopril.",
             "correlation_id": "c0", "status": 200, "body": {}},
        ],
    )


def _success():
    return Verdict(verdict="success", confidence=0.9, rationale="exploited",
                   owasp_web=[], owasp_llm=[])


def test_regression_scan_meets_slo():
    # the budget must be real, not a no-op
    assert 0 < REGRESSION_SLO_SECONDS <= 60

    store = Store(":memory:")
    harness = RegressionHarness(store, _FakeAdapter(), _FakeJudge(), pid=1)
    for i in range(25):
        harness.create_case(_success(), _attempt(i))

    start = time.perf_counter()
    results = harness.validate()
    elapsed = time.perf_counter() - start

    assert len(results) == 25  # full DB scanned
    assert elapsed < REGRESSION_SLO_SECONDS, f"regression scan {elapsed:.2f}s exceeded SLO"


# --------------------------------------------------------------------------- #
# committed evidence artifact
# --------------------------------------------------------------------------- #
def test_perf_baseline_doc_present_and_complete():
    path = _ROOT / "PERF_BASELINE.md"
    assert path.exists(), "PERF_BASELINE.md must be committed at the repo root"
    text = path.read_text()
    for section in ("Methodology", "Baseline Metrics", "Bottleneck", "Remediation", "Regression SLO"):
        assert section in text, f"missing section: {section}"
    assert "|" in text                       # a metrics table
    assert "100" in text                     # 100-case representative run
    assert "AI_COST_ANALYSIS.md" in text     # scaling remediation cross-reference
    assert "tests/test_perf_baseline.py" in text  # cites the SLO/baseline test
