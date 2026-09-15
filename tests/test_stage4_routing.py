from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "polyglot_project"
CLI = PROJECT_ROOT / "scripts" / "efficient_dev.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.efficient_dev import (
    ChangeTracker,
    ContextCompressor,
    InstructionRouter,
    ProjectMapBuilder,
    TaskRouter,
    TestRouter,
)


class ProjectCopyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary_directory.name) / "fixture"
        shutil.copytree(FIXTURE, self.project)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()


class InstructionRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_map = ProjectMapBuilder().build(FIXTURE)

    def _route(self, task: str):
        task_route = TaskRouter(self.project_map).route(task)
        return InstructionRouter(self.project_map).route(task, task_route=task_route)

    def test_frontend_task_loads_only_relevant_groups(self) -> None:
        result = self._route("Fix React component history rendering")

        self.assertIn("base", result.selected_names)
        self.assertIn("frontend", result.selected_names)
        self.assertIn("testing", result.selected_names)
        self.assertNotIn("backend", result.selected_names)
        self.assertNotIn("database", result.selected_names)

    def test_security_task_selects_security_rules(self) -> None:
        result = self._route("Audit authentication token permissions")

        self.assertIn("base", result.selected_names)
        self.assertIn("security", result.selected_names)

    def test_ambiguous_task_expands_conservatively(self) -> None:
        result = self._route("Resolve quasar entropy drift")

        self.assertTrue(result.safe_expansion)
        self.assertEqual(("base", "testing", "security"), result.selected_names)

    def test_base_rules_are_always_selected(self) -> None:
        tasks = (
            "Update README documentation",
            "Commit the current branch",
            "Change database schema",
        )

        for task in tasks:
            with self.subTest(task=task):
                self.assertEqual("base", self._route(task).selected_names[0])

    def test_instruction_routing_is_deterministic(self) -> None:
        first = self._route("Fix React component history rendering").to_dict()
        second = self._route("Fix React component history rendering").to_dict()

        self.assertEqual(first, second)


class TestRouterTests(ProjectCopyTestCase):
    def _baseline(self) -> ChangeTracker:
        tracker = ChangeTracker(self.project)
        tracker.scan(update_baseline=True)
        return tracker

    def _plan(self, tracker: ChangeTracker, task: str):
        project_map = ProjectMapBuilder().build(self.project)
        task_route = TaskRouter(project_map).route(task)
        return TestRouter(project_map).route(
            tracker.scan(),
            task_route=task_route,
        )

    def test_local_source_change_selects_linked_test_only(self) -> None:
        tracker = self._baseline()
        changed = self.project / "src" / "history" / "render_history.ts"
        changed.write_text("export const changed = true;\n", encoding="utf-8")

        plan = self._plan(tracker, "Fix history rendering")
        selected = {test.path for test in plan.selected_tests}

        self.assertFalse(plan.full_suite_recommended)
        self.assertEqual({"tests/history/render_history.test.ts"}, selected)
        self.assertEqual(("tests/history",), plan.area_test_directories)
        self.assertNotIn("python/test_report.py", selected)
        self.assertNotIn("go/cmd/server/main_test.go", selected)

    def test_shared_module_recommends_full_suite(self) -> None:
        source = self.project / "core" / "shared.py"
        test = self.project / "tests" / "core" / "test_shared.py"
        source.parent.mkdir(parents=True)
        test.parent.mkdir(parents=True)
        source.write_text("VALUE = 1\n", encoding="utf-8")
        test.write_text("def test_shared():\n    assert True\n", encoding="utf-8")
        tracker = self._baseline()
        source.write_text("VALUE = 2\n", encoding="utf-8")

        plan = self._plan(tracker, "Change shared core value")

        self.assertTrue(plan.full_suite_recommended)
        self.assertEqual(
            set(ProjectMapBuilder().build(self.project).tests),
            {test.path for test in plan.selected_tests},
        )

    def test_configuration_change_recommends_full_suite(self) -> None:
        tracker = self._baseline()
        config = self.project / "package.json"
        config.write_text('{"scripts":{"test":"node test"}}\n', encoding="utf-8")

        plan = self._plan(tracker, "Update package configuration")

        self.assertTrue(plan.full_suite_recommended)
        self.assertTrue(any("configuration" in reason for reason in plan.reasons))

    def test_unknown_test_relationship_uses_safer_full_suite(self) -> None:
        tracker = self._baseline()
        chart = self.project / "src" / "charts" / "portfolio_chart.ts"
        chart.write_text("export const chart = 2;\n", encoding="utf-8")

        plan = self._plan(tracker, "Update portfolio chart")

        self.assertTrue(plan.full_suite_recommended)
        self.assertTrue(any("no reliable mapped test" in reason for reason in plan.reasons))

    def test_deleted_source_recommends_full_suite(self) -> None:
        tracker = self._baseline()
        (self.project / "python" / "report.py").unlink()

        plan = self._plan(tracker, "Remove obsolete report")

        self.assertTrue(plan.full_suite_recommended)
        self.assertTrue(any("deleted files" in reason for reason in plan.reasons))

    def test_same_change_state_produces_same_test_plan(self) -> None:
        tracker = self._baseline()
        changed = self.project / "src" / "history" / "render_history.ts"
        changed.write_text("export const changed = true;\n", encoding="utf-8")

        first = self._plan(tracker, "Fix history rendering").to_dict()
        second = self._plan(tracker, "Fix history rendering").to_dict()

        self.assertEqual(first, second)

    def test_no_changes_selects_no_tests(self) -> None:
        tracker = self._baseline()

        plan = self._plan(tracker, "Fix history rendering")

        self.assertFalse(plan.full_suite_recommended)
        self.assertFalse(plan.selected_tests)


