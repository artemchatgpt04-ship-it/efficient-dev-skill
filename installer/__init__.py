"""Safe installation lifecycle for Efficient Development Skill."""

from .adapters import AdapterDestination, AntigravityAdapter, CodexAdapter, get_adapter
from .service import InstallResult, InstallationStatus, SkillInstaller

__all__ = [
    "AdapterDestination",
    "AntigravityAdapter",
    "CodexAdapter",
    "InstallResult",
    "InstallationStatus",
    "SkillInstaller",
    "get_adapter",
]
