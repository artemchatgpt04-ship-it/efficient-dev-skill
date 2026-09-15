from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_CLI = PROJECT_ROOT / "scripts" / "benchmark.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import BenchmarkHarness, materialize_fixture
from benchmarks.harness import _safe_project_path
from core.efficient_dev import ProjectMapBuilder


class FixtureScaleTests(unittest.TestCase):
    def test_small_medium_large_grow_while_noise_stays_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            maps = []
            raw_counts = []
            for name in ("small", "medium", "large"):
                project = materialize_fixture(name, root / name)
                project_map = ProjectMapBuilder().build(project)
                maps.append(project_map)
                raw_counts.append(sum(1 for path in project.rglob("*") if path.is_file()))
                self.assertFalse(
                    any(path.path.startswith("node_modules/") for path in project_map.files)
                )
                self.assertFalse(
                    any(path.path.startswith("dist/") for path in project_map.files)
                )

        self.assertEqual([18, 30, 80], [item.metrics["mapped_files"] for item in maps])
        self.assertEqual([20, 35, 93], raw_counts)

    def test_fixture_path_safety_rejects_parent_and_windows_drive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("../outside.py", "..\\outside.py", "C:/outside.py"):
                with self.subTest(relative=relative):
                    with self.assertRaisesRegex(ValueError, "Unsafe benchmark path"):
                        _safe_project_path(root, relative)


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = BenchmarkHarness(PROJECT_ROOT).run()
        cls.by_id = {item["id"]: item for item in cls.result["scenarios"]}

    def test_complete_benchmark_is_deterministic(self) -> None:
        first = BenchmarkHarness(PROJECT_ROOT).run()
        second = BenchmarkHarness(PROJECT_ROOT).run()

        self.assertEqual(first, second)

    def test_all_required_context_is_covered_without_quality_failures(self) -> None:
        summary = self.result["summary"]

        self.assertEqual(9, summary["quality_passes"])
        self.assertEqual(0, summary["quality_failures"])
        self.assertEqual(1.0, summary["required_context_coverage_min"])
        self.assertTrue(summary["mvp_success"])

    def test_local_scope_does_not_grow_with_fixture_size(self) -> None:
        local = [
            self.by_id[identifier]
            for identifier in ("local-small", "local-medium", "local-large")
        ]

        self.assertEqual(
            [18, 30, 80],
            [item["baseline"]["reading"]["mapped_first_party_files"] for item in local],
        )
        self.assertEqual(
            [2, 2, 2],
            [item["efficient"]["reading"]["files_read_or_recommended"] for item in local],
        )
        self.assertTrue(
            all(
                item["efficient"]["instructions"]["selected_instruction_groups"] == 3
                for item in local
            )
        )
        self.assertTrue(
            all(item["efficient"]["tests"]["selected_tests"] == 1 for item in local)
        )

    def test_broad_risk_cases_expand_instead_of_optimizing_tests(self) -> None:
        for identifier in (
            "shared-core-large",
            "configuration-medium",
            "ambiguous-large",
        ):
            with self.subTest(identifier=identifier):
                scenario = self.by_id[identifier]
                self.assertTrue(
                    scenario["efficient"]["tests"]["full_suite_recommended"]
                )
                self.assertEqual(
                    scenario["efficient"]["tests"]["available_tests"],
                    scenario["efficient"]["tests"]["selected_tests"],
                )
                self.assertTrue(scenario["quality"]["quality_pass"])

        self.assertTrue(
            self.by_id["ambiguous-large"]["efficient"]["routing"][
                "requires_broader_search"
            ]
        )

    def test_cache_hit_is_a_proxy_and_changed_content_is_never_reused(self) -> None:
        repeated = self.by_id["repeated-cache-medium"]["efficient"]["cache"]
        changed = self.by_id["changed-cache-medium"]["efficient"]["cache"]

        self.assertEqual("valid", repeated["status"])
        self.assertEqual(1, repeated["cache_hits"])
        self.assertEqual(1, repeated["avoided_repeat_reads"])
        self.assertEqual("stale", changed["status"])
        self.assertEqual(1, changed["stale_entries"])
        self.assertTrue(changed["same_timestamp_change"])
        self.assertFalse(changed["stale_knowledge_used"])

    def test_instruction_test_and_context_metrics_are_selective_proxies(self) -> None:
        summary = self.result["summary"]

        self.assertTrue(self.result["metrics_are_proxies"])
        self.assertFalse(self.result["real_token_usage_measured"])
        self.assertLess(
            summary["efficient_instruction_bytes"],
            summary["baseline_instruction_bytes"],
        )
        self.assertLess(
            summary["efficient_selected_tests"],
            summary["baseline_selected_tests"],
        )
        self.assertLess(
            summary["efficient_context_bytes"],
            summary["baseline_context_bytes"],
        )
        self.assertTrue(
            all(
                item["efficient"]["context"]["working_context_bytes"]
                < item["efficient"]["context"]["raw_context_bytes"]
                for item in self.result["scenarios"]
            )
        )

    def test_cli_supports_scenario_kind_and_json(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(BENCHMARK_CLI),
                "--scenario",
                "local",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(3, result["summary"]["scenario_count"])
        self.assertFalse(result["summary"]["complete_suite"])
        self.assertIsNone(result["summary"]["mvp_success"])
        self.assertEqual(
            {"local-small", "local-medium", "local-large"},
            {item["id"] for item in result["scenarios"]},
        )


if __name__ == "__main__":
    unittest.main()
