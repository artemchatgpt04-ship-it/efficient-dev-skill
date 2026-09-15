"""Command-line lifecycle for Efficient Development Skill installations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .service import InstallResult, InstallationStatus, SkillInstaller


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="efficient-dev-installer",
        description="Install and manage a bounded Efficient Development Skill bundle.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Skill source checkout (default: the checkout containing this installer)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "status", "update", "uninstall"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("agent", choices=("codex", "antigravity"))
        command_parser.add_argument("project", type=Path, help="Existing target project")
        command_parser.add_argument(
            "--mode",
            default="workspace",
            help="workspace (default), global, or an adapter-specific explicit mode",
        )
        command_parser.add_argument(
            "--home",
            type=Path,
            help="Existing user home used only by explicit non-workspace modes",
        )
        command_parser.add_argument("--json", action="store_true", help="Print JSON")
    return parser


def _print_result(result: InstallResult | InstallationStatus, *, as_json: bool) -> None:
    data = asdict(result)
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        return

    if isinstance(result, InstallationStatus):
        print(f"status: {result.status}")
        print(f"agent: {result.agent}")
        print(f"mode: {result.install_mode}")
        print(f"location: {result.install_root}")
        print(f"version: {result.version or '-'}")
        print(f"shared core: {'available' if result.core_available else 'unavailable'}")
        print(
            "project state: "
            + ("present and untouched" if result.project_state_exists else "not present")
        )
        for problem in result.problems:
            print(f"problem: {problem}")
    else:
        print(f"action: {result.action}")
        print(f"agent: {result.agent}")
        print(f"mode: {result.install_mode}")
        print(f"location: {result.install_root}")
        print(f"version: {result.version}")
        print(f"managed files: {len(result.managed_files)}")
        print(
            "project state: "
            + ("present and untouched" if result.project_state_preserved else "not present")
        )
        if result.remaining_unmanaged:
            print("remaining unmanaged files: " + ", ".join(result.remaining_unmanaged))
    print(f"discovery: {result.discovery_note}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        installer = SkillInstaller(args.source)
        operation = getattr(installer, args.command)
        result = operation(
            args.agent,
            args.project,
            mode=args.mode,
            user_home=args.home,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    _print_result(result, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
