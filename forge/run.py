"""MVP run entrypoint (ticket 009).

Drives the real Red Team -> Target Adapter -> Judge loop against a target,
persisting attempts, verdicts, ordered events, findings and metered cost to the
store, and printing a per-category pass/fail summary.

A category *passes* iff no attempt was a confirmed exploit (verdict "success").
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from forge.access import TargetRegistry
from forge.config import Config, resolve_reports_dir
from forge.evals import load_cases
from forge.judge import JudgeAgent
from forge.llm import ClaudeClient, LLMResponse
from forge.observability import Observability
from forge.red_team import RedTeamAgent
from forge.schemas import AttackDirective
from forge.store import Store
from forge.target import TargetAdapter


# --------------------------------------------------------------------------- #
# Cost metering
# --------------------------------------------------------------------------- #
# Default per-model pricing (USD per 1M tokens: input, output). List-price
# estimates used for the live cost view; ticket 021 refines them against
# recorded usage. Unknown models fall back to zero.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


class CostMeter:
    """Accumulates USD cost from LLM token usage.

    ``prices`` maps a model id to ``(input_usd_per_1M, output_usd_per_1M)``.
    Unknown models are priced at zero.
    """

    def __init__(self, prices: dict[str, tuple[float, float]] | None = None) -> None:
        self._prices = dict(prices or {})
        self.total_usd = 0.0
        self.total_in = 0
        self.total_out = 0

    def record(self, model: str, in_tokens: int, out_tokens: int) -> float:
        in_price, out_price = self._prices.get(model, (0.0, 0.0))
        usd = in_tokens / 1e6 * in_price + out_tokens / 1e6 * out_price
        self.total_usd += usd
        self.total_in += in_tokens
        self.total_out += out_tokens
        return usd


class MeteredLLM:
    """Transparent LLM wrapper that records token usage into a ``CostMeter``.

    Implements the ``LLMClient`` protocol so it can be dropped in front of any
    agent; it delegates to ``inner_llm`` and returns the response unchanged.
    """

    def __init__(self, inner_llm: Any, meter: CostMeter) -> None:
        self._inner = inner_llm
        self._meter = meter

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        resp = self._inner.complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            system=system,
            temperature=temperature,
        )
        self._meter.record(resp.model, resp.input_tokens, resp.output_tokens)
        return resp


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #
@dataclass
class CategorySummary:
    category: str
    attempts: int = 0
    exploits: int = 0
    defended: int = 0
    partial: int = 0

    def record(self, verdict_str: str) -> None:
        self.attempts += 1
        if verdict_str == "success":
            self.exploits += 1
        elif verdict_str == "fail":
            self.defended += 1
        elif verdict_str == "partial":
            self.partial += 1

    @property
    def passed(self) -> bool:
        return self.exploits == 0


class SuiteAborted(Exception):
    """Raised to stop a suite run cleanly after the failure budget is exhausted.

    Carries the accumulated failure count so callers can report it.
    """

    def __init__(self, failures: int) -> None:
        super().__init__(f"suite aborted after {failures} failures")
        self.failures = failures


@dataclass
class RunSummary:
    categories: dict[str, CategorySummary] = field(default_factory=dict)
    total_cost_usd: float = 0.0

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.categories.values())


# --------------------------------------------------------------------------- #
# Severity mapping
# --------------------------------------------------------------------------- #
def _severity_from_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
class Runner:
    """Orchestrates Red Team -> Judge over categories, persisting everything."""

    def __init__(
        self,
        store,
        red_team,
        judge,
        *,
        pid: int,
        cost_meter: CostMeter | None = None,
        max_failures: int | None = None,
        regression_harness=None,
        orchestrator=None,
        documentation=None,
    ) -> None:
        self._store = store
        self._red_team = red_team
        self._judge = judge
        self._pid = pid
        self._cost_meter = cost_meter
        self._max_failures = max_failures
        self._regression_harness = regression_harness
        self._orchestrator = orchestrator
        self._documentation = documentation
        self._failures = 0
        # per-run identity: stamped onto every record a run produces so the
        # dashboard can scope its stats to a single run (and version the trend).
        self._run_id: int | None = None
        self._version: str | None = None

    def _execute_directive(self, directive: AttackDirective) -> CategorySummary:
        """Run ONE directive (Red Team -> Judge over its attempts), persisting
        everything and stamping the per-run identity. Isolates a failed
        generation and honours the failure-budget circuit breaker exactly as the
        category/suite paths do."""
        category = directive.category
        summary = CategorySummary(category=category)
        try:
            if self._cost_meter is not None:
                snap_usd = self._cost_meter.total_usd
                snap_in = self._cost_meter.total_in
                snap_out = self._cost_meter.total_out

            attempts = self._red_team.run(directive, self._pid)

            for attempt in attempts:
                attempt_id = self._store.insert_attempt(attempt.model_dump())
                self._store.append_event(
                    {
                        "kind": "attack",
                        "attempt_id": attempt_id,
                        "category": category,
                        "run_id": self._run_id,
                        "target_version": self._version,
                    }
                )
                verdict = self._judge.evaluate(attempt)
                self._store.append_event(
                    {
                        "kind": "verdict",
                        "attempt_id": attempt_id,
                        "category": category,
                        "verdict": verdict.verdict,
                        "confidence": verdict.confidence,
                        "owasp_web": verdict.owasp_web,
                        "owasp_llm": verdict.owasp_llm,
                        "run_id": self._run_id,
                        "target_version": self._version,
                    }
                )
                summary.record(verdict.verdict)

                if verdict.verdict == "success":
                    self._store.insert_finding(
                        {
                            "severity": _severity_from_confidence(verdict.confidence),
                            "attack_category": category,
                            "status": "open",
                            "attempt_id": attempt_id,
                            "rationale": verdict.rationale,
                            "owasp_web": verdict.owasp_web,
                            "owasp_llm": verdict.owasp_llm,
                            "run_id": self._run_id,
                            "target_version": self._version,
                        }
                    )

            if self._cost_meter is not None:
                self._store.insert_cost(
                    {
                        "category": category,
                        "input_tokens": self._cost_meter.total_in - snap_in,
                        "output_tokens": self._cost_meter.total_out - snap_out,
                        "usd": self._cost_meter.total_usd - snap_usd,
                        "run_id": self._run_id,
                        "version": self._version,
                    }
                )
        except SuiteAborted:
            raise
        except Exception as exc:  # noqa: BLE001 - isolate a failed generation
            self._failures += 1
            self._store.append_event(
                {
                    "kind": "attempt_error",
                    "category": category,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            if self._max_failures is not None and self._failures >= self._max_failures:
                self._store.append_event(
                    {
                        "kind": "circuit_breaker",
                        "reason": "max_failures_exceeded",
                        "failures": self._failures,
                    }
                )
                raise SuiteAborted(self._failures) from exc

        return summary

    def run_category(self, category: str, seeds: list[str] | None = None) -> CategorySummary:
        summary = CategorySummary(category=category)
        seed_list = list(seeds) if seeds else [None]

        for seed in seed_list:
            directive = AttackDirective(category=category, seed=seed, max_attempts=1)
            part = self._execute_directive(directive)
            summary.attempts += part.attempts
            summary.exploits += part.exploits
            summary.defended += part.defended
            summary.partial += part.partial

        return summary

    def run_suite(self, seeds_by_category: dict[str, list[str]]) -> RunSummary:
        # Mock version per run. All pre-versioning data is the v1.0 baseline, so
        # the first NEW versioned run is v1.1 and the minor increments each run.
        prior = sum(
            1
            for e in self._store.get_events()
            if e.get("kind") == "run_start" and e.get("version") is not None
        )
        self._version = f"v1.{prior + 1}"
        self._run_id = self._store.append_event(
            {"kind": "run_start", "pid": self._pid, "ts": time.time(), "version": self._version}
        )
        self._failures = 0
        categories: dict[str, CategorySummary] = {}
        try:
            for category, seeds in seeds_by_category.items():
                categories[category] = self.run_category(category, seeds)
            # Regression replay runs AFTER the category loop but still inside the
            # try (before the finally's run_end) so its regression_result events
            # land within this run's event-id window. A SuiteAborted from the
            # loop above skips this naturally. Any harness failure is isolated so
            # it never aborts the run.
            if self._regression_harness is not None:
                try:
                    self._regression_harness.validate()
                except Exception as exc:  # noqa: BLE001 - isolate a harness failure
                    self._store.append_event(
                        {
                            "kind": "attempt_error",
                            "category": "regression",
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                    )
        except SuiteAborted:
            pass
        finally:
            self._store.append_event(
                {"kind": "run_end", "ts": time.time(), "version": self._version, "run_id": self._run_id}
            )
        total = self._cost_meter.total_usd if self._cost_meter is not None else 0.0
        return RunSummary(categories=categories, total_cost_usd=total)

    def run_autonomous(self, max_directives: int = 500) -> RunSummary:
        """The deployed one-loop run: the Orchestrator selects directives until
        it halts, then regression replay and the Documentation pass run — all
        within the same versioned run window as ``run_suite``."""
        prior = sum(
            1
            for e in self._store.get_events()
            if e.get("kind") == "run_start" and e.get("version") is not None
        )
        self._version = f"v1.{prior + 1}"
        self._run_id = self._store.append_event(
            {"kind": "run_start", "pid": self._pid, "ts": time.time(), "version": self._version}
        )
        self._failures = 0
        # Scope the Orchestrator to THIS run so its coverage/budget/findings
        # reflect only the current run (an active run -> end_id=None -> open
        # window), not cumulative history. Without this a run after history
        # exists sees every category covered and halts immediately (empty-run
        # bug).
        if self._orchestrator is not None:
            from forge.scoping import RunScopedStore

            self._orchestrator.observability = Observability(
                RunScopedStore(self._store, start_id=self._run_id, end_id=None)
            )
        categories: dict[str, CategorySummary] = {}
        try:
            # Orchestrator drives the attack phase until it returns None. The
            # safety cap guards against any non-halting strategist.
            for _ in range(max_directives):
                directive = self._orchestrator.next_directive()
                if directive is None:
                    break
                part = self._execute_directive(directive)
                existing = categories.get(part.category)
                if existing is None:
                    categories[part.category] = part
                else:
                    existing.attempts += part.attempts
                    existing.exploits += part.exploits
                    existing.defended += part.defended
                    existing.partial += part.partial
            else:
                self._store.append_event(
                    {"kind": "circuit_breaker", "reason": "max_directives_exceeded"}
                )

            # Regression replay runs BEFORE the documentation pass (ordering is
            # asserted) and still inside the try so its events land within this
            # run's id window. Any harness failure is isolated.
            if self._regression_harness is not None:
                try:
                    self._regression_harness.validate()
                except Exception as exc:  # noqa: BLE001 - isolate a harness failure
                    self._store.append_event(
                        {
                            "kind": "attempt_error",
                            "category": "regression",
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                    )

            # Documentation pass: draft reports + linked regression cases for
            # confirmed exploits. Isolated so a failure never aborts the run.
            if self._documentation is not None and self._regression_harness is not None:
                from forge.vuln_reports import generate_reports

                try:
                    generate_reports(
                        self._store,
                        documentation=self._documentation,
                        harness=self._regression_harness,
                    )
                except Exception as exc:  # noqa: BLE001 - isolate a documentation failure
                    self._store.append_event(
                        {
                            "kind": "attempt_error",
                            "category": "documentation",
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                    )
        except SuiteAborted:
            pass
        finally:
            self._store.append_event(
                {"kind": "run_end", "ts": time.time(), "version": self._version, "run_id": self._run_id}
            )
        total = self._cost_meter.total_usd if self._cost_meter is not None else 0.0
        return RunSummary(categories=categories, total_cost_usd=total)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def format_summary(summary: RunSummary) -> str:
    lines = ["Run summary", "==========="]
    for name, cat in summary.categories.items():
        status = "PASS" if cat.passed else "FAIL"
        lines.append(
            f"{name}: {status} "
            f"(attempts={cat.attempts} exploits={cat.exploits} "
            f"defended={cat.defended} partial={cat.partial})"
        )
    overall = "PASS" if summary.passed else "FAIL"
    lines.append(f"Overall: {overall}")
    lines.append(f"Total cost: ${summary.total_cost_usd:.6f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Seeds from eval dataset
# --------------------------------------------------------------------------- #
def seeds_for_category(cases, category: str) -> list[str]:
    seeds: list[str] = []
    for case in cases:
        if case.category != category:
            continue
        seed = getattr(case, "prompt", None)
        input_sequence = getattr(case, "input_sequence", None)
        if not seed and input_sequence:
            seed = "\n".join(s for s in input_sequence if s)
        if isinstance(seed, str) and seed:
            seeds.append(seed)
    return seeds


# --------------------------------------------------------------------------- #
# Autonomous runner factory (ticket 044)
# --------------------------------------------------------------------------- #
def build_autonomous_runner(
    store,
    *,
    red_team,
    judge,
    adapter,
    cases,
    cost_meter,
    pid: int,
) -> "Runner":
    """Wire the full four-agent deployed loop: Orchestrator + Red Team + Judge +
    Regression + Documentation, all sharing one store."""
    import os

    from forge.documentation import DocumentationAgent
    from forge.observability import Observability
    from forge.orchestrator import Orchestrator
    from forge.regression import RegressionHarness

    obs = Observability(store, cases=cases)
    categories = sorted({c.category for c in cases})
    seeds_by_category = {cat: seeds_for_category(cases, cat) for cat in categories}
    orchestrator = Orchestrator(
        obs, categories=categories, coverage_target=10,
        seeds_by_category=seeds_by_category,
    )
    documentation = DocumentationAgent(
        store, reports_dir=resolve_reports_dir()
    )
    harness = RegressionHarness(store, adapter, judge, pid=pid)
    return Runner(
        store,
        red_team,
        judge,
        pid=pid,
        cost_meter=cost_meter,
        regression_harness=harness,
        orchestrator=orchestrator,
        documentation=documentation,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="forge")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run a category or the full suite")
    run_p.add_argument("--category", type=str, default=None)
    run_p.add_argument("--suite", action="store_true", default=False)
    run_p.add_argument("--pid", type=int, default=1)

    serve_p = sub.add_parser("serve", help="serve the live demo dashboard")
    serve_p.add_argument("--host", type=str, default=None)
    serve_p.add_argument("--port", type=int, default=None)
    return parser.parse_args(argv)


def dev_mint_token_provider(
    mint_url: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 30,
) -> Callable[[int], str]:
    """Return a ``provider(pid) -> jwt`` that POSTs ``{"pid": pid}`` to ``mint_url``."""

    def provider(pid: int) -> str:
        data = json.dumps({"pid": pid}).encode()
        req = urllib.request.Request(
            mint_url,
            method="POST",
            headers={"Content-Type": "application/json"},
            data=data,
        )
        with opener(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        return body["token"]

    return provider


def main(argv=None) -> int:
    import os

    args = parse_args(argv)

    if args.command == "serve":
        from forge.dashboard import resolve_bind, serve

        host, port = resolve_bind(args, os.environ)
        store = Store(os.environ.get("FORGE_DB_PATH", "forge.db"))
        cases = load_cases()
        serve(store, host=host, port=port, cases=cases)
        return 0

    if not args.suite and not args.category:
        print("error: specify --category <name> or --suite")
        return 2

    config = Config.from_env()

    meter = CostMeter(PRICES)
    base_llm = ClaudeClient(api_key=config.anthropic_api_key)
    metered = MeteredLLM(base_llm, meter)

    store = Store(config.db_path)
    registry = TargetRegistry({"copilot": {"base_url": config.target_base_url}})
    mint_url = os.environ.get("FORGE_TOKEN_MINT_URL", "")
    adapter = TargetAdapter(
        registry,
        "copilot",
        token_provider=dev_mint_token_provider(mint_url),
        store=store,
    )

    red_team = RedTeamAgent(metered, adapter, model=config.models["red_team"])
    judge = JudgeAgent(metered, model=config.models["judge"])

    cases = load_cases()
    if not args.suite:
        cases = [c for c in cases if c.category == args.category]

    runner = build_autonomous_runner(
        store,
        red_team=red_team,
        judge=judge,
        adapter=adapter,
        cases=cases,
        cost_meter=meter,
        pid=args.pid,
    )

    summary = runner.run_autonomous()
    print(format_summary(summary))
    return 0 if summary.passed else 1