class ContextCompressorTests(ProjectCopyTestCase):
    def test_duplicates_are_removed_and_critical_facts_are_preserved(self) -> None:
        result = ContextCompressor(self.project).update(
            {
                "task": "Fix history rendering",
                "scope": ["src/history", "src/history"],
                "files_inspected": ["src/history/render_history.ts"],
                "files_changed": ["src/history/render_history.ts"],
                "key_findings": ["Cache is stale", "Cache is stale"],
                "decisions": ["Use the mapped test"],
                "tests_run": ["render_history.test.ts passed"],
                "open_issues": ["Browser behavior is unverified"],
                "next_action": "Run the related UI check",
            }
        )

        self.assertEqual(("src/history",), result.state.scope)
        self.assertEqual(("Cache is stale",), result.state.key_findings)
        self.assertEqual(2, result.metrics["deduplicated_items"])
        self.assertTrue(result.state.files_changed)
        self.assertTrue(result.state.decisions)
        self.assertTrue(result.state.tests_run)
        self.assertTrue(result.state.open_issues)

    def test_new_fact_replaces_old_value_without_growing_history(self) -> None:
        compressor = ContextCompressor(self.project)
        compressor.update(
            {
                "task": "Old task",
                "files_changed": ["python/report.py"],
                "decisions": ["Old decision"],
            }
        )

        result = compressor.update(
            {
                "task": "Current task",
                "decisions": ["Current decision"],
            }
        )

        self.assertEqual("Current task", result.state.task)
        self.assertEqual(("Current decision",), result.state.decisions)
        self.assertEqual(("python/report.py",), result.state.files_changed)

    def test_large_log_like_input_is_bounded(self) -> None:
        huge = "command output " * 10_000

        result = ContextCompressor(self.project).update(
            {
                "key_findings": [huge],
                "tests_run": [huge],
                "open_issues": [f"issue {index}" for index in range(100)],
                "next_action": huge,
            }
        )

        self.assertLessEqual(len(result.state.key_findings[0]), 500)
        self.assertLessEqual(len(result.state.tests_run[0]), 500)
        self.assertLessEqual(len(result.state.next_action), 500)
        self.assertEqual(50, len(result.state.open_issues))
        self.assertLess(result.metrics["context_size"], 4_000)

    def test_same_facts_produce_same_session_state(self) -> None:
        second_project = Path(self.temporary_directory.name) / "second"
        shutil.copytree(FIXTURE, second_project)
        facts = {
            "task": "Fix history rendering",
            "scope": ["src/history"],
            "files_changed": ["src/history/render_history.ts"],
            "decisions": ["Run linked tests"],
        }

        first = ContextCompressor(self.project).update(facts).to_dict()
        second = ContextCompressor(second_project).update(facts).to_dict()

        self.assertEqual(first, second)

    def test_session_storage_is_confined_to_runtime_directory(self) -> None:
        outside = Path(self.temporary_directory.name) / "outside-session.json"

        with self.assertRaises(ValueError):
            ContextCompressor(self.project, state_path=outside)


class Stage4CliTests(ProjectCopyTestCase):
    def test_new_commands_cover_instruction_test_and_context_flow(self) -> None:
        instructions = self._run_cli(
            "instructions",
            "Fix React component history rendering",
            "--root",
            str(self.project),
            "--json",
        )
        instruction_data = json.loads(instructions.stdout)
        selected = {group["name"] for group in instruction_data["selected"]}
        self.assertTrue({"base", "frontend", "testing"} <= selected)

        self._run_cli("changes", "--root", str(self.project), "--update", "--json")
        changed = self.project / "src" / "history" / "render_history.ts"
        changed.write_text("export const changed = true;\n", encoding="utf-8")
        tests = self._run_cli(
            "tests",
            "--root",
            str(self.project),
            "--task",
            "Fix history rendering",
            "--json",
        )
        test_data = json.loads(tests.stdout)
        self.assertFalse(test_data["full_suite_recommended"])
        self.assertEqual(
            ["tests/history/render_history.test.ts"],
            [item["path"] for item in test_data["selected_tests"]],
        )

        update = self._run_cli(
            "context",
            "update",
            "--root",
            str(self.project),
            "--task",
            "Fix history rendering",
            "--changed",
            "src/history/render_history.ts",
            "--decision",
            "Run linked test first",
            "--json",
        )
        update_data = json.loads(update.stdout)
        self.assertEqual("Fix history rendering", update_data["state"]["task"])

        shown = self._run_cli(
            "context", "show", "--root", str(self.project), "--json"
        )
        self.assertEqual(update_data["state"], json.loads(shown.stdout)["state"])

    @staticmethod
    def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-B", str(CLI), *arguments],
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
