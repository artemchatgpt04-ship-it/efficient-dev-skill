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

from core.efficient_dev import ProjectMap, ProjectMapBuilder, SmartReader, TaskRouter


class ProjectMapTests(unittest.TestCase):
    def test_map_classifies_supported_languages_and_key_files(self) -> None:
        project_map = ProjectMapBuilder().build(FIXTURE)
        languages = {item.language for item in project_map.files if item.language}

        self.assertTrue({"typescript", "python", "java", "go", "rust"} <= languages)
        self.assertIn("package.json", project_map.configuration)
        self.assertIn("README.md", project_map.documentation)
        self.assertIn("go/cmd/server/main.go", project_map.entry_points)
        self.assertEqual(12, project_map.metrics["mapped_files"])

    def test_map_links_sources_to_matching_tests(self) -> None:
        project_map = ProjectMapBuilder().build(FIXTURE)
        links = {(item.source, item.test) for item in project_map.test_relationships}

        self.assertIn(
            ("src/history/render_history.ts", "tests/history/render_history.test.ts"),
            links,
        )
        self.assertIn(("python/report.py", "python/test_report.py"), links)
        self.assertIn(("go/cmd/server/main.go", "go/cmd/server/main_test.go"), links)

    def test_noise_and_binary_files_do_not_pollute_map(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "fixture"
            shutil.copytree(FIXTURE, repository)
            noisy_files = (
                repository / "node_modules" / "dependency.js",
                repository / ".git" / "objects" / "object",
                repository / "build" / "bundle.js",
                repository / "coverage" / "report.json",
            )
            for noisy_file in noisy_files:
                noisy_file.parent.mkdir(parents=True, exist_ok=True)
                noisy_file.write_text("noise", encoding="utf-8")
            (repository / "image.png").write_bytes(b"\x89PNG\x00binary")

            project_map = ProjectMapBuilder().build(repository)
            mapped_paths = {item.path for item in project_map.files}

            self.assertFalse(any("node_modules" in path for path in mapped_paths))
            self.assertFalse(any(path.startswith(".git/") for path in mapped_paths))
            self.assertFalse(any(path.startswith("build/") for path in mapped_paths))
            self.assertFalse(any(path.startswith("coverage/") for path in mapped_paths))
            self.assertNotIn("image.png", mapped_paths)
            self.assertGreaterEqual(project_map.metrics["pruned_directories"], 4)

    def test_map_round_trip_and_output_are_deterministic(self) -> None:
        first = ProjectMapBuilder().build(FIXTURE)
        second = ProjectMapBuilder().build(FIXTURE)
        self.assertEqual(first.to_json(), second.to_json())

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "project-map.json"
            first.save(destination)
            loaded = ProjectMap.load(destination)
            self.assertEqual(first.to_dict(), loaded.to_dict())

    def test_extra_exclusion_patterns_extend_defaults(self) -> None:
        project_map = ProjectMapBuilder(extra_excludes=["python"]).build(FIXTURE)

        self.assertFalse(any(item.path.startswith("python/") for item in project_map.files))
        self.assertIn("python", project_map.exclusions["extra_patterns"])


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_map = ProjectMapBuilder().build(FIXTURE)

    def test_local_task_keeps_scope_focused_and_includes_related_test(self) -> None:
        result = TaskRouter(self.project_map).route("Fix history rendering")
        candidates = {item.path for item in result.candidate_files}

        self.assertEqual("focused", result.scope_mode)
        self.assertIn("src/history/render_history.ts", candidates)
        self.assertIn("tests/history/render_history.test.ts", candidates)
        self.assertLess(result.metrics["candidate_files"], result.metrics["mapped_files"])
        self.assertLess(result.metrics["scope_ratio"], 1.0)

    def test_unknown_task_requests_broader_search_without_false_confidence(self) -> None:
        result = TaskRouter(self.project_map).route("Resolve quasar entropy drift")

        self.assertEqual("low", result.confidence)
        self.assertEqual("broaden-search", result.scope_mode)
        self.assertTrue(result.requires_broader_search)
        self.assertEqual((".",), result.search_roots)
        self.assertFalse(result.high_probability)
        self.assertFalse(result.medium_probability)

    def test_explicit_aliases_bridge_task_and_repository_vocabulary(self) -> None:
        router = TaskRouter(
            self.project_map,
            aliases={"истории": ["history"], "отображение": ["render"]},
        )
        result = router.route("Исправить отображение истории")

        self.assertIn(
            "src/history/render_history.ts",
            {item.path for item in result.candidate_files},
        )

    def test_route_and_plan_are_deterministic_and_allow_expansion(self) -> None:
        router = TaskRouter(self.project_map)
        first_route = router.route("Fix history rendering")
        second_route = router.route("Fix history rendering")
        self.assertEqual(first_route.to_dict(), second_route.to_dict())

        first_plan = SmartReader.plan_route(first_route)
        second_plan = SmartReader.plan_route(second_route)
        self.assertEqual(first_plan.to_dict(), second_plan.to_dict())
        self.assertTrue(first_plan.cache_policy["check_before_read"])
        self.assertTrue(first_plan.expansion["allowed"])
        self.assertTrue(
            any("import" in trigger for trigger in first_plan.expansion["triggers"])
        )
        self.assertTrue(
            any("insufficient" in trigger for trigger in first_plan.expansion["triggers"])
        )


class CliTests(unittest.TestCase):
    def test_map_route_and_plan_commands_on_fixture(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        with tempfile.TemporaryDirectory() as temporary_directory:
            map_path = Path(temporary_directory) / "project-map.json"
            map_result = self._run_cli(
                "map",
                str(FIXTURE),
                "--output",
                str(map_path),
                "--json",
                environment=environment,
            )
            map_data = json.loads(map_result.stdout)
            self.assertTrue(map_path.is_file())
            self.assertEqual(12, map_data["metrics"]["mapped_files"])

            route_result = self._run_cli(
                "route",
                "Fix history rendering",
                "--map",
                str(map_path),
                "--json",
                environment=environment,
            )
            route_data = json.loads(route_result.stdout)
            self.assertEqual("focused", route_data["scope_mode"])

            plan_result = self._run_cli(
                "plan",
                "Fix history rendering",
                "--map",
                str(map_path),
                "--json",
                environment=environment,
            )
            plan_data = json.loads(plan_result.stdout)
            self.assertTrue(plan_data["expansion"]["allowed"])

    @staticmethod
    def _run_cli(*arguments: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
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
