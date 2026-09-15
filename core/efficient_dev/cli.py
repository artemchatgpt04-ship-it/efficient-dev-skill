"""Small command-line interface for the agent-neutral core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from .change_tracker import ChangeResult, ChangeTracker
from .context_compressor import ContextCompressor, ContextResult
from .instruction_router import InstructionPlan, InstructionRouter
from .project_map import ProjectMap, ProjectMapBuilder
from .read_cache import CacheLookup, CacheStatus, ReadCache
from .smart_reader import ReadPlan, SmartReader
from .task_router import FileCandidate, RouteResult, TaskRouter
from .test_router import TestPlan, TestRouter


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
        ("instructions", "Select task-relevant instruction groups"),
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

    cache_parser = subparsers.add_parser("cache", help="Manage compact read knowledge")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", required=True)

    cache_status = cache_subparsers.add_parser("status", help="Check all cache entries")
    _add_cache_common_arguments(cache_status)

    cache_inspect = cache_subparsers.add_parser("inspect", help="Check one cached file")
    cache_inspect.add_argument("file", help="Project-relative file path")
    cache_inspect.add_argument(
        "--exact",
        action="store_true",
        help="Require direct source reading even when cached knowledge is valid",
    )
    _add_cache_common_arguments(cache_inspect)

    cache_record = cache_subparsers.add_parser("record", help="Store current file knowledge")
    cache_record.add_argument("file", help="Project-relative file path")
    cache_record.add_argument("--summary", required=True, help="Short structured description")
    cache_record.add_argument("--symbol", action="append", default=[])
    cache_record.add_argument("--relationship", action="append", default=[])
    cache_record.add_argument(
        "--exclude", action="append", default=[], help="Additional path or name glob"
    )
    cache_record.add_argument("--max-file-size", type=int, default=1_000_000)
    _add_cache_common_arguments(cache_record)

    cache_invalidate = cache_subparsers.add_parser(
        "invalidate", help="Explicitly invalidate one cache entry"
    )
    cache_invalidate.add_argument("file", help="Project-relative file path")
    _add_cache_common_arguments(cache_invalidate)

    changes_parser = subparsers.add_parser(
        "changes", help="Compare eligible files with the fingerprint baseline"
    )
    changes_parser.add_argument("--root", default=".", help="Repository root")
    changes_parser.add_argument(
        "--update",
        action="store_true",
        help="Store the current fingerprints as the new baseline after comparison",
    )
    changes_parser.add_argument(
        "--exclude", action="append", default=[], help="Additional path or name glob"
    )
    changes_parser.add_argument("--max-file-size", type=int, default=1_000_000)
    changes_parser.add_argument("--json", action="store_true", help="Print JSON")

    tests_parser = subparsers.add_parser(
        "tests", help="Recommend a validation scope for current changes"
    )
    tests_parser.add_argument("--root", default=".", help="Repository root")
    tests_parser.add_argument("--task", help="Optional current development task")
    tests_parser.add_argument("--map", dest="map_file", help="Existing project-map JSON")
    tests_parser.add_argument(
        "--exclude", action="append", default=[], help="Additional path or name glob"
    )
    tests_parser.add_argument("--max-file-size", type=int, default=1_000_000)
    tests_parser.add_argument(
        "--alias",
        action="append",
        default=[],
        metavar="TASK_TERM=PATH_TERM",
        help="Add a transparent task-to-path term alias",
    )
    tests_parser.add_argument("--json", action="store_true", help="Print JSON")

    context_parser = subparsers.add_parser(
        "context", help="Show or update bounded session facts"
    )
    context_subparsers = context_parser.add_subparsers(
        dest="context_command", required=True
    )
    context_show = context_subparsers.add_parser("show", help="Show current session facts")
    _add_context_common_arguments(context_show)

    context_update = context_subparsers.add_parser(
        "update", help="Replace supplied fields in current session facts"
    )
    context_update.add_argument("--task")
    context_update.add_argument("--scope", action="append")
    context_update.add_argument("--inspected", action="append")
    context_update.add_argument("--changed", action="append")
    context_update.add_argument("--finding", action="append")
    context_update.add_argument("--decision", action="append")
    context_update.add_argument("--test", action="append")
    context_update.add_argument("--issue", action="append")
    context_update.add_argument("--next-action")
    _add_context_common_arguments(context_update)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.command == "map":
            return _map_command(args)
        if args.command == "cache":
            return _cache_command(args)
        if args.command == "changes":
            return _changes_command(args)
        if args.command == "tests":
            return _tests_command(args)
        if args.command == "context":
            return _context_command(args)
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

    route = router.route(args.task)
    if args.command == "route":
        if args.json:
            print(json.dumps(route.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
        else:
            _print_route(route)
        return 0

    if args.command == "instructions":
        instruction_plan = InstructionRouter(project_map).route(
            args.task,
            task_route=route,
        )
        if args.json:
            print(
                json.dumps(
                    instruction_plan.to_dict(),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
        else:
            _print_instruction_plan(instruction_plan)
        return 0

    plan = SmartReader.plan_route(route)
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_plan(plan)
    return 0


def _cache_command(args: argparse.Namespace) -> int:
    builder = ProjectMapBuilder(
        extra_excludes=getattr(args, "exclude", []),
        max_file_size=getattr(args, "max_file_size", 1_000_000),
    )
    cache = ReadCache(args.root, map_builder=builder)

    if args.cache_command == "record":
        entry = cache.record(
            args.file,
            summary=args.summary,
            symbols=args.symbol,
            relationships=args.relationship,
        )
        if args.json:
            print(json.dumps(entry.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(f"Cached: {entry.path}")
            print(f"Validity: {entry.validity}")
            print(f"Fingerprint: {entry.fingerprint}")
        return 0

    if args.cache_command == "inspect":
        lookup = cache.lookup(args.file, require_exact=args.exact)
        if args.json:
            print(json.dumps(lookup.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
        else:
            _print_cache_lookup(lookup)
        return 0

    if args.cache_command == "invalidate":
        invalidated = cache.invalidate(args.file)
        result = {"path": args.file, "invalidated": invalidated}
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(f"Invalidated: {invalidated}")
            print(f"Path: {args.file}")
        return 0

    status = cache.status()
    if args.json:
        print(json.dumps(status.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_cache_status(status)
    return 0


def _changes_command(args: argparse.Namespace) -> int:
    builder = ProjectMapBuilder(
        extra_excludes=args.exclude,
        max_file_size=args.max_file_size,
    )
    cache = ReadCache(args.root, map_builder=builder)
    result = ChangeTracker(args.root, map_builder=builder).scan(
        read_cache=cache,
        update_baseline=args.update,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_changes(result)
    return 0


def _tests_command(args: argparse.Namespace) -> int:
    builder = ProjectMapBuilder(
        extra_excludes=args.exclude,
        max_file_size=args.max_file_size,
    )
    project_map = _load_or_build_map(args)
    changes = ChangeTracker(args.root, map_builder=builder).scan()
    task_route = None
    if args.task:
        task_route = TaskRouter(
            project_map,
            aliases=_parse_aliases(args.alias),
        ).route(args.task)
    plan = TestRouter(project_map).route(changes, task_route=task_route)
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_test_plan(plan)
    return 0


def _context_command(args: argparse.Namespace) -> int:
    compressor = ContextCompressor(args.root)
    if args.context_command == "show":
        result = compressor.show()
    else:
        argument_fields = {
            "task": "task",
            "scope": "scope",
            "inspected": "files_inspected",
            "changed": "files_changed",
            "finding": "key_findings",
            "decision": "decisions",
            "test": "tests_run",
            "issue": "open_issues",
            "next_action": "next_action",
        }
        facts = {
            field: getattr(args, argument)
            for argument, field in argument_fields.items()
            if getattr(args, argument) is not None
        }
        result = compressor.update(facts)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_context(result)
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


def _add_cache_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print JSON")


def _add_context_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print JSON")


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
    print(f"Cache check before read: {plan.cache_policy['check_before_read']}")
    print("Expand scope when:")
    for trigger in plan.expansion["triggers"]:
        print(f"  - {trigger}")
    _print_metrics(plan.metrics)


def _print_instruction_plan(plan: InstructionPlan) -> None:
    print(f"Task: {plan.task}")
    print(f"Route confidence: {plan.route_confidence}")
    print(f"Safe expansion: {plan.safe_expansion}")
    print("Selected instruction groups:")
    for group in plan.selected:
        print(f"  - {group.name} ({group.reference}): {'; '.join(group.reasons)}")
    _print_paths("Deferred instruction groups", (item["name"] for item in plan.deferred))
    _print_metrics(plan.metrics)


def _print_cache_lookup(lookup: CacheLookup) -> None:
    print(f"Path: {lookup.path}")
    print(f"Status: {lookup.status}")
    print(f"Requires read: {lookup.requires_read}")
    print(f"Reason: {lookup.reason}")
    if lookup.cached_knowledge:
        print(f"Summary: {lookup.cached_knowledge['summary']}")
        _print_paths("Symbols", lookup.cached_knowledge["symbols"])
        _print_paths("Relationships", lookup.cached_knowledge["relationships"])
    _print_metrics(lookup.metrics)


def _print_cache_status(status: CacheStatus) -> None:
    print("Cache entries:")
    if not status.entries:
        print("  (none)")
    for entry in status.entries:
        print(f"  - {entry['path']}: {entry['validity']}")
    _print_paths("Removed deleted entries", status.removed_deleted)
    _print_metrics(status.metrics)


def _print_changes(result: ChangeResult) -> None:
    print(f"Baseline exists: {result.baseline_exists}")
    print(f"Baseline updated: {result.baseline_updated}")
    _print_paths("Added", result.added)
    _print_paths("Modified", result.modified)
    _print_paths("Deleted", result.deleted)
    _print_paths("Invalidated cache entries", result.invalidated_cache_entries)
    _print_paths("Project Map refresh directories", result.project_map_refresh_directories)
    print(f"Project Map potentially stale: {result.project_map_stale}")
    _print_metrics(result.metrics)


def _print_test_plan(plan: TestPlan) -> None:
    _print_paths("Changed files", plan.changed_files)
    print(f"Full suite recommended: {plan.full_suite_recommended}")
    print("Selected tests:")
    if not plan.selected_tests:
        print("  (none)")
    for test in plan.selected_tests:
        print(f"  - {test.path}: {'; '.join(test.reasons)}")
    _print_paths("Related test areas", plan.area_test_directories)
    _print_paths("Plan reasons", plan.reasons)
    _print_paths("Escalate to full suite when", plan.escalation_conditions)
    _print_metrics(plan.metrics)


def _print_context(result: ContextResult) -> None:
    state = result.state
    print(f"Task: {state.task or '(none)'}")
    _print_paths("Scope", state.scope)
    _print_paths("Files inspected", state.files_inspected)
    _print_paths("Files changed", state.files_changed)
    _print_paths("Key findings", state.key_findings)
    _print_paths("Decisions", state.decisions)
    _print_paths("Tests run", state.tests_run)
    _print_paths("Open issues", state.open_issues)
    print(f"Next action: {state.next_action or '(none)'}")
    _print_metrics(result.metrics)


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
        "cache_entries",
        "cache_hits",
        "cache_misses",
        "stale_entries",
        "changed_files",
        "unchanged_files",
        "available_instruction_groups",
        "selected_instruction_groups",
        "candidate_tests",
        "selected_tests",
        "full_suite_recommended",
        "context_items",
        "context_size",
        "deduplicated_items",
    ):
        if key in metrics:
            print(f"  {key}: {metrics[key]}")


if __name__ == "__main__":
    raise SystemExit(main())
