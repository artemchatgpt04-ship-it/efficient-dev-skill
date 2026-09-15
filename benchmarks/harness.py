"""Deterministic baseline-versus-efficient experiments for the MVP."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping

from core.efficient_dev import (
    ChangeTracker,
    ContextCompressor,
    InstructionRouter,
    ProjectMapBuilder,
    ReadCache,
    SmartReader,
    TaskRouter,
    TestRouter,
)
from core.efficient_dev.instruction_router import RULE_REFERENCES


BENCHMARK_VERSION = 1
FIXTURE_DIRECTORY = Path(__file__).resolve().parent / "fixtures"
SCENARIO_FILE = Path(__file__).resolve().parent / "scenarios.json"
MODULE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class FixtureSpec:
    name: str
    extra_modules: tuple[str, ...]
    noise_packages: int


@dataclass(frozen=True)
class ScenarioSpec:
    id: str
    kind: str
    fixture: str
    task: str
    changed_files: tuple[str, ...]
    cache_path: str
    cache_expectation: str
    required_files: tuple[str, ...]
    required_instruction_groups: tuple[str, ...]
    required_tests: tuple[str, ...]
    required_scope_expansions: tuple[str, ...]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_relative_path(relative: str) -> str:
    portable = relative.replace("\\", "/")
    path = PurePosixPath(portable)
    windows_path = PureWindowsPath(portable)
    if (
        "\x00" in relative
        or path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ":" in portable
        or not path.parts
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != portable
    ):
        raise ValueError(f"Unsafe benchmark path: {relative!r}")
    return portable


def load_fixture_spec(name: str) -> FixtureSpec:
    path = FIXTURE_DIRECTORY / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"Unknown benchmark fixture: {name!r}")
    data = _load_json(path)
    if not isinstance(data, dict) or data.get("name") != name:
        raise ValueError(f"Invalid benchmark fixture specification: {path}")
    modules = tuple(str(item) for item in data.get("extra_modules", ()))
    if len(set(modules)) != len(modules) or any(
        not MODULE_NAME.fullmatch(module) for module in modules
    ):
        raise ValueError(f"Invalid or duplicate module name in fixture: {name}")
    noise_packages = data.get("noise_packages")
    if not isinstance(noise_packages, int) or noise_packages < 0:
        raise ValueError(f"Invalid noise_packages in fixture: {name}")
    return FixtureSpec(name=name, extra_modules=modules, noise_packages=noise_packages)


def load_scenarios() -> tuple[ScenarioSpec, ...]:
    data = _load_json(SCENARIO_FILE)
    if not isinstance(data, list):
        raise ValueError("Benchmark scenarios must be a JSON list")
    scenarios: list[ScenarioSpec] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each benchmark scenario must be a JSON object")
        scenario = ScenarioSpec(
            id=str(item["id"]),
            kind=str(item["kind"]),
            fixture=str(item["fixture"]),
            task=str(item["task"]),
            changed_files=tuple(
                _validate_relative_path(str(path)) for path in item["changed_files"]
            ),
            cache_path=_validate_relative_path(str(item["cache_path"])),
            cache_expectation=str(item["cache_expectation"]),
            required_files=tuple(
                _validate_relative_path(str(path)) for path in item["required_files"]
            ),
            required_instruction_groups=tuple(
                str(name) for name in item["required_instruction_groups"]
            ),
            required_tests=tuple(
                _validate_relative_path(str(path)) for path in item["required_tests"]
            ),
            required_scope_expansions=tuple(
                str(name) for name in item["required_scope_expansions"]
            ),
        )
        if not scenario.id or not scenario.task.strip() or not MODULE_NAME.fullmatch(
            scenario.fixture
        ):
            raise ValueError("Benchmark scenario id, task, and fixture are required")
        if scenario.cache_expectation not in {"missing", "valid", "stale"}:
            raise ValueError(f"Invalid cache expectation in scenario: {scenario.id}")
        unknown_groups = set(scenario.required_instruction_groups) - set(RULE_REFERENCES)
        if unknown_groups:
            raise ValueError(
                f"Unknown instruction groups in scenario {scenario.id}: "
                + ", ".join(sorted(unknown_groups))
            )
        unknown_expansions = set(scenario.required_scope_expansions) - {
            "broaden-search",
            "full-test-suite",
        }
        if unknown_expansions:
            raise ValueError(
                f"Unknown scope expansions in scenario {scenario.id}: "
                + ", ".join(sorted(unknown_expansions))
            )
        scenarios.append(scenario)
    ids = tuple(scenario.id for scenario in scenarios)
    if len(set(ids)) != len(ids):
        raise ValueError("Benchmark scenario ids must be unique")
    return tuple(scenarios)


def _safe_project_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(_validate_relative_path(relative))
    target = root.joinpath(*path.parts).resolve(strict=False)
    target.relative_to(root.resolve())
    return target


def _write_project_file(root: Path, relative: str, content: str) -> None:
    target = _safe_project_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def materialize_fixture(name: str, destination: str | Path) -> Path:
    """Create one controlled project from a versioned fixture specification."""

    spec = load_fixture_spec(name)
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=False)
    common_files = {
        "README.md": f"# {name.title()} portfolio application\n\nControlled benchmark fixture.\n",
        "docs/architecture.md": (
            "# Architecture\n\n"
            "History, risk, dashboard, shared types, and settings are separate areas.\n"
        ),
        "package.json": json.dumps(
            {
                "name": f"benchmark-{name}",
                "private": True,
                "scripts": {"test": "controlled-suite"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "pyproject.toml": (
            "[project]\n"
            f'name = "benchmark-{name}"\n'
            'version = "0.0.0"\n'
            'requires-python = ">=3.10"\n'
        ),
        "src/frontend/history/render_history.ts": (
            "export function renderHistory(points: number[]): string {\n"
            '  return points.join(", ");\n'
            "}\n"
        ),
        "tests/frontend/history/render_history.test.ts": (
            'import { renderHistory } from "../../../src/frontend/history/render_history";\n\n'
            'if (renderHistory([1, 2]) !== "1, 2") {\n'
            '  throw new Error("unexpected history output");\n'
            "}\n"
        ),
        "src/frontend/dashboard/render_dashboard.ts": (
            "export function renderDashboard(total: number): string {\n"
            "  return `Total: ${total}`;\n"
            "}\n"
        ),
        "tests/frontend/dashboard/render_dashboard.test.ts": (
            'import { renderDashboard } from '
            '"../../../src/frontend/dashboard/render_dashboard";\n\n'
            'if (renderDashboard(4) !== "Total: 4") {\n'
            '  throw new Error("unexpected dashboard output");\n'
            "}\n"
        ),
        "src/risk/calculate_risk.py": (
            "def calculate_risk(values: list[float]) -> float:\n"
            "    return max(values, default=0.0)\n"
        ),
        "tests/risk/test_calculate_risk.py": (
            "from src.risk.calculate_risk import calculate_risk\n\n\n"
            "def test_calculate_risk() -> None:\n"
            "    assert calculate_risk([1.0, 3.0]) == 3.0\n"
        ),
        "src/shared/currency_types.py": (
            "SUPPORTED_CURRENCIES = (\"EUR\", \"USD\")\n"
        ),
        "tests/shared/test_currency_types.py": (
            "from src.shared.currency_types import SUPPORTED_CURRENCIES\n\n\n"
            "def test_currency_types() -> None:\n"
            "    assert \"USD\" in SUPPORTED_CURRENCIES\n"
        ),
        "src/settings/load_settings.py": (
            "def load_settings() -> dict[str, bool]:\n"
            "    return {\"history_enabled\": True}\n"
        ),
        "tests/settings/test_load_settings.py": (
            "from src.settings.load_settings import load_settings\n\n\n"
            "def test_load_settings() -> None:\n"
            "    assert load_settings()[\"history_enabled\"]\n"
        ),
        "src/legacy/compatibility.py": (
            "def compatibility_mode() -> str:\n"
            "    return \"stable\"\n"
        ),
        "tests/legacy/test_compatibility.py": (
            "from src.legacy.compatibility import compatibility_mode\n\n\n"
            "def test_compatibility() -> None:\n"
            "    assert compatibility_mode() == \"stable\"\n"
        ),
    }
    for relative, content in common_files.items():
        _write_project_file(root, relative, content)

    for module in spec.extra_modules:
        _write_project_file(
            root,
            f"src/modules/{module}.py",
            f"def {module}_summary(value: int) -> str:\n"
            f'    return "{module}:" + str(value)\n',
        )
        _write_project_file(
            root,
            f"tests/modules/test_{module}.py",
            f"from src.modules.{module} import {module}_summary\n\n\n"
            f"def test_{module}_summary() -> None:\n"
            f'    assert {module}_summary(2) == "{module}:2"\n',
        )

    for index in range(spec.noise_packages):
        _write_project_file(
            root,
            f"node_modules/dependency_{index:02d}/index.js",
            "export const generatedDependency = true;\n",
        )
    _write_project_file(root, "dist/bundle.js", "// generated bundle noise\n")
    return root


class BenchmarkHarness:
    """Compare one fair broad baseline with the current deterministic core."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[1]
        )
        self.scenarios = load_scenarios()
        self._scenario_by_id = {scenario.id: scenario for scenario in self.scenarios}

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(scenario.id for scenario in self.scenarios)

    def run(self, scenario_ids: Iterable[str] | None = None) -> dict[str, Any]:
        selected_ids = tuple(scenario_ids) if scenario_ids is not None else self.scenario_ids
        unknown = tuple(
            identifier
            for identifier in selected_ids
            if identifier not in self._scenario_by_id
        )
        if unknown:
            raise ValueError("Unknown benchmark scenarios: " + ", ".join(unknown))
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("Benchmark scenario ids must not repeat")

        with tempfile.TemporaryDirectory(prefix="efficient-dev-benchmark-") as temporary:
            temporary_root = Path(temporary)
            results = tuple(
                self._run_scenario(
                    self._scenario_by_id[identifier],
                    temporary_root / f"{index:02d}" / self._scenario_by_id[identifier].fixture,
                )
                for index, identifier in enumerate(selected_ids)
            )
        return {
            "benchmark_version": BENCHMARK_VERSION,
            "metrics_are_proxies": True,
            "real_token_usage_measured": False,
            "baseline_definition": (
                "Read every mapped first-party text file, load every instruction group, "
                "run every mapped test, and retain raw session input; standard noise "
                "exclusions are shared with efficient mode for a fair file universe."
            ),
            "efficient_definition": (
                "Use Project Map, Task Router, Smart Reader, Read Cache, Change Tracker, "
                "Instruction Router, Test Router, and Context Compressor."
            ),
            "scenarios": list(results),
            "summary": self._summary(results, selected_ids == self.scenario_ids),
        }

    def _run_scenario(self, scenario: ScenarioSpec, destination: Path) -> dict[str, Any]:
        project = materialize_fixture(scenario.fixture, destination)
        raw_project_files = sum(1 for path in project.rglob("*") if path.is_file())
        map_builder = ProjectMapBuilder()
        tracker = ChangeTracker(project, map_builder=map_builder)
        tracker.scan(update_baseline=True)
        read_cache = ReadCache(project, map_builder=map_builder)

        cached_mtime: int | None = None
        if scenario.cache_expectation in {"valid", "stale"}:
            read_cache.record(
                scenario.cache_path,
                summary="Current controlled knowledge for the benchmark target.",
                relationships=scenario.required_tests,
            )
            cached_mtime = _safe_project_path(
                project, scenario.cache_path
            ).stat().st_mtime_ns

        for relative in scenario.changed_files:
            self._mutate_file(_safe_project_path(project, relative))
        same_timestamp_change = False
        if scenario.cache_expectation == "stale" and cached_mtime is not None:
            target = _safe_project_path(project, scenario.cache_path)
            stat = target.stat()
            os.utime(target, ns=(stat.st_atime_ns, cached_mtime))
            same_timestamp_change = target.stat().st_mtime_ns == cached_mtime

        changes = tracker.scan(read_cache=read_cache)
        project_map = map_builder.build(project)
        task_route = TaskRouter(project_map).route(scenario.task)
        read_plan = SmartReader.plan_route(task_route)
        instruction_plan = InstructionRouter(project_map).route(
            scenario.task,
            task_route=task_route,
        )
        test_plan = TestRouter(project_map).route(changes, task_route=task_route)
        cache_lookup = read_cache.lookup(scenario.cache_path)

        all_paths = tuple(record.path for record in project_map.files)
        selected_paths = tuple(
            dict.fromkeys(candidate.path for candidate in task_route.candidate_files)
        )
        planned_paths = tuple(
            dict.fromkeys(
                target.path
                for target in (
                    read_plan.read_first
                    + read_plan.read_next
                    + read_plan.orientation_after_search
                )
            )
        )
        avoided_repeat_reads = int(
            cache_lookup.status == "valid" and not cache_lookup.requires_read
        )
        read_paths = tuple(
            path
            for path in planned_paths
            if not (avoided_repeat_reads and path == cache_lookup.path)
        )
        considered_paths = all_paths if task_route.requires_broader_search else selected_paths

        all_instruction_bytes = sum(
            (self.project_root / reference).stat().st_size
            for reference in RULE_REFERENCES.values()
        )
        selected_instruction_bytes = sum(
            (self.project_root / group.reference).stat().st_size
            for group in instruction_plan.selected
        )
        selected_tests = tuple(test.path for test in test_plan.selected_tests)

        raw_context = self._raw_context(
            scenario,
            selected_paths=selected_paths,
            changed_paths=tuple(sorted(scenario.changed_files)),
            selected_tests=selected_tests,
        )
        raw_context_bytes = len(
            json.dumps(
                raw_context,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        context_result = ContextCompressor(project).update(raw_context)
        compressed_context_bytes = context_result.metrics["context_size"]

        baseline = {
            "reading": self._reading_metrics(
                project,
                project_map,
                raw_project_files,
                considered_paths=all_paths,
                selected_paths=all_paths,
                read_paths=all_paths,
            ),
            "instructions": {
                "available_instruction_groups": len(RULE_REFERENCES),
                "selected_instruction_groups": len(RULE_REFERENCES),
                "instruction_bytes_all": all_instruction_bytes,
                "instruction_bytes_selected": all_instruction_bytes,
            },
            "tests": {
                "available_tests": len(project_map.tests),
                "selected_tests": len(project_map.tests),
                "full_suite_recommended": True,
            },
            "cache": {
                "cache_hits": 0,
                "cache_misses": 1,
                "stale_entries": 0,
                "avoided_repeat_reads": 0,
            },
            "context": {
                "raw_context_bytes": raw_context_bytes,
                "working_context_bytes": raw_context_bytes,
                "context_reduction_ratio": 0.0,
            },
            "required_context_coverage": 1.0,
        }
        efficient = {
            "reading": self._reading_metrics(
                project,
                project_map,
                raw_project_files,
                considered_paths=considered_paths,
                selected_paths=selected_paths,
                read_paths=read_paths,
            ),
            "instructions": {
                "available_instruction_groups": len(RULE_REFERENCES),
                "selected_instruction_groups": len(instruction_plan.selected),
                "instruction_bytes_all": all_instruction_bytes,
                "instruction_bytes_selected": selected_instruction_bytes,
            },
            "tests": {
                "available_tests": len(project_map.tests),
                "selected_tests": len(selected_tests),
                "full_suite_recommended": test_plan.full_suite_recommended,
            },
            "cache": {
                "status": cache_lookup.status,
                "cache_hits": cache_lookup.metrics["cache_hits"],
                "cache_misses": cache_lookup.metrics["cache_misses"],
                "stale_entries": cache_lookup.metrics["stale_entries"],
                "avoided_repeat_reads": avoided_repeat_reads,
                "stale_knowledge_used": bool(
                    cache_lookup.status == "stale" and cache_lookup.cached_knowledge
                ),
                "same_timestamp_change": same_timestamp_change,
            },
            "context": {
                "raw_context_bytes": raw_context_bytes,
                "working_context_bytes": compressed_context_bytes,
                "context_reduction_ratio": self._reduction(
                    raw_context_bytes,
                    compressed_context_bytes,
                ),
                "raw_context_items": self._raw_item_count(raw_context),
                "compressed_context_items": context_result.metrics["context_items"],
                "deduplicated_items": context_result.metrics["deduplicated_items"],
            },
            "routing": {
                "confidence": task_route.confidence,
                "requires_broader_search": task_route.requires_broader_search,
                "selected_files": list(selected_paths),
                "recommended_reads": list(read_paths),
                "selected_instruction_groups": list(instruction_plan.selected_names),
                "selected_tests": list(selected_tests),
            },
        }
        quality = self._quality(
            scenario,
            project_map_paths=all_paths,
            selected_paths=selected_paths,
            instruction_groups=instruction_plan.selected_names,
            selected_tests=selected_tests,
            broader_search=task_route.requires_broader_search,
            full_suite=test_plan.full_suite_recommended,
            cache_status=cache_lookup.status,
            cache_requires_read=cache_lookup.requires_read,
            stale_knowledge_used=efficient["cache"]["stale_knowledge_used"],
        )
        efficient["required_context_coverage"] = quality[
            "required_context_coverage"
        ]
        return {
            "id": scenario.id,
            "kind": scenario.kind,
            "fixture": scenario.fixture,
            "task": scenario.task,
            "baseline": baseline,
            "efficient": efficient,
            "comparison": {
                "reading_reduction_ratio": self._reduction(
                    baseline["reading"]["files_read_or_recommended"],
                    efficient["reading"]["files_read_or_recommended"],
                ),
                "instruction_byte_reduction_ratio": self._reduction(
                    all_instruction_bytes,
                    selected_instruction_bytes,
                ),
                "test_selection_reduction_ratio": self._reduction(
                    len(project_map.tests),
                    len(selected_tests),
                ),
                "context_reduction_ratio": efficient["context"][
                    "context_reduction_ratio"
                ],
            },
            "quality": quality,
        }

    @staticmethod
    def _mutate_file(path: Path) -> None:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            data["benchmark_revision"] = 1
            path.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return
        marker = (
            "// controlled benchmark change\n"
            if path.suffix in {".ts", ".js"}
            else "# controlled benchmark change\n"
        )
        path.write_text(
            path.read_text(encoding="utf-8") + marker,
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def _raw_context(
        scenario: ScenarioSpec,
        *,
        selected_paths: tuple[str, ...],
        changed_paths: tuple[str, ...],
        selected_tests: tuple[str, ...],
    ) -> dict[str, Any]:
        inspected = list(selected_paths) + list(selected_paths)
        changed = list(changed_paths) + list(changed_paths)
        tests = list(selected_tests) + list(selected_tests)
        return {
            "task": f"  {scenario.task}  ",
            "scope": inspected,
            "files_inspected": inspected,
            "files_changed": changed,
            "key_findings": [
                "  Routing evidence was reviewed.  ",
                "Routing evidence was reviewed.",
                "No full command logs are retained.",
                "No full command logs are retained.",
            ],
            "decisions": [
                "Use required context before considering efficiency.",
                "Use required context before considering efficiency.",
            ],
            "tests_run": tests,
            "open_issues": [],
            "next_action": "  Verify coverage and record proxy metrics.  ",
        }

    @staticmethod
    def _raw_item_count(raw_context: Mapping[str, Any]) -> int:
        count = 0
        for value in raw_context.values():
            if isinstance(value, list):
                count += len(value)
            elif value:
                count += 1
        return count

    @staticmethod
    def _reading_metrics(
        project: Path,
        project_map: Any,
        total_project_files: int,
        *,
        considered_paths: tuple[str, ...],
        selected_paths: tuple[str, ...],
        read_paths: tuple[str, ...],
    ) -> dict[str, int | float]:
        records = {record.path: record for record in project_map.files}

        def byte_count(paths: tuple[str, ...]) -> int:
            return sum(records[path].size_bytes for path in paths)

        def line_count(paths: tuple[str, ...]) -> int:
            return sum(
                len((project / path).read_text(encoding="utf-8").splitlines())
                for path in paths
            )

        mapped_files = len(records)
        return {
            "total_project_files": total_project_files,
            "mapped_first_party_files": mapped_files,
            "files_considered": len(considered_paths),
            "files_selected": len(selected_paths),
            "files_read_or_recommended": len(read_paths),
            "scope_ratio": round(len(read_paths) / mapped_files, 4) if mapped_files else 0.0,
            "bytes_considered": byte_count(considered_paths),
            "bytes_selected": byte_count(selected_paths),
            "bytes_read_or_recommended": byte_count(read_paths),
            "lines_considered": line_count(considered_paths),
            "lines_selected": line_count(selected_paths),
            "lines_read_or_recommended": line_count(read_paths),
        }

    @staticmethod
    def _quality(
        scenario: ScenarioSpec,
        *,
        project_map_paths: tuple[str, ...],
        selected_paths: tuple[str, ...],
        instruction_groups: tuple[str, ...],
        selected_tests: tuple[str, ...],
        broader_search: bool,
        full_suite: bool,
        cache_status: str,
        cache_requires_read: bool,
        stale_knowledge_used: bool,
    ) -> dict[str, Any]:
        file_context = set(selected_paths)
        if broader_search:
            file_context.update(project_map_paths)
        expansions = set()
        if broader_search:
            expansions.add("broaden-search")
        if full_suite:
            expansions.add("full-test-suite")

        missing_files = sorted(set(scenario.required_files) - file_context)
        missing_groups = sorted(
            set(scenario.required_instruction_groups) - set(instruction_groups)
        )
        missing_tests = sorted(set(scenario.required_tests) - set(selected_tests))
        missing_expansions = sorted(
            set(scenario.required_scope_expansions) - expansions
        )
        required_total = sum(
            len(items)
            for items in (
                scenario.required_files,
                scenario.required_instruction_groups,
                scenario.required_tests,
                scenario.required_scope_expansions,
            )
        )
        missing_total = sum(
            len(items)
            for items in (
                missing_files,
                missing_groups,
                missing_tests,
                missing_expansions,
            )
        )
        coverage = (
            round((required_total - missing_total) / required_total, 4)
            if required_total
            else 1.0
        )
        cache_safe = cache_status == scenario.cache_expectation
        if scenario.cache_expectation == "valid":
            cache_safe = cache_safe and not cache_requires_read
        if scenario.cache_expectation == "stale":
            cache_safe = cache_safe and cache_requires_read and not stale_knowledge_used
        return {
            "required_context_coverage": coverage,
            "quality_pass": coverage == 1.0 and cache_safe,
            "cache_expectation_met": cache_safe,
            "missing_required_files": missing_files,
            "missing_required_instruction_groups": missing_groups,
            "missing_required_tests": missing_tests,
            "missing_required_scope_expansions": missing_expansions,
        }

    def _summary(
        self,
        results: tuple[dict[str, Any], ...],
        complete_suite: bool,
    ) -> dict[str, Any]:
        baseline_reads = sum(
            item["baseline"]["reading"]["files_read_or_recommended"] for item in results
        )
        efficient_reads = sum(
            item["efficient"]["reading"]["files_read_or_recommended"] for item in results
        )
        baseline_instruction_bytes = sum(
            item["baseline"]["instructions"]["instruction_bytes_selected"]
            for item in results
        )
        efficient_instruction_bytes = sum(
            item["efficient"]["instructions"]["instruction_bytes_selected"]
            for item in results
        )
        baseline_tests = sum(
            item["baseline"]["tests"]["selected_tests"] for item in results
        )
        efficient_tests = sum(
            item["efficient"]["tests"]["selected_tests"] for item in results
        )
        baseline_context = sum(
            item["baseline"]["context"]["working_context_bytes"] for item in results
        )
        efficient_context = sum(
            item["efficient"]["context"]["working_context_bytes"] for item in results
        )
        criteria = self._mvp_criteria(results) if complete_suite else None
        return {
            "scenario_count": len(results),
            "complete_suite": complete_suite,
            "quality_passes": sum(item["quality"]["quality_pass"] for item in results),
            "quality_failures": sum(not item["quality"]["quality_pass"] for item in results),
            "required_context_coverage_min": min(
                (item["quality"]["required_context_coverage"] for item in results),
                default=1.0,
            ),
            "baseline_files_read_or_recommended": baseline_reads,
            "efficient_files_read_or_recommended": efficient_reads,
            "reading_reduction_ratio": self._reduction(baseline_reads, efficient_reads),
            "baseline_instruction_bytes": baseline_instruction_bytes,
            "efficient_instruction_bytes": efficient_instruction_bytes,
            "instruction_byte_reduction_ratio": self._reduction(
                baseline_instruction_bytes,
                efficient_instruction_bytes,
            ),
            "baseline_selected_tests": baseline_tests,
            "efficient_selected_tests": efficient_tests,
            "test_selection_reduction_ratio": self._reduction(
                baseline_tests,
                efficient_tests,
            ),
            "baseline_context_bytes": baseline_context,
            "efficient_context_bytes": efficient_context,
            "context_reduction_ratio": self._reduction(
                baseline_context,
                efficient_context,
            ),
            "cache_hits": sum(
                item["efficient"]["cache"]["cache_hits"] for item in results
            ),
            "cache_misses": sum(
                item["efficient"]["cache"]["cache_misses"] for item in results
            ),
            "stale_entries": sum(
                item["efficient"]["cache"]["stale_entries"] for item in results
            ),
            "avoided_repeat_reads": sum(
                item["efficient"]["cache"]["avoided_repeat_reads"] for item in results
            ),
            "mvp_criteria": criteria,
            "mvp_success": all(criteria.values()) if criteria is not None else None,
        }

    @staticmethod
    def _mvp_criteria(results: tuple[dict[str, Any], ...]) -> dict[str, bool]:
        by_id = {item["id"]: item for item in results}
        local = tuple(item for item in results if item["kind"] == "local")
        return {
            "all_required_context_covered": all(
                item["quality"]["required_context_coverage"] == 1.0 for item in results
            ),
            "all_quality_checks_pass": all(
                item["quality"]["quality_pass"] for item in results
            ),
            "local_reading_scope_below_35_percent": all(
                item["efficient"]["reading"]["scope_ratio"] < 0.35 for item in local
            ),
            "local_instructions_are_selective": all(
                item["efficient"]["instructions"]["selected_instruction_groups"]
                < item["baseline"]["instructions"]["selected_instruction_groups"]
                for item in local
            ),
            "local_tests_are_selective": all(
                item["efficient"]["tests"]["selected_tests"]
                < item["baseline"]["tests"]["selected_tests"]
                for item in local
            ),
            "shared_change_recommends_full_suite": by_id["shared-core-large"][
                "efficient"
            ]["tests"]["full_suite_recommended"],
            "configuration_change_recommends_full_suite": by_id[
                "configuration-medium"
            ]["efficient"]["tests"]["full_suite_recommended"],
            "ambiguous_task_broadens_search": by_id["ambiguous-large"]["efficient"][
                "routing"
            ]["requires_broader_search"],
            "unchanged_cache_avoids_repeat_orientation": by_id[
                "repeated-cache-medium"
            ]["efficient"]["cache"]["avoided_repeat_reads"] == 1,
            "changed_cache_is_stale_and_not_reused": (
                by_id["changed-cache-medium"]["efficient"]["cache"]["status"]
                == "stale"
                and not by_id["changed-cache-medium"]["efficient"]["cache"][
                    "stale_knowledge_used"
                ]
            ),
        }

    @staticmethod
    def _reduction(baseline: int, efficient: int) -> float:
        if baseline == 0:
            return 0.0
        return round(1 - efficient / baseline, 4)
