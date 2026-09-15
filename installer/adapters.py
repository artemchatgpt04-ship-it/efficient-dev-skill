"""Agent-specific discovery paths without duplicating core behavior."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


SKILL_DIRECTORY_NAME = "efficient-dev"


@dataclass(frozen=True)
class AdapterDestination:
    agent: str
    install_mode: str
    install_root: PurePath
    discovery_note: str


class CodexAdapter:
    """Resolve current Codex discovery paths plus an explicit legacy mode."""

    name = "codex"
    modes = ("workspace", "global", "legacy-global")

    def destination(
        self,
        project_root: PurePath,
        *,
        mode: str = "workspace",
        user_home: PurePath | None = None,
    ) -> AdapterDestination:
        self._validate_mode(mode)
        if mode == "workspace":
            root = project_root / ".agents" / "skills" / SKILL_DIRECTORY_NAME
            note = "Codex discovers repository skills automatically; restart if it does not appear."
        else:
            if user_home is None:
                raise ValueError("A user home is required for a global Codex installation")
            if mode == "global":
                root = user_home / ".agents" / "skills" / SKILL_DIRECTORY_NAME
                note = "Codex discovers user skills automatically; restart if it does not appear."
            else:
                root = user_home / ".codex" / "skills" / SKILL_DIRECTORY_NAME
                note = (
                    "Legacy Codex layout selected explicitly; prefer global mode for new installs "
                    "and restart Codex if discovery does not refresh."
                )
        return AdapterDestination(self.name, mode, root, note)

    def _validate_mode(self, mode: str) -> None:
        if mode not in self.modes:
            raise ValueError(f"Unsupported Codex install mode: {mode!r}")


class AntigravityAdapter:
    """Resolve Antigravity workspace, global, and CLI-global skill paths."""

    name = "antigravity"
    modes = ("workspace", "global", "cli-global")

    def destination(
        self,
        project_root: PurePath,
        *,
        mode: str = "workspace",
        user_home: PurePath | None = None,
    ) -> AdapterDestination:
        self._validate_mode(mode)
        if mode == "workspace":
            root = project_root / ".agents" / "skills" / SKILL_DIRECTORY_NAME
            note = "Antigravity discovers workspace skills from .agents/skills."
        else:
            if user_home is None:
                raise ValueError("A user home is required for a global Antigravity installation")
            if mode == "global":
                root = user_home / ".gemini" / "config" / "skills" / SKILL_DIRECTORY_NAME
                note = "Antigravity discovers global skills from ~/.gemini/config/skills."
            else:
                root = (
                    user_home
                    / ".gemini"
                    / "antigravity-cli"
                    / "skills"
                    / SKILL_DIRECTORY_NAME
                )
                note = "Antigravity CLI-specific global layout selected explicitly."
        return AdapterDestination(self.name, mode, root, note)

    def _validate_mode(self, mode: str) -> None:
        if mode not in self.modes:
            raise ValueError(f"Unsupported Antigravity install mode: {mode!r}")


def get_adapter(agent: str) -> CodexAdapter | AntigravityAdapter:
    normalized = agent.strip().lower()
    if normalized == "codex":
        return CodexAdapter()
    if normalized == "antigravity":
        return AntigravityAdapter()
    raise ValueError(f"Unsupported agent: {agent!r}")
