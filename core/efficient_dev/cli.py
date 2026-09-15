"""Small command-line interface for the Stage 2 core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from .project_map import ProjectMap, ProjectMapBuilder
from .smart_reader import ReadPlan, SmartReader
from .task_router import FileCandidate, RouteResult, TaskRouter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="efficient-dev",
        description="Build compact project maps and recommend an initial reading scope.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    map_parser = subparsers.add_parser("map", help="Build a compact project map")
    map_parser.add_argument("root", nargs="?", default=".", help="Repository root")
    map_parser.add_argument(
        "--output",
        help="Output JSON path (default: ROOT/.efficient-dev/project-map.json)",
    )
    map_parser.add_argument(
        "--exclude", action="append", default=[], help="Additional path or name glob"
    )
    map_parser.add_argument("--max-file-size", type=int, default=1_000_000)
    map_parser.add_argument("--json", action="store_true", help="Print JSON to stdout")

    for command, help_text in (
        ("route", "Rank an initial investigation scope"),
        ("plan", "Create a Smart Reader plan"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("task", help="Local development task")
        command_parser.add_argument("--root", default=".", help="Repository root")
        command_parser.add_argument("--map", dest="map_file", help="Existing project-map JSON")
        command_parser.add_argument(
            "--exclude", action="append", default=[], help="Additional path or name glob"
        )
        command_parser.add_argument("--max-file-size", type=int, default=1_000_000)
        command_parser.add_argument(
            "--alias",
            action="append",
            default=[],
            metavar="TASK_TERM=PATH_TERM",
            help="Add a transparent task-to-path term alias",
        )
        command_parser.add_argument("--json", action="store_true", help="Print JSON")

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.command == "map":
            return _map_command(args)
        return _route_or_plan_command(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _map_command(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    project_map = ProjectMapBuilder(
        extra_excludes=args.exclude,
        max_file_size=args.max_file_size,
    ).build(root)
    output = Path(args.output) if args.output else root / ".efficient-dev" / "project-map.json"
    saved_path = project_map.save(output)

    if args.json:
        print(project_map.to_json(), end="")
    else:
        metrics = project_map.metrics
        print(f"Project map: {project_map.project_name}")
        print(f"Written: {saved_path.resolve()}")
        print(
            "Files: "
            f"{metrics['mapped_files']} mapped / {metrics['total_files']} considered; "
            f"{metrics['pruned_directories']} directories pruned"
        )
        _print_paths("Probable entry points", project_map.entry_points)
        _print_paths("Tests", project_map.tests)
        _print_paths("Configuration", project_map.configuration)
    return 0


def _route_or_plan_command(args: argparse.Namespace) -> int:
    project_map = _load_or_build_map(args)
    aliases = _parse_aliases(args.alias)
    router = TaskRouter(project_map, aliases=aliases)

    if args.command == "route":
        route = router.route(args.task)
        if args.json:
            print(json.dumps(route.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
        else:
            _print_route(route)
        return 0

    plan = SmartReader(router).plan(args.task)
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_plan(plan)
    return 0


def _load_or_build_map(args: argparse.Namespace) -> ProjectMap:
    if args.map_file:
        return ProjectMap.load(args.map_file)
    return ProjectMapBuilder(
        extra_excludes=args.exclude,
        max_file_size=args.max_file_size,
    ).build(args.root)


def _parse_aliases(values: list[str]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Alias must use TASK_TERM=PATH_TERM: {value!r}")
        task_term, path_term = (part.strip().lower() for part in value.split("=", 1))
        if not task_term or not path_term:
            raise ValueError(f"Alias terms must not be empty: {value!r}")
        aliases.setdefault(task_term, []).append(path_term)
    return aliases


def _print_route(route: RouteResult) -> None:
    print(f"Task: {route.task}")
    print(f"Confidence: {route.confidence} ({route.scope_mode})")
    _print_candidates("High probability", route.high_probability)
    _print_candidates("Medium probability", route.medium_probability)
    _print_candidates("Low-confidence orientation", route.fallback_files)
    _print_paths("Search roots", route.search_roots)
    _print_paths("Deferred for now", route.deferred_directories)
    if route.requires_broader_search:
        print("Expansion: required; search the mapped repository before choosing files to read.")
    _print_metrics(route.metrics)


def _print_plan(plan: ReadPlan) -> None:
    print(f"Task: {plan.task}")
    print(f"Confidence: {plan.confidence} ({plan.scope_mode})")
    print("Search first:")
    search_step = next(step for step in plan.sequence if step["action"] == "search")
    print(f"  roots: {', '.join(search_step['roots'])}")
    print(f"  terms: {', '.join(search_step['terms']) or '(none)'}")
    _print_read_targets("Read first", plan.read_first)
    _print_read_targets("Read next if needed", plan.read_next)
    _print_read_targets("Orientation only after broad search", plan.orientation_after_search)
    _print_paths("Defer for now", plan.defer)
    print("Expand scope when:")
    for trigger in plan.expansion["triggers"]:
        print(f"  - {trigger}")
    _print_metrics(plan.metrics)


def _print_candidates(title: str, candidates: tuple[FileCandidate, ...]) -> None:
    print(f"{title}:")
    if not candidates:
        print("  (none)")
        return
    for candidate in candidates:
        print(f"  - {candidate.path} [score {candidate.score}]: {'; '.join(candidate.reasons)}")


def _print_read_targets(title: str, targets: tuple[object, ...]) -> None:
    print(f"{title}:")
    if not targets:
        print("  (none)")
        return
    for target in targets:
        print(f"  - {target.path} ({target.mode}): {target.reason}")


def _print_paths(title: str, paths: Iterable[str]) -> None:
    paths = tuple(paths)
    print(f"{title}:")
    if not paths:
        print("  (none)")
        return
    for path in paths:
        print(f"  - {path}")


def _print_metrics(metrics: dict[str, int | float]) -> None:
    print("Metrics:")
    for key in (
        "total_files",
        "mapped_files",
        "candidate_files",
        "candidate_directories",
        "scope_ratio",
    ):
        if key in metrics:
            print(f"  {key}: {metrics[key]}")


if __name__ == "__main__":
    raise SystemExit(main())
