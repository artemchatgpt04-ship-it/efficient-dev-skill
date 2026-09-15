"""Manifest-driven, project-state-preserving Skill installation service."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping

from .adapters import AdapterDestination, get_adapter


MANIFEST_NAME = ".efficient-dev-install.json"
BUNDLE_ROOT_FILES = ("SKILL.md", "VERSION")
BUNDLE_EXPLICIT_FILES = (
    "core/README.md",
    "core/__init__.py",
    "docs/project-state.md",
    "scripts/README.md",
    "scripts/efficient_dev.py",
)


@dataclass(frozen=True)
class InstallationManifest:
    version: str
    agent: str
    install_mode: str
    managed_files: tuple[str, ...]
    installed_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["managed_files"] = list(self.managed_files)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InstallationManifest":
        managed = data.get("managed_files")
        if not isinstance(managed, list) or not all(
            isinstance(item, str) for item in managed
        ):
            raise ValueError("Installation manifest managed_files must be a string list")
        manifest = cls(
            version=str(data.get("version", "")),
            agent=str(data.get("agent", "")),
            install_mode=str(data.get("install_mode", "")),
            managed_files=tuple(managed),
            installed_at=str(data.get("installed_at", "")),
        )
        if not manifest.version or not manifest.agent or not manifest.install_mode:
            raise ValueError("Installation manifest is missing required metadata")
        if not manifest.installed_at:
            raise ValueError("Installation manifest is missing installed_at")
        return manifest


@dataclass(frozen=True)
class InstallationStatus:
    status: str
    agent: str
    install_mode: str
    install_root: str
    version: str | None
    core_available: bool
    project_state_exists: bool
    problems: tuple[str, ...]
    discovery_note: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["problems"] = list(self.problems)
        return data


@dataclass(frozen=True)
class InstallResult:
    action: str
    agent: str
    install_mode: str
    install_root: str
    version: str
    managed_files: tuple[str, ...]
    project_state_preserved: bool
    remaining_unmanaged: tuple[str, ...]
    discovery_note: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["managed_files"] = list(self.managed_files)
        data["remaining_unmanaged"] = list(self.remaining_unmanaged)
        return data


class SkillInstaller:
    """Install a bounded bundle and mutate only manifest-owned Skill files."""

    def __init__(self, source_root: str | Path | None = None) -> None:
        self.source_root = (
            Path(source_root).resolve()
            if source_root is not None
            else Path(__file__).resolve().parents[1]
        )
        if not self.source_root.is_dir():
            raise ValueError(f"Skill source root is not a directory: {self.source_root}")
        self.version = self._read_version(self.source_root / "VERSION")
        self._validate_skill_file(self.source_root / "SKILL.md")

    def install(
        self,
        agent: str,
        project_root: str | Path,
        *,
        mode: str = "workspace",
        user_home: str | Path | None = None,
    ) -> InstallResult:
        project, destination = self._resolve_destination(
            agent,
            project_root,
            mode=mode,
            user_home=user_home,
        )
        install_root = Path(destination.install_root)
        if install_root.exists() or install_root.is_symlink():
            raise ValueError(
                f"Installation destination already exists; use update or inspect it first: {install_root}"
            )

        install_root.parent.mkdir(parents=True, exist_ok=True)
        stage = self._temporary_sibling(install_root, "install")
        try:
            manifest = self._build_bundle(stage, destination)
            stage.replace(install_root)
        except Exception:
            self._remove_known_tree(stage, install_root.parent, "install")
            raise

        self._validate_skill_file(install_root / "SKILL.md")
        return self._result(
            "installed",
            destination,
            manifest,
            project,
        )

    def status(
        self,
        agent: str,
        project_root: str | Path,
        *,
        mode: str = "workspace",
        user_home: str | Path | None = None,
    ) -> InstallationStatus:
        project, destination = self._resolve_destination(
            agent,
            project_root,
            mode=mode,
            user_home=user_home,
        )
        install_root = Path(destination.install_root)
        state_exists = (project / ".efficient-dev").is_dir()
        if not install_root.exists() and not install_root.is_symlink():
            return InstallationStatus(
                status="missing",
                agent=destination.agent,
                install_mode=destination.install_mode,
                install_root=str(install_root),
                version=None,
                core_available=False,
                project_state_exists=state_exists,
                problems=("installation directory does not exist",),
                discovery_note=destination.discovery_note,
            )

        problems: list[str] = []
        if install_root.is_symlink() or not install_root.is_dir():
            problems.append("installation root must be a real directory")
        manifest: InstallationManifest | None = None
        if not problems:
            try:
                manifest = self._load_manifest(install_root)
                self._validate_manifest(manifest, install_root, destination)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                problems.append(str(error))

        if manifest is not None and not problems:
            for relative in manifest.managed_files:
                target = self._managed_target(install_root, relative)
                if target.is_symlink():
                    problems.append(f"managed file is an unsafe symbolic link: {relative}")
                elif not target.is_file():
                    problems.append(f"managed file is missing: {relative}")
            installed_version = self._safe_installed_version(install_root, problems)
            if installed_version and installed_version != manifest.version:
                problems.append("manifest version does not match installed VERSION")
            try:
                self._validate_skill_file(install_root / "SKILL.md")
            except (OSError, ValueError) as error:
                problems.append(str(error))
        else:
            installed_version = manifest.version if manifest else None

        core_available = (install_root / "core" / "efficient_dev" / "__init__.py").is_file()
        if not core_available:
            problems.append("shared core is missing")
        return InstallationStatus(
            status="broken" if problems else "installed",
            agent=destination.agent,
            install_mode=destination.install_mode,
            install_root=str(install_root),
            version=installed_version,
            core_available=core_available,
            project_state_exists=state_exists,
            problems=tuple(dict.fromkeys(problems)),
            discovery_note=destination.discovery_note,
        )

    def update(
        self,
        agent: str,
        project_root: str | Path,
        *,
        mode: str = "workspace",
        user_home: str | Path | None = None,
    ) -> InstallResult:
        project, destination = self._resolve_destination(
            agent,
            project_root,
            mode=mode,
            user_home=user_home,
        )
        current_status = self.status(
            agent,
            project,
            mode=mode,
            user_home=user_home,
        )
        if current_status.status != "installed":
            raise ValueError(
                "Cannot update an incomplete installation: "
                + "; ".join(current_status.problems)
            )

        install_root = Path(destination.install_root)
        old_manifest = self._load_manifest(install_root)
        self._validate_version_compatibility(old_manifest.version, self.version)
        state_existed = (project / ".efficient-dev").exists()
        stage = self._temporary_sibling(install_root, "update")
        backup = self._temporary_sibling(install_root, "backup")
        try:
            new_manifest = self._build_bundle(stage, destination)
            self._copy_unmanaged_files(
                install_root,
                stage,
                old_manifest.managed_files,
                new_manifest.managed_files,
            )
            install_root.replace(backup)
            try:
                stage.replace(install_root)
            except Exception:
                backup.replace(install_root)
                raise
            self._remove_known_tree(backup, install_root.parent, "backup")
        except Exception:
            self._remove_known_tree(stage, install_root.parent, "update")
            if backup.exists() and not install_root.exists():
                backup.replace(install_root)
            raise

        if state_existed != (project / ".efficient-dev").exists():
            raise RuntimeError("Project state changed unexpectedly during update")
        return self._result(
            "updated",
            destination,
            new_manifest,
            project,
        )

    def uninstall(
        self,
        agent: str,
        project_root: str | Path,
        *,
        mode: str = "workspace",
        user_home: str | Path | None = None,
    ) -> InstallResult:
        project, destination = self._resolve_destination(
            agent,
            project_root,
            mode=mode,
            user_home=user_home,
        )
        install_root = Path(destination.install_root)
        current_status = self.status(
            agent,
            project,
            mode=mode,
            user_home=user_home,
        )
        if current_status.status != "installed":
            raise ValueError(
                "Cannot safely uninstall an incomplete installation: "
                + "; ".join(current_status.problems)
            )

        manifest = self._load_manifest(install_root)
        targets = [
            (relative, self._managed_target(install_root, relative))
            for relative in manifest.managed_files
        ]
        for relative, target in targets:
            if target.is_dir() and not target.is_symlink():
                raise ValueError(f"Managed path unexpectedly points to a directory: {relative}")
        manifest_target: Path | None = None
        for relative, target in targets:
            if relative == MANIFEST_NAME:
                manifest_target = target
                continue
            if target.exists() or target.is_symlink():
                target.unlink()
        if manifest_target is None:
            raise ValueError("Installation manifest does not manage itself")
        manifest_target.unlink()

        self._remove_empty_directories(install_root)
        remaining = self._relative_files(install_root) if install_root.exists() else ()
        return InstallResult(
            action="uninstalled",
            agent=destination.agent,
            install_mode=destination.install_mode,
            install_root=str(install_root),
            version=manifest.version,
            managed_files=manifest.managed_files,
            project_state_preserved=(project / ".efficient-dev").exists(),
            remaining_unmanaged=remaining,
            discovery_note=destination.discovery_note,
        )

    def _resolve_destination(
        self,
        agent: str,
        project_root: str | Path,
        *,
        mode: str,
        user_home: str | Path | None,
    ) -> tuple[Path, AdapterDestination]:
        project = self._validate_directory(project_root, "target project")
        home = None
        if mode != "workspace":
            home = self._validate_directory(
                Path.home() if user_home is None else user_home,
                "user home",
            )
        adapter = get_adapter(agent)
        destination = adapter.destination(project, mode=mode, user_home=home)
        base = project if mode == "workspace" else home
        assert base is not None
        install_root = self._confined_destination(base, Path(destination.install_root))
        return project, AdapterDestination(
            agent=destination.agent,
            install_mode=destination.install_mode,
            install_root=install_root,
            discovery_note=destination.discovery_note,
        )

    @staticmethod
    def _validate_directory(value: str | Path, label: str) -> Path:
        raw = Path(value)
        if raw.is_symlink():
            raise ValueError(f"{label.capitalize()} must not be a symbolic link: {raw}")
        resolved = raw.resolve()
        if not resolved.is_dir():
            raise ValueError(f"{label.capitalize()} is not an existing directory: {resolved}")
        if resolved == Path(resolved.anchor):
            raise ValueError(f"{label.capitalize()} must not be a filesystem root")
        return resolved

    @staticmethod
    def _confined_destination(base: Path, candidate: Path) -> Path:
        resolved_base = base.resolve()
        resolved_candidate = candidate.resolve(strict=False)
        try:
            relative = resolved_candidate.relative_to(resolved_base)
        except ValueError as error:
            raise ValueError("Installation destination escapes its allowed root") from error
        current = resolved_base
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError(f"Installation destination contains a symbolic link: {current}")
        return resolved_candidate

    def _bundle_files(self) -> tuple[tuple[str, Path], ...]:
        relative_paths = list(BUNDLE_ROOT_FILES + BUNDLE_EXPLICIT_FILES)
        relative_paths.extend(
            path.relative_to(self.source_root).as_posix()
            for path in (self.source_root / "core" / "efficient_dev").glob("*.py")
        )
        relative_paths.extend(
            path.relative_to(self.source_root).as_posix()
            for path in (self.source_root / "rules").glob("*.md")
        )
        result: list[tuple[str, Path]] = []
        for relative in sorted(set(relative_paths)):
            normalized = self._validate_relative_path(relative)
            source = self.source_root.joinpath(*PurePosixPath(normalized).parts)
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Required bundle file is missing or unsafe: {relative}")
            result.append((normalized, source))
        return tuple(result)

    def _build_bundle(
        self,
        destination_root: Path,
        destination: AdapterDestination,
    ) -> InstallationManifest:
        if destination_root.exists():
            raise ValueError(f"Temporary installation path already exists: {destination_root}")
        destination_root.mkdir(parents=True)
        managed: list[str] = []
        for relative, source in self._bundle_files():
            target = self._managed_target(destination_root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            managed.append(relative)
        managed.append(MANIFEST_NAME)
        manifest = InstallationManifest(
            version=self.version,
            agent=destination.agent,
            install_mode=destination.install_mode,
            managed_files=tuple(sorted(managed)),
            installed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        manifest_path = destination_root / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self._validate_skill_file(destination_root / "SKILL.md")
        return manifest

    def _load_manifest(self, install_root: Path) -> InstallationManifest:
        manifest_path = install_root / MANIFEST_NAME
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError("installation manifest is missing or unsafe")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("installation manifest must be a JSON object")
        return InstallationManifest.from_dict(data)

    def _validate_manifest(
        self,
        manifest: InstallationManifest,
        install_root: Path,
        destination: AdapterDestination,
    ) -> None:
        if manifest.agent != destination.agent:
            raise ValueError("installation manifest agent does not match the requested adapter")
        if manifest.install_mode != destination.install_mode:
            raise ValueError("installation manifest mode does not match the requested mode")
        if MANIFEST_NAME not in manifest.managed_files:
            raise ValueError("installation manifest does not manage itself")
        if len(set(manifest.managed_files)) != len(manifest.managed_files):
            raise ValueError("installation manifest contains duplicate managed paths")
        for relative in manifest.managed_files:
            self._managed_target(install_root, relative)

    def _copy_unmanaged_files(
        self,
        current_root: Path,
        stage: Path,
        old_managed: Iterable[str],
        new_managed: Iterable[str],
    ) -> None:
        old_set = set(old_managed)
        new_set = set(new_managed)
        for relative in self._relative_files(current_root):
            if relative in old_set:
                continue
            if relative in new_set:
                raise ValueError(f"Unmanaged file conflicts with the new bundle: {relative}")
            source = self._managed_target(current_root, relative)
            if source.is_symlink():
                raise ValueError(f"Unmanaged symbolic links are not preserved: {relative}")
            target = self._managed_target(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    @staticmethod
    def _validate_skill_file(path: Path) -> None:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"SKILL.md is missing or unsafe: {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("SKILL.md must start with YAML frontmatter")
        try:
            end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
        except StopIteration as error:
            raise ValueError("SKILL.md frontmatter is not closed") from error
        metadata: dict[str, str] = {}
        for line in lines[1:end]:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"\'')
        if metadata.get("name") != "efficient-dev-skill":
            raise ValueError("SKILL.md name must be efficient-dev-skill")
        if not metadata.get("description"):
            raise ValueError("SKILL.md description is required")

    @staticmethod
    def _read_version(path: Path) -> str:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"VERSION is missing or unsafe: {path}")
        version = path.read_text(encoding="utf-8").strip()
        parts = version.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError("VERSION must use numeric MAJOR.MINOR.PATCH format")
        return version

    @staticmethod
    def _validate_version_compatibility(installed: str, available: str) -> None:
        if installed.split(".", 1)[0] != available.split(".", 1)[0]:
            raise ValueError(
                f"Refusing incompatible major-version update: {installed} -> {available}"
            )

    @staticmethod
    def _validate_relative_path(value: str) -> str:
        portable_value = value.replace("\\", "/")
        path = PurePosixPath(portable_value)
        windows_path = PureWindowsPath(portable_value)
        if (
            "\x00" in value
            or path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ":" in portable_value
            or not path.parts
            or ".." in path.parts
            or "." in path.parts
        ):
            raise ValueError(f"Unsafe managed path: {value!r}")
        normalized = path.as_posix()
        if normalized != portable_value:
            raise ValueError(f"Managed path is not normalized: {value!r}")
        return normalized

    @classmethod
    def _managed_target(cls, install_root: Path, relative: str) -> Path:
        normalized = cls._validate_relative_path(relative)
        root = install_root.resolve(strict=False)
        target = root.joinpath(*PurePosixPath(normalized).parts)
        current = root
        for part in PurePosixPath(normalized).parts:
            current /= part
            if current.is_symlink():
                raise ValueError(f"Managed path contains a symbolic link: {relative!r}")
        resolved_target = target.resolve(strict=False)
        try:
            resolved_target.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Managed path escapes installation root: {relative!r}") from error
        return target

    @staticmethod
    def _safe_installed_version(install_root: Path, problems: list[str]) -> str | None:
        try:
            return SkillInstaller._read_version(install_root / "VERSION")
        except (OSError, ValueError) as error:
            problems.append(str(error))
            return None

    @staticmethod
    def _temporary_sibling(install_root: Path, purpose: str) -> Path:
        return install_root.parent / f".{install_root.name}.{purpose}-{uuid.uuid4().hex}"

    @staticmethod
    def _remove_known_tree(path: Path, parent: Path, purpose: str) -> None:
        if not path.exists() and not path.is_symlink():
            return
        if path.parent != parent or not path.name.startswith(f".efficient-dev.{purpose}-"):
            raise RuntimeError(f"Refusing to remove unexpected temporary path: {path}")
        if path.is_symlink():
            path.unlink()
        else:
            shutil.rmtree(path)

    @staticmethod
    def _remove_empty_directories(install_root: Path) -> None:
        if not install_root.exists():
            return
        directories = sorted(
            (path for path in install_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            install_root.rmdir()
        except OSError:
            pass

    @classmethod
    def _relative_files(cls, root: Path) -> tuple[str, ...]:
        if not root.exists():
            return ()
        files: list[str] = []
        for path in root.rglob("*"):
            if path.is_symlink():
                relative = path.relative_to(root).as_posix()
                files.append(relative)
            elif path.is_file():
                files.append(path.relative_to(root).as_posix())
        return tuple(sorted(files))

    @staticmethod
    def _result(
        action: str,
        destination: AdapterDestination,
        manifest: InstallationManifest,
        project: Path,
    ) -> InstallResult:
        return InstallResult(
            action=action,
            agent=destination.agent,
            install_mode=destination.install_mode,
            install_root=str(destination.install_root),
            version=manifest.version,
            managed_files=manifest.managed_files,
            project_state_preserved=(project / ".efficient-dev").exists(),
            remaining_unmanaged=(),
            discovery_note=destination.discovery_note,
        )
