"""Compact project-local knowledge cache with content-based validity checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from .fingerprint import fingerprint_file
from .paths import resolve_project_file, resolve_runtime_path
from .project_map import ProjectMapBuilder


CACHE_VERSION = 1
VALIDITY_STATES = frozenset({"valid", "stale", "invalid"})
MAX_SUMMARY_LENGTH = 2_000
MAX_METADATA_ITEMS = 50
MAX_METADATA_ITEM_LENGTH = 300


@dataclass(frozen=True)
class CacheEntry:
    path: str
    fingerprint: str
    summary: str
    symbols: tuple[str, ...]
    relationships: tuple[str, ...]
    validity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "fingerprint": self.fingerprint,
            "summary": self.summary,
            "symbols": list(self.symbols),
            "relationships": list(self.relationships),
            "validity": self.validity,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CacheEntry":
        validity = str(data["validity"])
        if validity not in VALIDITY_STATES:
            raise ValueError(f"Unsupported cache validity state: {validity!r}")
        entry = cls(
            path=str(data["path"]),
            fingerprint=str(data["fingerprint"]),
            summary=str(data["summary"]),
            symbols=tuple(str(item) for item in data.get("symbols", [])),
            relationships=tuple(str(item) for item in data.get("relationships", [])),
            validity=validity,
        )
        if not entry.summary.strip() or len(entry.summary) > MAX_SUMMARY_LENGTH:
            raise ValueError("Stored cache summary is empty or exceeds the size limit")
        for label, items in (
            ("symbols", entry.symbols),
            ("relationships", entry.relationships),
        ):
            if len(items) > MAX_METADATA_ITEMS:
                raise ValueError(f"Stored cache {label} exceed {MAX_METADATA_ITEMS} items")
            if any(not item.strip() or len(item) > MAX_METADATA_ITEM_LENGTH for item in items):
                raise ValueError(f"Stored cache {label} contain an empty or oversized item")
        return entry


@dataclass(frozen=True)
class CacheLookup:
    path: str
    status: str
    requires_read: bool
    reason: str
    stored_fingerprint: str | None
    current_fingerprint: str | None
    cached_knowledge: dict[str, Any] | None
    metrics: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CacheStatus:
    entries: tuple[dict[str, str], ...]
    removed_deleted: tuple[str, ...]
    metrics: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": list(self.entries),
            "removed_deleted": list(self.removed_deleted),
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class CacheReconcileResult:
    invalidated: tuple[str, ...]
    removed_deleted: tuple[str, ...]
    metrics: dict[str, int]


class ReadCache:
    """Keep one bounded knowledge record per current project file."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        storage_path: str | Path | None = None,
        map_builder: ProjectMapBuilder | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root is not a directory: {self.project_root}")
        self.storage_path = self._resolve_storage_path(storage_path)
        self.map_builder = map_builder or ProjectMapBuilder()
        self.entries = self._load_entries()

    def record(
        self,
        file_path: str | Path,
        *,
        summary: str,
        symbols: Iterable[str] = (),
        relationships: Iterable[str] = (),
    ) -> CacheEntry:
        record = self.map_builder.inspect_file(self.project_root, file_path)
        if record is None:
            raise ValueError(f"File is missing, excluded, binary, or too large: {file_path}")
        clean_summary = summary.strip()
        if not clean_summary:
            raise ValueError("Cache summary must not be empty")
        if len(clean_summary) > MAX_SUMMARY_LENGTH:
            raise ValueError(
                f"Cache summary exceeds {MAX_SUMMARY_LENGTH} characters; store compact knowledge only"
            )

        entry = CacheEntry(
            path=record.path,
            fingerprint=fingerprint_file(self.project_root / record.path),
            summary=clean_summary,
            symbols=self._normalize_items(symbols, "symbols"),
            relationships=self._normalize_items(relationships, "relationships"),
            validity="valid",
        )
        self.entries[entry.path] = entry
        self.save()
        return entry

    def lookup(self, file_path: str | Path, *, require_exact: bool = False) -> CacheLookup:
        relative, absolute = resolve_project_file(self.project_root, file_path)
        entry = self.entries.get(relative)
        if entry is None:
            return self._lookup_result(
                path=relative,
                status="missing",
                requires_read=True,
                reason="No cached knowledge exists for this file.",
                entry=None,
                current_fingerprint=None,
                cache_hit=False,
            )

        if not absolute.is_file():
            del self.entries[relative]
            self.save()
            return self._lookup_result(
                path=relative,
                status="deleted",
                requires_read=True,
                reason="The source file no longer exists; its cache entry was removed.",
                entry=entry,
                current_fingerprint=None,
                cache_hit=False,
            )

        current = fingerprint_file(absolute)
        if entry.validity == "invalid":
            return self._lookup_result(
                path=relative,
                status="invalid",
                requires_read=True,
                reason="The cache entry was explicitly invalidated.",
                entry=entry,
                current_fingerprint=current,
                cache_hit=False,
            )

        if current != entry.fingerprint:
            if entry.validity != "stale":
                entry = replace(entry, validity="stale")
                self.entries[relative] = entry
                self.save()
            return self._lookup_result(
                path=relative,
                status="stale",
                requires_read=True,
                reason="The content fingerprint changed; cached knowledge must not be used.",
                entry=entry,
                current_fingerprint=current,
                cache_hit=False,
            )

        if entry.validity != "valid":
            entry = replace(entry, validity="valid")
            self.entries[relative] = entry
            self.save()
        return self._lookup_result(
            path=relative,
            status="valid",
            requires_read=require_exact,
            reason=(
                "Fingerprint matches, but the caller requested exact source content."
                if require_exact
                else "Fingerprint matches; compact cached knowledge may be reused."
            ),
            entry=entry,
            current_fingerprint=current,
            cache_hit=True,
        )

    def status(self) -> CacheStatus:
        removed: list[str] = []
        changed = False
        for path in sorted(tuple(self.entries)):
            entry = self.entries[path]
            try:
                _, absolute = resolve_project_file(self.project_root, path)
            except ValueError:
                removed.append(path)
                del self.entries[path]
                changed = True
                continue
            if not absolute.is_file():
                removed.append(path)
                del self.entries[path]
                changed = True
                continue
            current = fingerprint_file(absolute)
            expected = "valid" if current == entry.fingerprint else "stale"
            if entry.validity != "invalid" and entry.validity != expected:
                self.entries[path] = replace(entry, validity=expected)
                changed = True
        if changed:
            self.save()
        return CacheStatus(
            entries=tuple(
                {
                    "path": entry.path,
                    "validity": entry.validity,
                    "fingerprint": entry.fingerprint,
                }
                for entry in (self.entries[path] for path in sorted(self.entries))
            ),
            removed_deleted=tuple(removed),
            metrics=self._metrics(),
        )

    def invalidate(self, file_path: str | Path) -> bool:
        relative, _ = resolve_project_file(self.project_root, file_path)
        entry = self.entries.get(relative)
        if entry is None:
            return False
        if entry.validity != "invalid":
            self.entries[relative] = replace(entry, validity="invalid")
            self.save()
        return True

    def reconcile(self, current_fingerprints: Mapping[str, str]) -> CacheReconcileResult:
        invalidated: list[str] = []
        removed: list[str] = []
        changed = False

        for path in sorted(tuple(self.entries)):
            entry = self.entries[path]
            current = current_fingerprints.get(path)
            if current is None:
                invalidated.append(path)
                removed.append(path)
                del self.entries[path]
                changed = True
                continue
            if entry.validity == "invalid":
                invalidated.append(path)
                continue
            expected = "valid" if current == entry.fingerprint else "stale"
            if expected == "stale":
                invalidated.append(path)
            if entry.validity != expected:
                self.entries[path] = replace(entry, validity=expected)
                changed = True

        if changed:
            self.save()
        return CacheReconcileResult(
            invalidated=tuple(invalidated),
            removed_deleted=tuple(removed),
            metrics=self._metrics(),
        )

    def get_entry(self, file_path: str | Path) -> CacheEntry | None:
        relative, _ = resolve_project_file(self.project_root, file_path)
        return self.entries.get(relative)

    def save(self) -> Path:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": CACHE_VERSION,
            "entries": [self.entries[path].to_dict() for path in sorted(self.entries)],
        }
        temporary = self.storage_path.with_name(self.storage_path.name + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(self.storage_path)
        return self.storage_path

    def _resolve_storage_path(self, storage_path: str | Path | None) -> Path:
        return resolve_runtime_path(
            self.project_root,
            storage_path,
            default_relative=Path("cache") / "read-cache.json",
        )

    def _load_entries(self) -> dict[str, CacheEntry]:
        if not self.storage_path.exists():
            return {}
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        if data.get("version") != CACHE_VERSION:
            raise ValueError(
                f"Unsupported read cache version: {data.get('version')!r}; expected {CACHE_VERSION}."
            )
        entries: dict[str, CacheEntry] = {}
        for item in data.get("entries", []):
            entry = CacheEntry.from_dict(item)
            normalized, _ = resolve_project_file(self.project_root, entry.path)
            if normalized != entry.path or self.map_builder.is_excluded_path(normalized):
                raise ValueError(f"Invalid or excluded read cache path: {entry.path}")
            if entry.path in entries:
                raise ValueError(f"Duplicate read cache path: {entry.path}")
            entries[entry.path] = entry
        return entries

    @staticmethod
    def _normalize_items(values: Iterable[str], label: str) -> tuple[str, ...]:
        normalized = tuple(sorted({value.strip() for value in values if value.strip()}))
        if len(normalized) > MAX_METADATA_ITEMS:
            raise ValueError(f"Cache {label} exceed {MAX_METADATA_ITEMS} items")
        if any(len(value) > MAX_METADATA_ITEM_LENGTH for value in normalized):
            raise ValueError(
                f"A cache {label} item exceeds {MAX_METADATA_ITEM_LENGTH} characters"
            )
        return normalized

    def _lookup_result(
        self,
        *,
        path: str,
        status: str,
        requires_read: bool,
        reason: str,
        entry: CacheEntry | None,
        current_fingerprint: str | None,
        cache_hit: bool,
    ) -> CacheLookup:
        knowledge = None
        if cache_hit and entry is not None:
            knowledge = {
                "summary": entry.summary,
                "symbols": list(entry.symbols),
                "relationships": list(entry.relationships),
            }
        metrics = self._metrics()
        metrics.update(
            {
                "cache_hits": int(cache_hit),
                "cache_misses": int(not cache_hit),
            }
        )
        return CacheLookup(
            path=path,
            status=status,
            requires_read=requires_read,
            reason=reason,
            stored_fingerprint=entry.fingerprint if entry else None,
            current_fingerprint=current_fingerprint,
            cached_knowledge=knowledge,
            metrics=metrics,
        )

    def _metrics(self) -> dict[str, int]:
        return {
            "cache_entries": len(self.entries),
            "stale_entries": sum(
                entry.validity != "valid" for entry in self.entries.values()
            ),
        }
