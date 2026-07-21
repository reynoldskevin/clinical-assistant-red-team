"""MVP run entrypoint (ticket 009).

Drives the real Red Team -> Target Adapter -> Judge loop against a target,
persisting attempts, verdicts, ordered events, findings and metered cost to the
store, and printing a per-category pass/fail summary.

A category *passes* iff no attempt was a confirmed exploit (verdict "success").
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from forge.access import TargetRegistry
from forge.config import Config
from forge.evals import load_cases
from forge.judge import JudgeAgent
from forge.llm import ClaudeClient, LLMResponse
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

    def __init__(self, store, red_team, judge, *, pid: int, cost_meter: CostMeter | None = None) -> None:
        self._store = store
        self._red_team = red_team
        self._judge = judge
        self._pid = pid
        self._cost_meter = cost_meter

    def run_category(self, category: str, seeds: list[str] | None = None) -> CategorySummary:
        summary = CategorySummary(category=category)
        seed_list = list(seeds) if seeds else [None]

        for seed in seed_list:
            if self._cost_meter is not None:
                snap_usd = self._cost_meter.total_usd
                snap_in = self._cost_meter.total_in
                snap_out = self._cost_meter.total_out

            directive = AttackDirective(category=category, seed=seed, max_attempts=1)
            attempts = self._red_team.run(directive, self._pid)

            for attempt in attempts:
                attempt_id = self._store.insert_attempt(attempt.model_dump())
                self._store.append_event(
                    {"kind": "attack", "attempt_id": attempt_id, "category": category}
                )
                verdict = self._judge.evaluate(attempt)
                self._store.append_event(
                    {
                        "kind": "verdict",
                        "attempt_id": attempt_id,
                        "category": category,
                        "verdict": verdict.verdict,
                        "confidence": verdict.confidence,
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
                        }
                    )

            if self._cost_meter is not None:
                self._store.insert_cost(
                    {
                        "category": category,
                        "input_tokens": self._cost_meter.total_in - snap_in,
                        "output_tokens": self._cost_meter.total_out - snap_out,
                        "usd": self._cost_meter.total_usd - snap_usd,
                    }
                )

        return summary

    def run_suite(self, seeds_by_category: dict[str, list[str]]) -> RunSummary:
        self._store.append_event({"kind": "run_start", "pid": self._pid})
        categories: dict[str, CategorySummary] = {}
        for category, seeds in seeds_by_category.items():
            categories[category] = self.run_category(category, seeds)
        self._store.append_event({"kind": "run_end"})
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
        seed = case.prompt
        if not seed and case.input_sequence:
            seed = "\n".join(s for s in case.input_sequence if s)
        if isinstance(seed, str) and seed:
            seeds.append(seed)
    return seeds


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

    runner = Runner(store, red_team, judge, pid=args.pid, cost_meter=meter)

    cases = load_cases()
    if args.suite:
        categories = sorted({c.category for c in cases})
        seeds_by_category = {
            cat: seeds_for_category(cases, cat) for cat in categories
        }
    else:
        seeds_by_category = {args.category: seeds_for_category(cases, args.category)}

    summary = runner.run_suite(seeds_by_category)
    print(format_summary(summary))
    return 0 if summary.passed else 1
