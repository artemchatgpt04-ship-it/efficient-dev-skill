"""Build a compact, deterministic map of a source repository."""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .paths import resolve_project_file


MAP_VERSION = 1

DEFAULT_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".cache",
        ".efficient-dev",
        ".git",
        ".gradle",
        ".hg",
        ".mypy_cache",
        ".next",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".turbo",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "env",
        "node_modules",
        "out",
        "target",
        "tmp",
        "temp",
        "venv",
        "vendor",
    }
)

DEFAULT_EXCLUDED_FILE_GLOBS = (
    "*.class",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.jar",
    "*.min.css",
    "*.min.js",
    "*.o",
    "*.obj",
    "*.pdb",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.war",
    "*.zip",
    ".DS_Store",
    "Thumbs.db",
)

BINARY_EXTENSIONS = frozenset(
    {
        ".7z",
        ".avi",
        ".bmp",
        ".doc",
        ".docx",
        ".eot",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".mov",
        ".mp3",
        ".mp4",
        ".otf",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".rar",
        ".tar",
        ".ttf",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xls",
        ".xlsx",
        ".xz",
    }
)

LANGUAGE_BY_EXTENSION = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".h": "c",
    ".hpp": "cpp",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".php": "php",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "typescript",
}

CONFIG_NAMES = frozenset(
    {
        ".editorconfig",
        ".gitignore",
        ".npmrc",
        "build.gradle",
        "build.gradle.kts",
        "cargo.toml",
        "compose.yaml",
        "compose.yml",
        "docker-compose.yaml",
        "docker-compose.yml",
        "dockerfile",
        "go.mod",
        "go.sum",
        "gradle.properties",
        "makefile",
        "package-lock.json",
        "package.json",
        "pnpm-lock.yaml",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "settings.gradle",
        "settings.gradle.kts",
        "tox.ini",
        "tsconfig.json",
        "yarn.lock",
    }
)

CONFIG_SUFFIXES = (
    ".config.js",
    ".config.json",
    ".config.mjs",
    ".config.ts",
    ".properties",
)

DOCUMENTATION_EXTENSIONS = frozenset({".adoc", ".md", ".mdx", ".rst"})
TEST_DIRECTORY_NAMES = frozenset({"__tests__", "spec", "specs", "test", "tests"})
ENTRY_POINT_NAMES = frozenset(
    {
        "app.js",
        "app.py",
        "app.ts",
        "cli.js",
        "cli.py",
        "cli.ts",
        "index.js",
        "index.ts",
        "lib.rs",
        "main.go",
        "main.js",
        "main.py",
        "main.rs",
        "main.ts",
        "mod.rs",
        "server.js",
        "server.py",
        "server.ts",
    }
)


@dataclass(frozen=True)
class FileRecord:
    path: str
    kind: str
    language: str | None
    size_bytes: int
    entry_point: bool


@dataclass(frozen=True)
class TestRelationship:
    source: str
    test: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class ProjectMap:
    """Portable representation of repository structure and likely test links."""

    project_name: str
    root: str
    files: tuple[FileRecord, ...]
    directories: tuple[dict[str, Any], ...]
    important_files: tuple[str, ...]
    entry_points: tuple[str, ...]
    tests: tuple[str, ...]
    configuration: tuple[str, ...]
    documentation: tuple[str, ...]
    test_relationships: tuple[TestRelationship, ...]
    exclusions: dict[str, Any]
    metrics: dict[str, int]
    version: int = MAP_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "project_name": self.project_name,
            "root": self.root,
            "directories": list(self.directories),
            "files": [asdict(item) for item in self.files],
            "important_files": list(self.important_files),
            "entry_points": list(self.entry_points),
            "tests": list(self.tests),
            "configuration": list(self.configuration),
            "documentation": list(self.documentation),
            "test_relationships": [
                {
                    "source": item.source,
                    "test": item.test,
                    "signals": list(item.signals),
                }
                for item in self.test_relationships
            ],
            "exclusions": self.exclusions,
            "metrics": self.metrics,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def save(self, destination: str | Path) -> Path:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination_path.with_name(destination_path.name + ".tmp")
        temporary_path.write_text(self.to_json(), encoding="utf-8", newline="\n")
        temporary_path.replace(destination_path)
        return destination_path

    @classmethod
    def load(cls, source: str | Path) -> "ProjectMap":
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        if data.get("version") != MAP_VERSION:
            raise ValueError(
                f"Unsupported project map version: {data.get('version')!r}; expected {MAP_VERSION}."
            )
        return cls(
            version=data["version"],
            project_name=data["project_name"],
            root=data["root"],
            files=tuple(FileRecord(**item) for item in data["files"]),
            directories=tuple(data["directories"]),
            important_files=tuple(data["important_files"]),
            entry_points=tuple(data["entry_points"]),
            tests=tuple(data["tests"]),
            configuration=tuple(data["configuration"]),
            documentation=tuple(data["documentation"]),
            test_relationships=tuple(
                TestRelationship(
                    source=item["source"],
                    test=item["test"],
                    signals=tuple(item["signals"]),
                )
                for item in data["test_relationships"]
            ),
            exclusions=data["exclusions"],
            metrics=data["metrics"],
        )


