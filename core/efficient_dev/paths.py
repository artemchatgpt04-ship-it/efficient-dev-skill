"""Safe project-relative path handling shared by local-state components."""

from __future__ import annotations

from pathlib import Path


def resolve_project_file(
    project_root: str | Path, file_path: str | Path
) -> tuple[str, Path]:
    """Return a portable relative path and resolved path confined to the project."""

    root = Path(project_root).resolve()
    supplied = Path(file_path)
    candidate = supplied if supplied.is_absolute() else root / supplied
    if candidate.is_symlink():
        raise ValueError(f"Symbolic links are not eligible project files: {file_path}")
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"File is outside the project root: {file_path}") from error
    if relative == Path("."):
        raise ValueError("A project file path is required")
    return relative.as_posix(), resolved


def resolve_runtime_path(
    project_root: str | Path,
    supplied_path: str | Path | None,
    *,
    default_relative: str | Path,
) -> Path:
    """Resolve a state file and confine it to the project's `.efficient-dev`."""

    root = Path(project_root).resolve()
    runtime_root = root / ".efficient-dev"
    if runtime_root.is_symlink():
        raise ValueError("The .efficient-dev runtime directory must not be a symbolic link")
    candidate = (
        runtime_root / default_relative
        if supplied_path is None
        else Path(supplied_path)
        if Path(supplied_path).is_absolute()
        else root / supplied_path
    )
    resolved_runtime = runtime_root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_runtime)
    except ValueError as error:
        raise ValueError("Runtime state must stay inside the project's .efficient-dev") from error
    return resolved_candidate
