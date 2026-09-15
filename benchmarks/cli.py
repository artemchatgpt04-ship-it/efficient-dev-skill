"""Command-line interface for controlled MVP efficiency experiments."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from .harness import BenchmarkHarness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="efficient-dev-benchmark",
        description=(
            "Compare a broad baseline with Efficient Development using deterministic "
            "proxy metrics; no real token usage is measured."
        ),
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--all",
        action="store_true",
        help="Run the complete scenario suite (default)",
    )
    selection.add_argument(
        "--scenario",
        help="Run one scenario id or every scenario of a kind, such as local",
    )
    parser.add_argument("--list", action="store_true", help="List scenarios and exit")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON")
    return parser


def _scenario_selection(harness: BenchmarkHarness, selector: str | None) -> tuple[str, ...] | None:
    if selector is None:
        return None
    if selector in harness.scenario_ids:
        return (selector,)
    matches = tuple(
        scenario.id for scenario in harness.scenarios if scenario.kind == selector
    )
    if matches:
        return matches
    raise ValueError(f"Unknown scenario id or kind: {selector!r}")


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _print_human(result: dict[str, Any]) -> None:
    print("Efficient Development MVP benchmark")
    print("All reductions are deterministic proxy metrics; real token usage was not measured.")
    print()
    print("Scenario | Fixture | Baseline files | Efficient files | Reduction | Coverage")
    print("--- | --- | ---: | ---: | ---: | ---:")
    for scenario in result["scenarios"]:
        baseline = scenario["baseline"]["reading"]["files_read_or_recommended"]
        efficient = scenario["efficient"]["reading"]["files_read_or_recommended"]
        reduction = _percent(scenario["comparison"]["reading_reduction_ratio"])
        coverage = _percent(scenario["quality"]["required_context_coverage"])
        print(
            f"{scenario['id']} | {scenario['fixture']} | {baseline} | "
            f"{efficient} | {reduction} | {coverage}"
        )
    summary = result["summary"]
    print()
    print(f"Quality failures: {summary['quality_failures']}")
    print(f"Reading reduction: {_percent(summary['reading_reduction_ratio'])}")
    print(
        "Instruction-byte reduction: "
        + _percent(summary["instruction_byte_reduction_ratio"])
    )
    print(f"Test-selection reduction: {_percent(summary['test_selection_reduction_ratio'])}")
    print(f"Context-byte reduction: {_percent(summary['context_reduction_ratio'])}")
    print(
        "Cache: "
        f"hits={summary['cache_hits']}, misses={summary['cache_misses']}, "
        f"stale={summary['stale_entries']}, "
        f"potential avoided repeat reads={summary['avoided_repeat_reads']}"
    )
    if summary["mvp_success"] is not None:
        print(f"MVP criteria passed: {summary['mvp_success']}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        harness = BenchmarkHarness()
        if args.list:
            for scenario in harness.scenarios:
                print(f"{scenario.id}: {scenario.kind} ({scenario.fixture})")
            return 0
        selected = _scenario_selection(harness, args.scenario)
        result = harness.run(selected)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_human(result)
    if result["summary"]["quality_failures"]:
        return 1
    if result["summary"]["mvp_success"] is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
