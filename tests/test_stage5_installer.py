from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_CLI = PROJECT_ROOT / "installer" / "efficient_dev_installer.py"
SOURCE_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from installer.adapters import AntigravityAdapter, CodexAdapter
from installer.service import MANIFEST_NAME, SkillInstaller


class InstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.sandbox = Path(self.temporary_directory.name)
        self.project = self.sandbox / "project"
        self.home = self.sandbox / "home"
        self.project.mkdir()
        self.home.mkdir()
        self.installer = SkillInstaller(PROJECT_ROOT)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def root_for(self, agent: str = "codex") -> Path:
        del agent
        return self.project / ".agents" / "skills" / "efficient-dev"


class AdapterPathTests(unittest.TestCase):
    def test_codex_paths_are_exact_on_posix_and_windows(self) -> None:
        adapter = CodexAdapter()
        posix = adapter.destination(PurePosixPath("/work/repo"))
        windows = adapter.destination(PureWindowsPath("C:/work/repo"))
        global_posix = adapter.destination(
            PurePosixPath("/work/repo"),
            mode="global",
            user_home=PurePosixPath("/home/dev"),
        )

        self.assertEqual("/work/repo/.agents/skills/efficient-dev", str(posix.install_root))
        self.assertEqual(
            "C:\\work\\repo\\.agents\\skills\\efficient-dev",
            str(windows.install_root),
        )
        self.assertEqual("/home/dev/.agents/skills/efficient-dev", str(global_posix.install_root))

    def test_antigravity_paths_cover_workspace_ide_and_cli(self) -> None:
        adapter = AntigravityAdapter()
        project = PurePosixPath("/work/repo")
        home = PurePosixPath("/home/dev")

        self.assertEqual(
            "/work/repo/.agents/skills/efficient-dev",
            str(adapter.destination(project).install_root),
        )
        self.assertEqual(
            "/home/dev/.gemini/config/skills/efficient-dev",
            str(adapter.destination(project, mode="global", user_home=home).install_root),
        )
        self.assertEqual(
            "/home/dev/.gemini/antigravity-cli/skills/efficient-dev",
            str(
                adapter.destination(project, mode="cli-global", user_home=home).install_root
            ),
        )


