"""Acceptance tests for ticket 025 — failure-handling policy + circuit breaker.

Pins the FIXED contract:

- `AgentFailure(error: ErrorResult)` — the exception an agent op raises to signal
  a typed failure the policy must handle.
- `FailurePolicy(*, max_retries=3, breaker=None, sleep=..., backoff=0.0)`:
    - `classify(error_type) -> "transient" | "hard"` — target_unreachable /
      judge_timeout are transient; budget_exceeded / no_findings_in_window are hard.
    - `execute(fn) -> Outcome` — runs `fn`; on `AgentFailure` a transient error is
      retried with backoff up to `max_retries` then resolves `action="skip"`; a
      hard error resolves `action="halt"` immediately; a clean call → `action="ok"`.
- `CircuitBreaker(threshold, store=None)` — `record_failure()` counts failures and,
  on reaching `threshold`, logs a `circuit_breaker` event (if a store is set) and
  raises `CircuitOpen`. A tripped breaker aborts the run (no cascading loop).
"""

import pytest

from forge.failure import (
    AgentFailure,
    CircuitBreaker,
    CircuitOpen,
    FailurePolicy,
    Outcome,
)
from forge.schemas import ErrorResult, ErrorType
from forge.store import Store


def _fail(error_type):
    return AgentFailure(ErrorResult(error_type=error_type, detail="boom"))


class Recorder:
    """A sleep spy — records each backoff duration, never actually sleeps."""

    def __init__(self):
        self.sleeps = []

    def __call__(self, seconds):
        self.sleeps.append(seconds)


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "error_type", [ErrorType.target_unreachable, ErrorType.judge_timeout]
)
def test_transient_error_types(error_type):
    assert FailurePolicy().classify(error_type) == "transient"


@pytest.mark.parametrize(
    "error_type", [ErrorType.budget_exceeded, ErrorType.no_findings_in_window]
)
def test_hard_error_types(error_type):
    assert FailurePolicy().classify(error_type) == "hard"


# --------------------------------------------------------------------------- #
# (1) transient → bounded retry-with-backoff → skip (not a crash)
# --------------------------------------------------------------------------- #
def test_transient_retries_then_skips():
    sleep = Recorder()
    policy = FailurePolicy(max_retries=3, sleep=sleep, backoff=0.25)

    calls = {"n": 0}

    def always_transient():
        calls["n"] += 1
        raise _fail(ErrorType.target_unreachable)

    outcome = policy.execute(always_transient)
    assert isinstance(outcome, Outcome)
    assert outcome.ok is False
    assert outcome.action == "skip", "exhausted transient retries redirect/skip, not crash"
    assert outcome.attempts == 4, "1 initial try + 3 retries"
    assert calls["n"] == 4
    assert sleep.sleeps == [0.25, 0.25, 0.25], "backoff between each retry"
    assert outcome.error_type == ErrorType.target_unreachable


def test_transient_that_recovers_returns_ok():
    policy = FailurePolicy(max_retries=3, sleep=Recorder())
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _fail(ErrorType.judge_timeout)
        return "recovered"

    outcome = policy.execute(flaky)
    assert outcome.ok is True
    assert outcome.action == "ok"
    assert outcome.value == "recovered"
    assert outcome.attempts == 3


# --------------------------------------------------------------------------- #
# (2) hard error → halt/redirect path immediately (no retry)
# --------------------------------------------------------------------------- #
def test_hard_error_halts_without_retry():
    sleep = Recorder()
    policy = FailurePolicy(max_retries=3, sleep=sleep)
    calls = {"n": 0}

    def hard():
        calls["n"] += 1
        raise _fail(ErrorType.budget_exceeded)

    outcome = policy.execute(hard)
    assert outcome.ok is False
    assert outcome.action == "halt", "a hard error routes to halt/redirect"
    assert outcome.attempts == 1, "hard errors are not retried"
    assert calls["n"] == 1
    assert sleep.sleeps == [], "no backoff on a hard error"
    assert outcome.error_type == ErrorType.budget_exceeded


# --------------------------------------------------------------------------- #
# (3) K failures within a run trips the circuit breaker
# --------------------------------------------------------------------------- #
def test_circuit_breaker_trips_after_k_failures_and_logs():
    store = Store(":memory:")
    breaker = CircuitBreaker(threshold=3, store=store)
    policy = FailurePolicy(max_retries=0, breaker=breaker, sleep=Recorder())

    def hard():
        raise _fail(ErrorType.budget_exceeded)

    # first two failures are absorbed (breaker not yet at threshold)
    for _ in range(2):
        outcome = policy.execute(hard)
        assert outcome.action == "halt"
    assert breaker.tripped is False
    assert breaker.failures == 2

    # the 3rd failure trips the breaker → run aborts
    with pytest.raises(CircuitOpen):
        policy.execute(hard)
    assert breaker.tripped is True

    events = [e for e in store.get_events() if e.get("kind") == "circuit_breaker"]
    assert len(events) == 1, "the breaker trip is logged to events"
    assert events[0].get("failures") == 3


def test_circuit_breaker_counts_across_retries_of_one_op():
    # A single transient op that exhausts its retries counts as ONE agent failure,
    # not one-per-retry — K is measured in failed operations.
    breaker = CircuitBreaker(threshold=2)
    policy = FailurePolicy(max_retries=2, breaker=breaker, sleep=Recorder())

    def transient():
        raise _fail(ErrorType.target_unreachable)

    outcome = policy.execute(transient)
    assert outcome.action == "skip"
    assert breaker.failures == 1, "one exhausted op = one breaker failure"
    assert breaker.tripped is False


def test_breaker_without_store_still_trips():
    breaker = CircuitBreaker(threshold=1)
    with pytest.raises(CircuitOpen):
        breaker.record_failure()
    assert breaker.tripped is True