class ProjectMapBuilder:
    """Build maps with bounded metadata inspection and extensible exclusions."""

    def __init__(
        self,
        *,
        extra_excludes: Iterable[str] = (),
        max_file_size: int = 1_000_000,
    ) -> None:
        if max_file_size < 1:
            raise ValueError("max_file_size must be positive")
        self.extra_excludes = tuple(sorted(set(extra_excludes)))
        self.max_file_size = max_file_size

    def build(self, root: str | Path) -> ProjectMap:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise ValueError(f"Repository root is not a directory: {root_path}")

        files: list[FileRecord] = []
        pruned_directory_count = 0
        skipped_file_count = 0
        total_files = 0

        for current_root, directory_names, file_names in os.walk(root_path, topdown=True):
            current_path = Path(current_root)
            relative_directory = current_path.relative_to(root_path)

            kept_directories: list[str] = []
            for name in sorted(directory_names):
                candidate = current_path / name
                relative = (relative_directory / name).as_posix()
                if candidate.is_symlink() or self._excluded_directory(relative, name):
                    pruned_directory_count += 1
                else:
                    kept_directories.append(name)
            directory_names[:] = kept_directories

            for name in sorted(file_names):
                candidate = current_path / name
                relative = (relative_directory / name).as_posix()
                total_files += 1

                if candidate.is_symlink() or self._excluded_file(relative, name):
                    skipped_file_count += 1
                    continue

                try:
                    size = candidate.stat().st_size
                except OSError:
                    skipped_file_count += 1
                    continue

                if size > self.max_file_size or self._is_binary(candidate):
                    skipped_file_count += 1
                    continue

                kind, language = self._classify(relative)
                files.append(
                    FileRecord(
                        path=relative,
                        kind=kind,
                        language=language,
                        size_bytes=size,
                        entry_point=self._is_entry_point(relative, kind),
                    )
                )

        files.sort(key=lambda item: item.path)
        relationships = self._build_test_relationships(files)
        directories = self._summarize_directories(files)
        entry_points = tuple(item.path for item in files if item.entry_point)
        tests = tuple(item.path for item in files if item.kind == "test")
        configuration = tuple(item.path for item in files if item.kind == "config")
        documentation = tuple(item.path for item in files if item.kind == "documentation")
        important_files = tuple(
            item.path
            for item in files
            if item.entry_point or item.kind in {"config", "documentation"}
        )

        return ProjectMap(
            project_name=root_path.name,
            root=".",
            files=tuple(files),
            directories=directories,
            important_files=important_files,
            entry_points=entry_points,
            tests=tests,
            configuration=configuration,
            documentation=documentation,
            test_relationships=relationships,
            exclusions={
                "default_directories": sorted(DEFAULT_EXCLUDED_DIRECTORIES),
                "default_file_globs": list(DEFAULT_EXCLUDED_FILE_GLOBS),
                "extra_patterns": list(self.extra_excludes),
                "max_file_size": self.max_file_size,
            },
            metrics={
                "total_files": total_files,
                "mapped_files": len(files),
                "excluded_files": skipped_file_count,
                "mapped_directories": len(directories),
                "pruned_directories": pruned_directory_count,
            },
        )

    def inspect_file(
        self, root: str | Path, file_path: str | Path
    ) -> FileRecord | None:
        """Classify one eligible file using the same policy as a full map build."""

        root_path = Path(root).resolve()
        relative, candidate = resolve_project_file(root_path, file_path)
        if self.is_excluded_path(relative) or not candidate.is_file():
            return None
        size = candidate.stat().st_size
        if size > self.max_file_size or self._is_binary(candidate):
            return None
        kind, language = self._classify(relative)
        return FileRecord(
            path=relative,
            kind=kind,
            language=language,
            size_bytes=size,
            entry_point=self._is_entry_point(relative, kind),
        )

    def is_excluded_path(self, relative: str) -> bool:
        """Return whether a portable relative path is outside the mapping policy."""

        relative_path = PurePosixPath(relative.replace("\\", "/"))
        if relative_path.is_absolute() or ".." in relative_path.parts or not relative_path.name:
            return True
        current = PurePosixPath()
        for part in relative_path.parts[:-1]:
            current /= part
            if self._excluded_directory(current.as_posix(), part):
                return True
        return self._excluded_file(relative_path.as_posix(), relative_path.name)

    def _excluded_directory(self, relative: str, name: str) -> bool:
        if name.lower() in DEFAULT_EXCLUDED_DIRECTORIES:
            return True
        return self._matches_extra(relative, name)

    def _excluded_file(self, relative: str, name: str) -> bool:
        if any(fnmatch.fnmatch(name, pattern) for pattern in DEFAULT_EXCLUDED_FILE_GLOBS):
            return True
        if Path(name).suffix.lower() in BINARY_EXTENSIONS:
            return True
        return self._matches_extra(relative, name)

    def _matches_extra(self, relative: str, name: str) -> bool:
        posix_path = PurePosixPath(relative)
        return any(
            fnmatch.fnmatch(name, pattern)
            or fnmatch.fnmatch(relative, pattern)
            or posix_path.match(pattern)
            for pattern in self.extra_excludes
        )

    @staticmethod
    def _is_binary(path: Path) -> bool:
        try:
            with path.open("rb") as stream:
                return b"\x00" in stream.read(4096)
        except OSError:
            return True

    @staticmethod
    def _classify(relative: str) -> tuple[str, str | None]:
        path = PurePosixPath(relative)
        name = path.name.lower()
        original_stem = path.stem
        stem = original_stem.lower()
        suffix = path.suffix.lower()
        language = LANGUAGE_BY_EXTENSION.get(suffix)
        parts = {part.lower() for part in path.parts[:-1]}

        if (
            parts.intersection(TEST_DIRECTORY_NAMES)
            or stem.startswith(("test_", "spec_"))
            or stem.endswith(("_test", "_spec", ".test", ".spec"))
            or original_stem.endswith(("Test", "Tests", "Spec", "Specs"))
        ):
            return "test", language
        if (
            name in CONFIG_NAMES
            or name.startswith("requirements") and name.endswith(".txt")
            or name.endswith(CONFIG_SUFFIXES)
            or ".github" in parts and suffix in {".yaml", ".yml"}
        ):
            return "config", language
        if (
            suffix in DOCUMENTATION_EXTENSIONS
            or name.startswith("readme")
            or "docs" in parts
            or "documentation" in parts
        ):
            return "documentation", language
        if language:
            return "source", language
        return "other", None

    @staticmethod
    def _is_entry_point(relative: str, kind: str) -> bool:
        if kind not in {"source", "test"}:
            return False
        name = PurePosixPath(relative).name.lower()
        return name in ENTRY_POINT_NAMES or name.endswith("application.java")

    @staticmethod
    def _normalized_stem(path: str) -> str:
        original_name = PurePosixPath(path).name
        name = original_name.lower()
        for suffix in sorted(LANGUAGE_BY_EXTENSION, key=len, reverse=True):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                original_name = original_name[: -len(suffix)]
                break
        name = re.sub(r"\.(test|spec)$", "", name)
        name = re.sub(r"^(test_|spec_)", "", name)
        name = re.sub(r"(_test|_spec)$", "", name)
        if original_name.endswith(("Tests", "Specs")):
            name = name[:-5]
        elif original_name.endswith(("Test", "Spec")):
            name = name[:-4]
        return name

    def _build_test_relationships(
        self, files: list[FileRecord]
    ) -> tuple[TestRelationship, ...]:
        sources_by_stem: dict[str, list[str]] = defaultdict(list)
        tests_by_stem: dict[str, list[str]] = defaultdict(list)

        for item in files:
            stem = self._normalized_stem(item.path)
            if not stem:
                continue
            if item.kind == "source":
                sources_by_stem[stem].append(item.path)
            elif item.kind == "test":
                tests_by_stem[stem].append(item.path)

        relationships: list[TestRelationship] = []
        for stem in sorted(sources_by_stem.keys() & tests_by_stem.keys()):
            for source in sorted(sources_by_stem[stem]):
                for test in sorted(tests_by_stem[stem]):
                    relationships.append(
                        TestRelationship(
                            source=source,
                            test=test,
                            signals=(f"matching normalized stem: {stem}",),
                        )
                    )
        return tuple(relationships)

    @staticmethod
    def _summarize_directories(files: list[FileRecord]) -> tuple[dict[str, Any], ...]:
        direct_counts: dict[str, int] = defaultdict(int)
        recursive_counts: dict[str, int] = defaultdict(int)
        kinds: dict[str, set[str]] = defaultdict(set)

        for item in files:
            parent = PurePosixPath(item.path).parent
            parent_text = "." if str(parent) == "." else parent.as_posix()
            direct_counts[parent_text] += 1

            ancestors = ["."]
            if parent_text != ".":
                current = PurePosixPath()
                for part in parent.parts:
                    current /= part
                    ancestors.append(current.as_posix())
            for ancestor in ancestors:
                recursive_counts[ancestor] += 1
                kinds[ancestor].add(item.kind)

        return tuple(
            {
                "path": path,
                "direct_files": direct_counts[path],
                "total_files": recursive_counts[path],
                "kinds": sorted(kinds[path]),
            }
            for path in sorted(recursive_counts)
        )
