"""Turn routing evidence into a non-binding, safety-aware reading plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .task_router import FileCandidate, RouteResult, TaskRouter


EXPANSION_TRIGGERS = (
    "an import, call, inheritance edge, or runtime reference leaves the current scope",
    "the change affects a shared interface, public API, or cross-module contract",
    "a related or dependent test lives outside the current scope",
    "a shared type, schema, model, migration, or generated contract is involved",
    "configuration, build metadata, feature flags, or environment behavior may change the result",
    "the source of data or control flow is still unknown",
    "a build, test, type-check, or runtime failure points outside the current scope",
    "the available evidence is insufficient for a safe and correct change",
)

FULL_FILE_CONDITIONS = (
    "relevant search hits are spread across the file",
    "file-level ordering, initialization, or invariants affect the task",
    "the edit changes a shared interface or needs surrounding declarations",
    "the file is a small manifest or configuration unit that must be interpreted as a whole",
    "section boundaries cannot be established safely from search results",
)


@dataclass(frozen=True)
class ReadTarget:
    path: str
    mode: str
    reason: str


@dataclass(frozen=True)
class ReadPlan:
    task: str
    confidence: str
    scope_mode: str
    sequence: tuple[dict[str, Any], ...]
    read_first: tuple[ReadTarget, ...]
    read_next: tuple[ReadTarget, ...]
    orientation_after_search: tuple[ReadTarget, ...]
    defer: tuple[str, ...]
    full_file_conditions: tuple[str, ...]
    expansion: dict[str, Any]
    metrics: dict[str, int | float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "confidence": self.confidence,
            "scope_mode": self.scope_mode,
            "sequence": list(self.sequence),
            "read_first": [asdict(item) for item in self.read_first],
            "read_next": [asdict(item) for item in self.read_next],
            "orientation_after_search": [
                asdict(item) for item in self.orientation_after_search
            ],
            "defer": list(self.defer),
            "full_file_conditions": list(self.full_file_conditions),
            "expansion": self.expansion,
            "metrics": self.metrics,
        }


class SmartReader:
    """Recommend reading order while keeping scope expansion explicitly available."""

    def __init__(self, router: TaskRouter) -> None:
        self.router = router

    def plan(self, task: str) -> ReadPlan:
        return self.plan_route(self.router.route(task))

    @staticmethod
    def plan_route(route: RouteResult) -> ReadPlan:
        read_first = tuple(
            SmartReader._read_target(candidate, "relevant_sections")
            for candidate in route.high_probability
        )
        read_next = tuple(
            SmartReader._read_target(candidate, "relevant_sections_if_needed")
            for candidate in route.medium_probability
        )
        orientation = tuple(
            SmartReader._read_target(candidate, "only_after_broad_search")
            for candidate in route.fallback_files
        )
        primary_targets = read_first if read_first else orientation
        primary_action = (
            "read_relevant_sections" if read_first else "read_orientation_after_search"
        )
        primary_reason = (
            "Start with the strongest explicit path and relationship signals."
            if read_first
            else "With low confidence, read orientation files only after broad mapped search."
        )

        search_reason = (
            "Routing confidence is low; search all mapped paths before choosing files."
            if route.requires_broader_search
            else "Confirm the routing signals and locate relevant symbols before reading."
        )
        sequence = (
            {
                "step": 1,
                "action": "inspect_project_map",
                "reason": "Use compact structure and relationships before repository reads.",
            },
            {
                "step": 2,
                "action": "search",
                "roots": list(route.search_roots),
                "terms": list(route.task_tokens),
                "reason": search_reason,
            },
            {
                "step": 3,
                "action": primary_action,
                "targets": [item.path for item in primary_targets],
                "reason": primary_reason,
            },
            {
                "step": 4,
                "action": "read_additional_candidates_if_needed",
                "targets": [item.path for item in read_next],
                "reason": "Use medium signals only when first-pass evidence is insufficient.",
            },
            {
                "step": 5,
                "action": "expand_scope_on_evidence",
                "reason": "The initial scope is a recommendation, never a hard boundary.",
            },
        )

        return ReadPlan(
            task=route.task,
            confidence=route.confidence,
            scope_mode=route.scope_mode,
            sequence=sequence,
            read_first=read_first,
            read_next=read_next,
            orientation_after_search=orientation,
            defer=route.deferred_directories,
            full_file_conditions=FULL_FILE_CONDITIONS,
            expansion={
                "allowed": True,
                "rule": "Keep the initial scope minimal, but expand it whenever evidence or risk requires more context.",
                "triggers": list(EXPANSION_TRIGGERS),
                "next_action": "Add the referenced paths, record the reason, search them, and then revise the read order.",
            },
            metrics=route.metrics,
        )

    @staticmethod
    def _read_target(candidate: FileCandidate, mode: str) -> ReadTarget:
        return ReadTarget(
            path=candidate.path,
            mode=mode,
            reason="; ".join(candidate.reasons),
        )
