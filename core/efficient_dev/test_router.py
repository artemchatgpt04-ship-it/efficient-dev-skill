"""Recommend the smallest safe validation scope for known file changes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

from .change_tracker import ChangeResult
from .project_map import ProjectMap
from .task_router import RouteResult, tokenize


SHARED_DIRECTORY_NAMES = frozenset({"common", "core", "shared"})
PUBLIC_INTERFACE_STEMS = frozenset({"base", "interface", "interfaces", "types"})
FULL_SUITE_ESCALATION_CONDITIONS = (
    "a focused test fails outside the expected local cause",
    "new evidence shows cross-module consumers or a public contract",
    "the changed scope expands to configuration, shared code, or multiple modules",
    "the available relationships are incomplete or the remaining risk is unclear",
    "the work is being finalized at a stage or release boundary",
)


@dataclass(frozen=True)
class TestSelection:
    path: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TestPlan:
    changed_files: tuple[str, ...]
    selected_tests: tuple[TestSelection, ...]
    area_test_directories: tuple[str, ...]
    full_suite_recommended: bool
    reasons: tuple[str, ...]
    escalation_conditions: tuple[str, ...]
    metrics: dict[str, int | bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_files": list(self.changed_files),
            "selected_tests": [asdict(test) for test in self.selected_tests],
            "area_test_directories": list(self.area_test_directories),
            "full_suite_recommended": self.full_suite_recommended,
            "reasons": list(self.reasons),
            "escalation_conditions": list(self.escalation_conditions),
            "metrics": self.metrics,
        }


class TestRouter:
    """Use mapped source-test links and explicit risk signals to plan tests."""

    def __init__(self, project_map: ProjectMap) -> None:
        self.project_map = project_map
        self._files = {record.path: record for record in project_map.files}

    def route(
        self,
        changes: ChangeResult,
        *,
        task_route: RouteResult | None = None,
    ) -> TestPlan:
        changed_files = tuple(sorted(changes.added + changes.modified + changes.deleted))
        changed_set = set(changed_files)
        test_reasons: dict[str, list[str]] = {}
        plan_reasons: list[str] = []

        for relationship in self.project_map.test_relationships:
            if relationship.source in changed_set:
                self._add_test_reason(
                    test_reasons,
                    relationship.test,
                    f"mapped test for changed source {relationship.source}",
                )

        for path in changed_files:
            record = self._files.get(path)
            if record and record.kind == "test":
                self._add_test_reason(test_reasons, path, "the test file itself changed")

        if task_route is not None and changed_files:
            for candidate in task_route.high_probability + task_route.medium_probability:
                record = self._files.get(candidate.path)
                if record and record.kind == "test":
                    self._add_test_reason(
                        test_reasons,
                        candidate.path,
                        "Task Router selected this test for the current task",
                    )

        full_suite = False
        if not changes.baseline_exists:
            full_suite = True
            plan_reasons.append("no accepted change baseline; impact is unknown")

        configuration_changes = tuple(
            path
            for path in changed_files
            if self._files.get(path) and self._files[path].kind == "config"
        )
        if configuration_changes:
            full_suite = True
            plan_reasons.append(
                "critical configuration changed: " + ", ".join(configuration_changes)
            )

        shared_changes = tuple(path for path in changed_files if self._is_shared(path))
        if shared_changes:
            full_suite = True
            plan_reasons.append(
                "shared/core or public interface changed: " + ", ".join(shared_changes)
            )

        if changes.deleted:
            full_suite = True
            plan_reasons.append(
                "deleted files may have unmapped consumers: " + ", ".join(changes.deleted)
            )

        source_changes = tuple(
            path
            for path in changed_files
            if self._files.get(path) and self._files[path].kind == "source"
        )
        linked_sources = {
            relationship.source
            for relationship in self.project_map.test_relationships
            if relationship.test in test_reasons
        }
        unlinked_sources = tuple(path for path in source_changes if path not in linked_sources)
        if unlinked_sources:
            full_suite = True
            plan_reasons.append(
                "no reliable mapped test for changed source: " + ", ".join(unlinked_sources)
            )

        if task_route is not None and task_route.requires_broader_search and changed_files:
            full_suite = True
            plan_reasons.append("Task Router confidence is low; validation risk is unclear")

        if not changed_files:
            plan_reasons.append("no eligible file changes detected")
        elif not full_suite:
            plan_reasons.append("changes are local and have explicit mapped tests")

        all_tests = tuple(sorted(self.project_map.tests))
        if full_suite:
            for test in all_tests:
                self._add_test_reason(
                    test_reasons,
                    test,
                    "included because the full suite is recommended",
                )

        selected_tests = tuple(
            TestSelection(path=path, reasons=tuple(test_reasons[path]))
            for path in sorted(test_reasons)
        )
        focused_paths = tuple(
            path
            for path, reasons in test_reasons.items()
            if "included because the full suite is recommended" not in reasons
        )
        area_directories = tuple(
            sorted(
                {
                    self._parent(path)
                    for path in focused_paths
                }
            )
        )
        return TestPlan(
            changed_files=changed_files,
            selected_tests=selected_tests,
            area_test_directories=area_directories,
            full_suite_recommended=full_suite,
            reasons=tuple(plan_reasons),
            escalation_conditions=FULL_SUITE_ESCALATION_CONDITIONS,
            metrics={
                "candidate_tests": len(all_tests),
                "selected_tests": len(selected_tests),
                "full_suite_recommended": full_suite,
            },
        )

    @staticmethod
    def _add_test_reason(
        test_reasons: dict[str, list[str]], path: str, reason: str
    ) -> None:
        reasons = test_reasons.setdefault(path, [])
        if reason not in reasons:
            reasons.append(reason)

    @staticmethod
    def _parent(path: str) -> str:
        parent = PurePosixPath(path).parent
        return "." if str(parent) == "." else parent.as_posix()

    @staticmethod
    def _is_shared(path: str) -> bool:
        parsed = PurePosixPath(path)
        directory_tokens = {
            token
            for part in parsed.parts[:-1]
            for token in tokenize(part)
        }
        return bool(directory_tokens & SHARED_DIRECTORY_NAMES) or (
            parsed.name == "__init__.py"
            or parsed.stem.lower() in PUBLIC_INTERFACE_STEMS
        )
