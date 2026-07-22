"""Agent failure-handling policy + circuit breaker (ticket 025).

An agent operation signals a typed failure by raising :class:`AgentFailure`,
which carries an :class:`~forge.schemas.ErrorResult`. :class:`FailurePolicy`
classifies the error, retries transient failures with backoff (bounded), and
routes hard failures to a halt. A :class:`CircuitBreaker` counts failed
operations across a run and, once it reaches its threshold, logs a
``circuit_breaker`` event and raises :class:`CircuitOpen` to abort the run.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from forge.schemas import ErrorResult, ErrorType

_TRANSIENT: frozenset[ErrorType] = frozenset(
    {ErrorType.target_unreachable, ErrorType.judge_timeout}
)


class AgentFailure(Exception):
    """Raised by an agent op to signal a typed failure the policy handles."""

    def __init__(self, error: ErrorResult):
        super().__init__(str(getattr(error, "detail", "")))
        self.error = error


class CircuitOpen(Exception):
    """Raised when the circuit breaker trips and the run must abort."""


@dataclass
class Outcome:
    """The resolved result of running an op through a :class:`FailurePolicy`."""

    ok: bool
    value: object = None
    action: str = "ok"  # one of "ok" | "skip" | "halt"
    attempts: int = 1
    error_type: ErrorType | None = None


class CircuitBreaker:
    """Counts failed operations; trips (and logs) once ``threshold`` is hit."""

    def __init__(self, threshold: int, store=None):
        self.threshold = threshold
        self.store = store
        self.failures = 0
        self.tripped = False

    def record_failure(self, reason: str = "failure_threshold_exceeded") -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.tripped = True
            if self.store is not None:
                # Log BEFORE raising so the event persists.
                self.store.append_event(
                    {
                        "kind": "circuit_breaker",
                        "reason": reason,
                        "failures": self.failures,
                        "threshold": self.threshold,
                    }
                )
            raise CircuitOpen(
                f"circuit breaker tripped after {self.failures} failures"
            )


class FailurePolicy:
    """Classifies failures and runs ops with bounded retry/backoff."""

    def __init__(
        self,
        *,
        max_retries: int = 3,
        breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], None] = time.sleep,
        backoff: float = 0.0,
    ):
        self.max_retries = max_retries
        self.breaker = breaker
        self.sleep = sleep
        self.backoff = backoff

    def classify(self, error_type: ErrorType) -> str:
        return "transient" if error_type in _TRANSIENT else "hard"

    def _record_breaker_failure(self) -> None:
        if self.breaker is not None:
            self.breaker.record_failure()

    def execute(self, fn: Callable[[], object]) -> Outcome:
        attempts = 0
        error_type: ErrorType | None = None
        while True:
            attempts += 1
            try:
                value = fn()
            except AgentFailure as exc:
                error_type = exc.error.error_type
                if self.classify(error_type) == "hard":
                    self._record_breaker_failure()
                    return Outcome(
                        ok=False,
                        action="halt",
                        attempts=attempts,
                        error_type=error_type,
                    )
                # transient: retry up to max_retries times
                if attempts <= self.max_retries:
                    self.sleep(self.backoff)
                    continue
                # retries exhausted
                self._record_breaker_failure()
                return Outcome(
                    ok=False,
                    action="skip",
                    attempts=attempts,
                    error_type=error_type,
                )
            else:
                return Outcome(
                    ok=True, value=value, action="ok", attempts=attempts
                )
