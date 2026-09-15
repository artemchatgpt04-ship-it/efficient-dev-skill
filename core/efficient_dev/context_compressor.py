"""Maintain bounded project-local session facts without generating new content."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from .paths import resolve_runtime_path


SESSION_VERSION = 1
SCALAR_LIMITS = {
    "task": 500,
    "next_action": 500,
}
LIST_LIMITS = {
    "scope": (20, 300),
    "files_inspected": (100, 300),
    "files_changed": (100, 300),
    "key_findings": (50, 500),
    "decisions": (50, 500),
    "tests_run": (50, 500),
    "open_issues": (50, 500),
}
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class SessionState:
    task: str = ""
    scope: tuple[str, ...] = ()
    files_inspected: tuple[str, ...] = ()
    files_changed: tuple[str, ...] = ()
    key_findings: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    tests_run: tuple[str, ...] = ()
    open_issues: tuple[str, ...] = ()
    next_action: str = ""
    version: int = SESSION_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for field in LIST_LIMITS:
            data[field] = list(data[field])
        return data


@dataclass(frozen=True)
class ContextResult:
    state: SessionState
    metrics: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "metrics": self.metrics,
        }


class ContextCompressor:
    """Normalize, deduplicate, replace, and bound caller-supplied session facts."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        state_path: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root is not a directory: {self.project_root}")
        self.state_path = resolve_runtime_path(
            self.project_root,
            state_path,
            default_relative=Path("state") / "session.json",
        )

    def show(self) -> ContextResult:
        state = self._load()
        return ContextResult(state=state, metrics=self._metrics(state, 0))

    def update(self, facts: Mapping[str, Any]) -> ContextResult:
        if not facts:
            raise ValueError("At least one session fact is required")
        unknown = sorted(set(facts) - set(SCALAR_LIMITS) - set(LIST_LIMITS))
        if unknown:
            raise ValueError("Unsupported session fields: " + ", ".join(unknown))

        state = self._load()
        deduplicated = 0
        updates: dict[str, Any] = {}
        for field, value in facts.items():
            if field in SCALAR_LIMITS:
                if not isinstance(value, str):
                    raise ValueError(f"Session field {field} must be a string")
                updates[field] = self._clean_text(value, SCALAR_LIMITS[field])
                continue
            values, duplicates = self._clean_list(field, value)
            updates[field] = values
            deduplicated += duplicates

        state = replace(state, **updates)
        self._save(state)
        return ContextResult(
            state=state,
            metrics=self._metrics(state, deduplicated),
        )

    def _load(self) -> SessionState:
        if not self.state_path.exists():
            return SessionState()
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        if data.get("version") != SESSION_VERSION:
            raise ValueError(
                f"Unsupported session version: {data.get('version')!r}; expected {SESSION_VERSION}."
            )

        values: dict[str, Any] = {"version": SESSION_VERSION}
        for field, limit in SCALAR_LIMITS.items():
            raw = data.get(field, "")
            if not isinstance(raw, str) or raw != self._clean_text(raw, limit):
                raise ValueError(f"Invalid or oversized stored session field: {field}")
            values[field] = raw
        for field in LIST_LIMITS:
            raw = data.get(field, [])
            cleaned, duplicates = self._clean_list(field, raw)
            if duplicates or not isinstance(raw, list) or list(cleaned) != raw:
                raise ValueError(f"Invalid, duplicate, or oversized stored session field: {field}")
            values[field] = cleaned
        return SessionState(**values)

    def _save(self, state: SessionState) -> Path:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        temporary.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(self.state_path)
        return self.state_path

    @staticmethod
    def _clean_text(value: str, limit: int) -> str:
        normalized = WHITESPACE_PATTERN.sub(" ", value.strip())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"

    def _clean_list(
        self,
        field: str,
        value: Any,
    ) -> tuple[tuple[str, ...], int]:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise ValueError(f"Session field {field} must be a list of strings")
        max_items, max_length = LIST_LIMITS[field]
        result: list[str] = []
        seen: set[str] = set()
        duplicates = 0
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"Session field {field} must contain only strings")
            normalized = self._clean_text(item, max_length)
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            if len(result) >= max_items:
                continue
            result.append(normalized)
        return tuple(result), duplicates

    @staticmethod
    def _metrics(state: SessionState, deduplicated: int) -> dict[str, int]:
        data = state.to_dict()
        item_count = sum(bool(data[field]) for field in SCALAR_LIMITS)
        item_count += sum(len(data[field]) for field in LIST_LIMITS)
        serialized = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return {
            "context_items": item_count,
            "context_size": len(serialized),
            "deduplicated_items": deduplicated,
        }
