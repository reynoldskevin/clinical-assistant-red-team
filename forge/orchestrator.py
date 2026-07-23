"""Orchestrator agent — prioritize · budget · trigger (ticket 014).

The strategist of the red-team platform: it reads the Observability read-model
(never the SQL directly) and decides the next ``AttackDirective``, enforcing the
per-run budget, redirecting/halting on low signal, applying coverage-sufficiency,
and emitting ``RegressionTrigger``s on target-version change or elapsed windows.

Stdlib + existing forge schemas only. Deterministic tie-breaks (alphabetical) so
the same read-model always yields the same decision.
"""

from __future__ import annotations

from forge.schemas import AttackDirective, RegressionTrigger

_HIGH_SEVERITIES = {"critical", "high"}


class Orchestrator:
    """Reads Observability and decides the next directive / regression trigger."""

    def __init__(
        self,
        observability,
        *,
        categories,
        target_id: str = "copilot",
        run_budget_usd: float = 5.0,
        coverage_target: int = 10,
        pass_rate_target: float = 1.0,
        directive_max_attempts: int = 3,
        directive_max_cost_usd: float = 1.0,
        min_spend_before_halt: float = 0.5,
        min_signal_per_usd: float = 1.0,
        seeds_by_category=None,
    ):
        self.observability = observability
        self.categories = list(categories)
        self._seeds = dict(seeds_by_category or {})
        self._seed_cursor: dict[str, int] = {}
        self.target_id = target_id
        self.run_budget_usd = run_budget_usd
        self.coverage_target = coverage_target
        self.pass_rate_target = pass_rate_target
        self.directive_max_attempts = directive_max_attempts
        self.directive_max_cost_usd = directive_max_cost_usd
        self.min_spend_before_halt = min_spend_before_halt
        self.min_signal_per_usd = min_signal_per_usd

    # ------------------------------------------------------------------ #
    # read-model helpers
    # ------------------------------------------------------------------ #
    def _category_stats(self, category: str) -> tuple[int, float]:
        """(attempts, pass_rate) for a category; absent → (0, 0.0)."""
        bucket = self.observability.pass_fail()["by_category"].get(category)
        if bucket is None:
            return 0, 0.0
        return bucket["attempts"], bucket["pass_rate"]

    def _total_usd(self) -> float:
        return self.observability.cost()["total_usd"]

    def _exploits(self) -> int:
        return self.observability.pass_fail()["overall"]["exploits"]

    # ------------------------------------------------------------------ #
    # coverage / signal
    # ------------------------------------------------------------------ #
    def is_covered(self, category: str) -> bool:
        attempts, pass_rate = self._category_stats(category)
        return attempts >= self.coverage_target and pass_rate >= self.pass_rate_target

    def signal_per_usd(self) -> float:
        total = self._total_usd()
        return (self._exploits() / total) if total > 0 else 0.0

    def should_halt_for_low_signal(self) -> bool:
        return (
            self._total_usd() >= self.min_spend_before_halt
            and self.signal_per_usd() < self.min_signal_per_usd
        )

    def _open_high_severity_categories(self) -> list[str]:
        cats = {
            f.get("attack_category")
            for f in self.observability.store.list_findings(status="open")
            if f.get("severity") in _HIGH_SEVERITIES
        }
        return sorted(c for c in cats if c is not None)

    # ------------------------------------------------------------------ #
    # decision
    # ------------------------------------------------------------------ #
    def _next_seed(self, category: str) -> str | None:
        seeds = self._seeds.get(category)
        if not seeds:
            return None
        i = self._seed_cursor.get(category, 0)
        self._seed_cursor[category] = i + 1
        return seeds[i % len(seeds)]

    def _floor_for(self, category: str) -> int:
        return max(self.coverage_target, len(self._seeds.get(category, [])))

    def _directive(self, category: str) -> AttackDirective:
        return AttackDirective(
            category=category,
            max_attempts=self.directive_max_attempts,
            max_cost_usd=self.directive_max_cost_usd,
            seed=self._next_seed(category),
        )

    def next_directive(self) -> AttackDirective | None:
        # 1. per-run budget hard stop
        if self._total_usd() >= self.run_budget_usd:
            return None

        # 2. COVERAGE FLOOR (floor-first): every category must reach
        # ``coverage_target`` ATTEMPTS before an open finding can monopolize the
        # loop. Probe the least-covered below-floor category (alpha tie-break).
        below_floor = [
            c for c in self.categories if self._category_stats(c)[0] < self._floor_for(c)
        ]
        if below_floor:
            chosen = min(below_floor, key=lambda c: (self._category_stats(c)[0], c))
            return self._directive(chosen)

        # 3. open high/critical-severity finding → re-probe (even if covered)
        high_sev = self._open_high_severity_categories()
        if high_sev:
            return self._directive(high_sev[0])

        # 4. residual coverage-sufficiency gap → least-covered (alpha tie-break)
        uncovered = [c for c in self.categories if not self.is_covered(c)]
        if uncovered:
            chosen = min(uncovered, key=lambda c: (self._category_stats(c)[0], c))
            return self._directive(chosen)

        # 5. all covered, nothing open → halt cleanly
        return None

    # ------------------------------------------------------------------ #
    # regression triggers
    # ------------------------------------------------------------------ #
    def regression_trigger(
        self,
        *,
        target_version,
        previous_version,
        seconds_since_last_run=None,
        window_seconds=None,
    ) -> RegressionTrigger | None:
        if previous_version is not None and target_version != previous_version:
            return RegressionTrigger(
                reason="target_version_change",
                target_id=self.target_id,
                target_version=target_version,
            )
        if (
            window_seconds is not None
            and seconds_since_last_run is not None
            and seconds_since_last_run >= window_seconds
        ):
            return RegressionTrigger(
                reason="time_window",
                target_id=self.target_id,
                target_version=target_version,
            )
        return None