class LifecycleTests(InstallerTestCase):
    def test_codex_workspace_install_has_bounded_bundle_and_manifest(self) -> None:
        result = self.installer.install("codex", self.project)
        root = self.root_for()
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))

        self.assertEqual("installed", result.action)
        self.assertEqual(SOURCE_VERSION, result.version)
        self.assertEqual(SOURCE_VERSION, (root / "VERSION").read_text(encoding="utf-8").strip())
        self.assertTrue((root / "SKILL.md").is_file())
        self.assertTrue((root / "core" / "efficient_dev" / "project_map.py").is_file())
        self.assertTrue((root / "rules" / "base.md").is_file())
        self.assertTrue((root / "scripts" / "efficient_dev.py").is_file())
        self.assertFalse((root / "tests").exists())
        self.assertFalse((root / "benchmarks").exists())
        self.assertFalse((root / "installer").exists())
        self.assertFalse((root / "adapters").exists())
        self.assertFalse((root / "docs" / "MVP_EFFICIENCY_REPORT.md").exists())
        self.assertFalse((root / ".git").exists())
        self.assertEqual("codex", manifest["agent"])
        self.assertEqual("workspace", manifest["install_mode"])
        self.assertEqual(SOURCE_VERSION, manifest["version"])
        self.assertIn(MANIFEST_NAME, manifest["managed_files"])
        self.assertTrue(manifest["installed_at"].endswith("Z"))

    def test_antigravity_workspace_install_reports_shared_core(self) -> None:
        self.installer.install("antigravity", self.project)
        status = self.installer.status("antigravity", self.project)

        self.assertEqual("installed", status.status)
        self.assertTrue(status.core_available)
        self.assertEqual("antigravity", status.agent)

    def test_global_install_is_explicit_and_uses_home(self) -> None:
        result = self.installer.install(
            "codex", self.project, mode="global", user_home=self.home
        )

        self.assertEqual(
            str((self.home / ".agents" / "skills" / "efficient-dev").resolve()),
            result.install_root,
        )
        self.assertFalse(self.root_for().exists())

    def test_existing_destination_is_never_overwritten(self) -> None:
        root = self.root_for()
        root.mkdir(parents=True)
        marker = root / "user-file.txt"
        marker.write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "already exists"):
            self.installer.install("codex", self.project)

        self.assertEqual("keep", marker.read_text(encoding="utf-8"))

    def test_status_distinguishes_missing_installed_and_broken(self) -> None:
        self.assertEqual("missing", self.installer.status("codex", self.project).status)
        self.installer.install("codex", self.project)
        self.assertEqual("installed", self.installer.status("codex", self.project).status)

        (self.root_for() / "core" / "efficient_dev" / "project_map.py").unlink()
        status = self.installer.status("codex", self.project)

        self.assertEqual("broken", status.status)
        self.assertTrue(any("project_map.py" in problem for problem in status.problems))

    def test_update_restores_managed_files_and_preserves_unmanaged_and_state(self) -> None:
        state = self.project / ".efficient-dev" / "state" / "session.json"
        state.parent.mkdir(parents=True)
        state.write_text('{"task": "keep"}\n', encoding="utf-8")
        self.installer.install("codex", self.project)
        root = self.root_for()
        managed = root / "rules" / "base.md"
        original = (PROJECT_ROOT / "rules" / "base.md").read_text(encoding="utf-8")
        managed.write_text("locally changed", encoding="utf-8")
        custom = root / "custom" / "notes.md"
        custom.parent.mkdir()
        custom.write_text("keep me", encoding="utf-8")

        result = self.installer.update("codex", self.project)

        self.assertEqual("updated", result.action)
        self.assertEqual(original, managed.read_text(encoding="utf-8"))
        self.assertEqual("keep me", custom.read_text(encoding="utf-8"))
        self.assertEqual('{"task": "keep"}\n', state.read_text(encoding="utf-8"))
        self.assertTrue(result.project_state_preserved)

    def test_uninstall_removes_only_managed_files_and_preserves_state(self) -> None:
        state = self.project / ".efficient-dev" / "project-map.json"
        state.parent.mkdir()
        state.write_text("{}\n", encoding="utf-8")
        self.installer.install("codex", self.project)
        root = self.root_for()
        custom = root / "custom.txt"
        custom.write_text("unmanaged", encoding="utf-8")

        result = self.installer.uninstall("codex", self.project)

        self.assertEqual("uninstalled", result.action)
        self.assertEqual(("custom.txt",), result.remaining_unmanaged)
        self.assertEqual("unmanaged", custom.read_text(encoding="utf-8"))
        self.assertEqual("{}\n", state.read_text(encoding="utf-8"))
        self.assertFalse((root / MANIFEST_NAME).exists())

    def test_uninstall_of_clean_install_removes_skill_directory(self) -> None:
        self.installer.install("antigravity", self.project)
        root = self.root_for("antigravity")

        self.installer.uninstall("antigravity", self.project)

        self.assertFalse(root.exists())

    def test_manifest_traversal_is_rejected_without_touching_outside_file(self) -> None:
        self.installer.install("codex", self.project)
        root = self.root_for()
        outside = root.parent / "outside.txt"
        outside.write_text("safe", encoding="utf-8")
        manifest_path = root / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["managed_files"].append("../outside.txt")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        status = self.installer.status("codex", self.project)
        with self.assertRaisesRegex(ValueError, "Cannot safely uninstall"):
            self.installer.uninstall("codex", self.project)

        self.assertEqual("broken", status.status)
        self.assertEqual("safe", outside.read_text(encoding="utf-8"))

    def test_manifest_duplicate_and_wrong_agent_fail_closed(self) -> None:
        self.installer.install("codex", self.project)
        manifest_path = self.root_for() / MANIFEST_NAME
        original = json.loads(manifest_path.read_text(encoding="utf-8"))

        duplicate = dict(original)
        duplicate["managed_files"] = original["managed_files"] + ["SKILL.md"]
        manifest_path.write_text(json.dumps(duplicate), encoding="utf-8")
        self.assertEqual("broken", self.installer.status("codex", self.project).status)

        wrong_agent = dict(original)
        wrong_agent["agent"] = "antigravity"
        manifest_path.write_text(json.dumps(wrong_agent), encoding="utf-8")
        self.assertEqual("broken", self.installer.status("codex", self.project).status)

    def test_managed_symbolic_link_fails_closed(self) -> None:
        self.installer.install("codex", self.project)
        root = self.root_for()
        managed = root / "rules" / "base.md"
        other = root / "rules" / "testing.md"
        managed.unlink()
        try:
            os.symlink(other, managed)
        except OSError as error:
            self.skipTest(f"symbolic links are unavailable: {error}")

        self.assertEqual("broken", self.installer.status("codex", self.project).status)
        with self.assertRaisesRegex(ValueError, "Cannot safely uninstall"):
            self.installer.uninstall("codex", self.project)
        self.assertTrue(other.is_file())

    def test_wrong_target_and_unsupported_mode_are_rejected(self) -> None:
        missing = self.sandbox / "missing"
        with self.assertRaisesRegex(ValueError, "not an existing directory"):
            self.installer.install("codex", missing)
        with self.assertRaisesRegex(ValueError, "Unsupported Codex install mode"):
            self.installer.install("codex", self.project, mode="cli-global", user_home=self.home)

    def test_filesystem_root_is_rejected(self) -> None:
        filesystem_root = Path(self.project.anchor)
        with self.assertRaisesRegex(ValueError, "filesystem root"):
            self.installer.status("codex", filesystem_root)

    def test_major_version_compatibility_rule(self) -> None:
        self.assertEqual(3, len(SOURCE_VERSION.split(".")))
        self.assertTrue(all(part.isdigit() for part in SOURCE_VERSION.split(".")))
        SkillInstaller._validate_version_compatibility("0.1.0", "0.9.4")
        with self.assertRaisesRegex(ValueError, "incompatible major-version"):
            SkillInstaller._validate_version_compatibility("0.9.4", "1.0.0")

    def test_windows_drive_and_parent_managed_paths_are_rejected(self) -> None:
        for unsafe in (
            "../outside.txt",
            "..\\outside.txt",
            "C:/outside.txt",
            "SKILL.md:alternate-stream",
        ):
            with self.subTest(path=unsafe):
                with self.assertRaisesRegex(ValueError, "Unsafe managed path"):
                    SkillInstaller._validate_relative_path(unsafe)

    def test_cli_status_outputs_machine_readable_metadata(self) -> None:
        self.installer.install("codex", self.project)
        completed = subprocess.run(
            [
                sys.executable,
                str(INSTALLER_CLI),
                "status",
                "codex",
                str(self.project),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("installed", payload["status"])
        self.assertEqual(SOURCE_VERSION, payload["version"])
        self.assertTrue(payload["core_available"])

    def test_installed_core_cli_does_not_leave_bundle_bytecode(self) -> None:
        self.installer.install("codex", self.project)
        root = self.root_for()
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "efficient_dev.py"),
                "map",
                str(self.project),
                "--json",
            ],
            cwd=self.project,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertFalse(any(root.rglob("__pycache__")))
        self.installer.uninstall("codex", self.project)
        self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
