"""Route a task to a small initial repository scope using explicit heuristics."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping

from .project_map import FileRecord, ProjectMap


WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "bug",
        "change",
        "create",
        "error",
        "fix",
        "for",
        "in",
        "issue",
        "of",
        "on",
        "please",
        "the",
        "to",
        "update",
        "with",
        "для",
        "изменить",
        "исправить",
        "на",
        "ошибка",
        "ошибку",
        "по",
        "с",
        "создать",
        "и",
        "в",
    }
)

ROLE_TERMS = {
    "test": frozenset({"spec", "specs", "test", "tests", "testing", "тест", "тесты"}),
    "config": frozenset(
        {"config", "configuration", "manifest", "settings", "конфиг", "настройки"}
    ),
    "documentation": frozenset(
        {"doc", "docs", "documentation", "readme", "документация"}
    ),
}


def tokenize(value: str) -> tuple[str, ...]:
    """Return stable identifier-like tokens without language-specific parsing."""

    expanded = CAMEL_BOUNDARY.sub(" ", value.replace("\\", "/"))
    return tuple(token.lower() for token in WORD_PATTERN.findall(expanded))


def _similar(left: str, right: str) -> bool:
    if left == right:
        return True
    return min(len(left), len(right)) >= 4 and (
        left.startswith(right) or right.startswith(left)
    )


@dataclass(frozen=True)
class FileCandidate:
    path: str
    kind: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DirectoryCandidate:
    path: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RouteResult:
    task: str
    task_tokens: tuple[str, ...]
    confidence: str
    scope_mode: str
    high_probability: tuple[FileCandidate, ...]
    medium_probability: tuple[FileCandidate, ...]
    fallback_files: tuple[FileCandidate, ...]
    candidate_directories: tuple[DirectoryCandidate, ...]
    search_roots: tuple[str, ...]
    deferred_directories: tuple[str, ...]
    requires_broader_search: bool
    metrics: dict[str, int | float]

    @property
    def candidate_files(self) -> tuple[FileCandidate, ...]:
        return self.high_probability + self.medium_probability + self.fallback_files

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "task_tokens": list(self.task_tokens),
            "confidence": self.confidence,
            "scope_mode": self.scope_mode,
            "high_probability": [asdict(item) for item in self.high_probability],
            "medium_probability": [asdict(item) for item in self.medium_probability],
            "fallback_files": [asdict(item) for item in self.fallback_files],
            "candidate_directories": [asdict(item) for item in self.candidate_directories],
            "search_roots": list(self.search_roots),
            "deferred_directories": list(self.deferred_directories),
            "requires_broader_search": self.requires_broader_search,
            "metrics": self.metrics,
        }


class TaskRouter:
    """Rank mapped files without pretending to understand source semantics."""

    def __init__(
        self,
        project_map: ProjectMap,
        *,
        aliases: Mapping[str, Iterable[str]] | None = None,
        max_candidates: int = 24,
    ) -> None:
        if max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        self.project_map = project_map
        self.aliases = {
            key.lower(): tuple(sorted({value.lower() for value in values}))
            for key, values in (aliases or {}).items()
        }
        self.max_candidates = max_candidates
        self._files = {item.path: item for item in project_map.files}

    def route(self, task: str) -> RouteResult:
        if not task.strip():
            raise ValueError("Task description must not be empty")

        raw_task_tokens = tuple(dict.fromkeys(tokenize(task)))
        task_tokens = self._expand_task_tokens(raw_task_tokens)
        searchable_tokens = tuple(token for token in task_tokens if token not in STOP_WORDS)
        scored: dict[str, tuple[int, list[str]]] = {}

        for item in self.project_map.files:
            score, reasons = self._score_file(item, task, raw_task_tokens, searchable_tokens)
            if score:
                scored[item.path] = (score, reasons)

        self._add_linked_files(scored)

        ranked = [
            FileCandidate(
                path=path,
                kind=self._files[path].kind,
                score=score,
                reasons=tuple(dict.fromkeys(reasons)),
            )
            for path, (score, reasons) in scored.items()
            if score >= 3
        ]
        ranked.sort(key=lambda item: (-item.score, item.path))
        total_ranked = len(ranked)
        ranked = ranked[: self.max_candidates]

        high = tuple(item for item in ranked if item.score >= 6)
        medium = tuple(item for item in ranked if item.score < 6)
        top_score = ranked[0].score if ranked else 0
        confidence = "high" if top_score >= 8 else "medium" if ranked else "low"
        requires_broader_search = not ranked

        fallback = self._fallback_files() if requires_broader_search else ()
        all_candidates = high + medium + fallback
        directory_candidates = self._directory_candidates(high + medium)
        search_roots = (
            tuple(item.path for item in directory_candidates)
            if directory_candidates
            else (".",)
        )
        deferred = self._deferred_directories(search_roots, requires_broader_search)
        mapped_files = self.project_map.metrics["mapped_files"]
        candidate_count = len(all_candidates)

        return RouteResult(
            task=task,
            task_tokens=searchable_tokens,
            confidence=confidence,
            scope_mode="broaden-search" if requires_broader_search else "focused",
            high_probability=high,
            medium_probability=medium,
            fallback_files=fallback,
            candidate_directories=directory_candidates,
            search_roots=search_roots,
            deferred_directories=deferred,
            requires_broader_search=requires_broader_search,
            metrics={
                "total_files": self.project_map.metrics["total_files"],
                "mapped_files": mapped_files,
                "candidate_files": candidate_count,
                "candidate_directories": len(directory_candidates),
                "scope_ratio": round(candidate_count / mapped_files, 4) if mapped_files else 0.0,
                "truncated_candidates": max(0, total_ranked - len(ranked)),
            },
        )

    def _expand_task_tokens(self, raw_tokens: tuple[str, ...]) -> tuple[str, ...]:
        expanded: list[str] = list(raw_tokens)
        for token in raw_tokens:
            expanded.extend(self.aliases.get(token, ()))
        return tuple(dict.fromkeys(expanded))

    @staticmethod
    def _score_file(
        item: FileRecord,
        task: str,
        raw_task_tokens: tuple[str, ...],
        task_tokens: tuple[str, ...],
    ) -> tuple[int, list[str]]:
        path_tokens = tuple(dict.fromkeys(tokenize(item.path)))
        path_token_set = set(path_tokens)
        exact = sorted(set(task_tokens) & path_token_set)
        related = sorted(
            {
                task_token
                for task_token in task_tokens
                if task_token not in exact
                and any(_similar(task_token, path_token) for path_token in path_tokens)
            }
        )

        score = len(exact) * 4 + len(related) * 2
        reasons: list[str] = []
        if exact:
            reasons.append("task terms in path: " + ", ".join(exact))
        if related:
            reasons.append("closely related path terms: " + ", ".join(related))

        normalized_task = task.lower().replace("\\", "/")
        if item.path.lower() in normalized_task:
            score += 10
            reasons.append("task names this path")

        raw_set = set(raw_task_tokens)
        for kind, role_terms in ROLE_TERMS.items():
            matched_roles = sorted(raw_set & role_terms)
            if matched_roles and item.kind == kind:
                score += 4
                reasons.append(f"task explicitly mentions {kind}")

        if item.language and item.language in raw_set:
            score += 2
            reasons.append(f"task mentions language: {item.language}")

        return score, reasons

    def _add_linked_files(self, scored: dict[str, tuple[int, list[str]]]) -> None:
        for relationship in self.project_map.test_relationships:
            source_score = scored.get(relationship.source, (0, []))[0]
            test_score = scored.get(relationship.test, (0, []))[0]
            if source_score >= 3:
                self._raise_score(
                    scored,
                    relationship.test,
                    5,
                    f"linked test for {relationship.source}",
                )
            if test_score >= 3:
                self._raise_score(
                    scored,
                    relationship.source,
                    5,
                    f"source linked from {relationship.test}",
                )

    @staticmethod
    def _raise_score(
        scored: dict[str, tuple[int, list[str]]], path: str, minimum: int, reason: str
    ) -> None:
        score, reasons = scored.get(path, (0, []))
        if reason not in reasons:
            reasons.append(reason)
        scored[path] = (max(score, minimum), reasons)

    def _fallback_files(self) -> tuple[FileCandidate, ...]:
        fallback_paths = list(
            dict.fromkeys(
                self.project_map.entry_points
                + self.project_map.configuration
                + self.project_map.documentation
            )
        )[:6]
        return tuple(
            FileCandidate(
                path=path,
                kind=self._files[path].kind,
                score=1,
                reasons=("low-confidence orientation candidate; search before reading",),
            )
            for path in fallback_paths
        )

    @staticmethod
    def _directory_candidates(
        candidates: tuple[FileCandidate, ...],
    ) -> tuple[DirectoryCandidate, ...]:
        scores: dict[str, int] = defaultdict(int)
        reasons: dict[str, list[str]] = defaultdict(list)
        for candidate in candidates:
            parent = PurePosixPath(candidate.path).parent
            directory = "." if str(parent) == "." else parent.as_posix()
            scores[directory] = max(scores[directory], candidate.score)
            reason = f"contains candidate {candidate.path}"
            if reason not in reasons[directory]:
                reasons[directory].append(reason)
        return tuple(
            DirectoryCandidate(path=path, score=scores[path], reasons=tuple(reasons[path]))
            for path in sorted(scores, key=lambda item: (-scores[item], item))
        )

    def _deferred_directories(
        self, search_roots: tuple[str, ...], requires_broader_search: bool
    ) -> tuple[str, ...]:
        if requires_broader_search or "." in search_roots:
            return ()
        all_top_level = {
            directory["path"].split("/", 1)[0]
            for directory in self.project_map.directories
            if directory["path"] != "."
        }
        selected_top_level = {path.split("/", 1)[0] for path in search_roots}
        return tuple(sorted(all_top_level - selected_top_level))
