"""Compare project files with a content-fingerprint baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .fingerprint import fingerprint_file
from .paths import resolve_project_file, resolve_runtime_path
from .project_map import ProjectMap, ProjectMapBuilder
from .read_cache import ReadCache


TRACKING_VERSION = 1


@dataclass(frozen=True)
class ChangeResult:
    baseline_exists: bool
    baseline_updated: bool
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    unchanged: tuple[str, ...]
    invalidated_cache_entries: tuple[str, ...]
    project_map_stale: bool
    project_map_refresh_paths: tuple[str, ...]
    project_map_refresh_directories: tuple[str, ...]
    metrics: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_exists": self.baseline_exists,
            "baseline_updated": self.baseline_updated,
            "added": list(self.added),
            "modified": list(self.modified),
            "deleted": list(self.deleted),
            "unchanged": list(self.unchanged),
            "invalidated_cache_entries": list(self.invalidated_cache_entries),
            "project_map_stale": self.project_map_stale,
            "project_map_refresh_paths": list(self.project_map_refresh_paths),
            "project_map_refresh_directories": list(
                self.project_map_refresh_directories
            ),
            "metrics": self.metrics,
        }


class ChangeTracker:
    """Track added, modified, deleted, and unchanged eligible project files."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        state_path: str | Path | None = None,
        map_builder: ProjectMapBuilder | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root is not a directory: {self.project_root}")
        self.state_path = self._resolve_state_path(state_path)
        self.map_builder = map_builder or ProjectMapBuilder()

    def scan(
        self,
        *,
        read_cache: ReadCache | None = None,
        update_baseline: bool = False,
    ) -> ChangeResult:
        project_map, current = self._snapshot()
        baseline = self._load_baseline()
        baseline_files = baseline if baseline is not None else {}

        current_paths = set(current)
        baseline_paths = set(baseline_files)
        added = tuple(sorted(current_paths - baseline_paths))
        deleted = tuple(sorted(baseline_paths - current_paths))
        modified = tuple(
            sorted(
                path
                for path in current_paths & baseline_paths
                if current[path] != baseline_files[path]
            )
        )
        unchanged = tuple(
            sorted(
                path
                for path in current_paths & baseline_paths
                if current[path] == baseline_files[path]
            )
        )

        cache = read_cache or ReadCache(
            self.project_root,
            map_builder=self.map_builder,
        )
        reconciliation = cache.reconcile(current)
        changed_paths = tuple(sorted(added + modified + deleted))
        refresh_directories = self._refresh_directories(changed_paths)

        if update_baseline:
            self._save_baseline(current)

        return ChangeResult(
            baseline_exists=baseline is not None,
            baseline_updated=update_baseline,
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            invalidated_cache_entries=reconciliation.invalidated,
            project_map_stale=bool(changed_paths),
            project_map_refresh_paths=changed_paths,
            project_map_refresh_directories=refresh_directories,
            metrics={
                "changed_files": len(changed_paths),
                "unchanged_files": len(unchanged),
                "cache_entries": reconciliation.metrics["cache_entries"],
                "stale_entries": reconciliation.metrics["stale_entries"],
                "mapped_files": project_map.metrics["mapped_files"],
            },
        )

    def _snapshot(self) -> tuple[ProjectMap, dict[str, str]]:
        project_map = self.map_builder.build(self.project_root)
        fingerprints = {
            record.path: fingerprint_file(self.project_root / record.path)
            for record in project_map.files
        }
        return project_map, fingerprints

    def _load_baseline(self) -> dict[str, str] | None:
        if not self.state_path.exists():
            return None
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        if data.get("version") != TRACKING_VERSION:
            raise ValueError(
                f"Unsupported change state version: {data.get('version')!r}; expected {TRACKING_VERSION}."
            )
        files = data.get("files")
        if not isinstance(files, dict):
            raise ValueError("Change state must contain a files object")
        normalized_files: dict[str, str] = {}
        for path, fingerprint in files.items():
            normalized, _ = resolve_project_file(self.project_root, str(path))
            if normalized != path or self.map_builder.is_excluded_path(normalized):
                raise ValueError(f"Invalid or excluded change state path: {path}")
            normalized_files[normalized] = str(fingerprint)
        return normalized_files

    def _save_baseline(self, fingerprints: Mapping[str, str]) -> Path:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": TRACKING_VERSION,
            "files": {path: fingerprints[path] for path in sorted(fingerprints)},
        }
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(self.state_path)
        return self.state_path

    def _resolve_state_path(self, state_path: str | Path | None) -> Path:
        return resolve_runtime_path(
            self.project_root,
            state_path,
            default_relative=Path("state") / "tracked-files.json",
        )

    @staticmethod
    def _refresh_directories(paths: tuple[str, ...]) -> tuple[str, ...]:
        directories: set[str] = set()
        for path in paths:
            parent = PurePosixPath(path).parent
            directories.add("." if str(parent) == "." else parent.as_posix())
        return tuple(sorted(directories))
