"""Select task-relevant instruction references using transparent signals."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .project_map import ProjectMap
from .task_router import RouteResult, TaskRouter, tokenize


RULE_REFERENCES = {
    "base": "rules/base.md",
    "frontend": "rules/frontend.md",
    "backend": "rules/backend.md",
    "testing": "rules/testing.md",
    "git": "rules/git.md",
    "security": "rules/security.md",
    "database": "rules/database.md",
    "documentation": "rules/documentation.md",
}

CATEGORY_TERMS = {
    "frontend": frozenset(
        {
            "browser",
            "component",
            "css",
            "frontend",
            "html",
            "jsx",
            "react",
            "render",
            "style",
            "tsx",
            "ui",
            "vue",
            "компонент",
            "интерфейс",
            "отображение",
        }
    ),
    "backend": frozenset(
        {
            "api",
            "backend",
            "controller",
            "endpoint",
            "handler",
            "http",
            "server",
            "service",
            "бэкенд",
            "сервер",
        }
    ),
    "testing": frozenset(
        {
            "assertion",
            "coverage",
            "fixture",
            "spec",
            "test",
            "tests",
            "testing",
            "проверка",
            "тест",
            "тесты",
        }
    ),
    "git": frozenset(
        {
            "branch",
            "commit",
            "git",
            "merge",
            "push",
            "rebase",
            "ветка",
            "коммит",
        }
    ),
    "security": frozenset(
        {
            "auth",
            "authorization",
            "credential",
            "encrypt",
            "password",
            "permission",
            "secret",
            "security",
            "token",
            "безопасность",
            "пароль",
            "секрет",
            "токен",
        }
    ),
    "database": frozenset(
        {
            "database",
            "db",
            "migration",
            "query",
            "repository",
            "schema",
            "sql",
            "база",
            "запрос",
            "миграция",
        }
    ),
    "documentation": frozenset(
        {
            "doc",
            "docs",
            "documentation",
            "markdown",
            "readme",
            "документация",
        }
    ),
}

PATH_TERMS = {
    "frontend": frozenset({"client", "components", "frontend", "styles", "ui", "web"}),
    "backend": frozenset({"api", "backend", "controllers", "handlers", "server", "services"}),
    "testing": frozenset({"spec", "specs", "test", "tests"}),
    "security": frozenset({"auth", "permissions", "security"}),
    "database": frozenset({"database", "db", "migrations", "models", "schema"}),
    "documentation": frozenset({"docs", "documentation", "readme"}),
}


@dataclass(frozen=True)
class InstructionGroup:
    name: str
    reference: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class InstructionPlan:
    task: str
    route_confidence: str
    selected: tuple[InstructionGroup, ...]
    deferred: tuple[dict[str, str], ...]
    safe_expansion: bool
    metrics: dict[str, int]

    @property
    def selected_names(self) -> tuple[str, ...]:
        return tuple(group.name for group in self.selected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "route_confidence": self.route_confidence,
            "selected": [asdict(group) for group in self.selected],
            "deferred": list(self.deferred),
            "safe_expansion": self.safe_expansion,
            "metrics": self.metrics,
        }


class InstructionRouter:
    """Recommend rule references without loading unrelated rule contents."""

    def __init__(self, project_map: ProjectMap) -> None:
        self.project_map = project_map
        self._files = {record.path: record for record in project_map.files}

    def route(
        self,
        task: str,
        *,
        task_route: RouteResult | None = None,
    ) -> InstructionPlan:
        route = task_route or TaskRouter(self.project_map).route(task)
        if route.task != task:
            raise ValueError("Instruction routing task must match the Task Router result")

        task_tokens = set(tokenize(task))
        scoped_candidates = route.high_probability + route.medium_probability
        scoped_paths = tuple(candidate.path for candidate in scoped_candidates)
        path_tokens = {
            token
            for path in scoped_paths
            for token in tokenize(path)
        }
        selected_reasons: dict[str, list[str]] = {
            "base": ["mandatory safety and scope-expansion rules"]
        }

        for category in RULE_REFERENCES:
            if category == "base":
                continue
            reasons: list[str] = []
            matched_task = sorted(task_tokens & CATEGORY_TERMS.get(category, frozenset()))
            matched_paths = sorted(path_tokens & PATH_TERMS.get(category, frozenset()))
            if matched_task:
                reasons.append("task terms: " + ", ".join(matched_task))
            if matched_paths:
                reasons.append("routed path terms: " + ", ".join(matched_paths))
            if category == "testing" and any(
                self._files[candidate.path].kind == "test"
                for candidate in scoped_candidates
            ):
                reasons.append("Task Router selected a related test file")
            if category == "documentation" and any(
                self._files[candidate.path].kind == "documentation"
                for candidate in scoped_candidates
            ):
                reasons.append("Task Router selected documentation")
            if reasons:
                selected_reasons[category] = reasons

        safe_expansion = route.confidence == "low"
        matched_domain_groups = set(selected_reasons) - {"base", "testing"}
        if safe_expansion:
            selected_reasons.setdefault(
                "testing",
                ["low routing confidence; keep verification guidance available"],
            )
        if safe_expansion and not matched_domain_groups:
            selected_reasons.setdefault(
                "security",
                ["ambiguous task; retain conservative security guidance"],
            )

        selected = tuple(
            InstructionGroup(
                name=name,
                reference=reference,
                reasons=tuple(selected_reasons[name]),
            )
            for name, reference in RULE_REFERENCES.items()
            if name in selected_reasons
        )
        deferred = tuple(
            {
                "name": name,
                "reference": reference,
            }
            for name, reference in RULE_REFERENCES.items()
            if name not in selected_reasons
        )
        return InstructionPlan(
            task=task,
            route_confidence=route.confidence,
            selected=selected,
            deferred=deferred,
            safe_expansion=safe_expansion,
            metrics={
                "available_instruction_groups": len(RULE_REFERENCES),
                "selected_instruction_groups": len(selected),
            },
        )
