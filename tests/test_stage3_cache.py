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

from core.efficient_dev import ChangeTracker, ReadCache, fingerprint_file


class ProjectCopyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary_directory.name) / "fixture"
        shutil.copytree(FIXTURE, self.project)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()


class FingerprintTests(ProjectCopyTestCase):
    def test_fingerprint_is_deterministic_and_detects_same_timestamp_change(self) -> None:
        path = self.project / "src" / "history" / "render_history.ts"
        original = path.read_text(encoding="utf-8")
        original_stat = path.stat()
        first = fingerprint_file(path)
        self.assertEqual(first, fingerprint_file(path))

        path.write_text(original.replace("join", "sort"), encoding="utf-8")
        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

        self.assertEqual(original_stat.st_mtime_ns, path.stat().st_mtime_ns)
        self.assertNotEqual(first, fingerprint_file(path))


class ReadCacheTests(ProjectCopyTestCase):
    def test_cache_hit_reuses_compact_knowledge(self) -> None:
        cache = ReadCache(self.project)
        entry = cache.record(
            "src/history/render_history.ts",
            summary="Formats portfolio history points for display.",
            symbols=["renderHistory"],
            relationships=["tests/history/render_history.test.ts"],
        )
        result = cache.lookup("src/history/render_history.ts")

        self.assertEqual("valid", entry.validity)
        self.assertEqual("valid", result.status)
        self.assertFalse(result.requires_read)
        self.assertEqual(1, result.metrics["cache_hits"])
        self.assertEqual(0, result.metrics["cache_misses"])
        self.assertEqual(
            "Formats portfolio history points for display.",
            result.cached_knowledge["summary"],
        )

        cache_text = cache.storage_path.read_text(encoding="utf-8")
        source_text = (self.project / entry.path).read_text(encoding="utf-8")
        self.assertNotIn(source_text, cache_text)

    def test_exact_source_request_still_reads_on_cache_hit(self) -> None:
        cache = ReadCache(self.project)
        cache.record(
            "src/history/render_history.ts",
            summary="Formats portfolio history points.",
        )

        result = cache.lookup("src/history/render_history.ts", require_exact=True)

        self.assertEqual("valid", result.status)
        self.assertTrue(result.requires_read)
        self.assertEqual(1, result.metrics["cache_hits"])

    def test_modified_file_marks_only_its_entry_stale(self) -> None:
        cache = ReadCache(self.project)
        cache.record(
            "src/history/render_history.ts",
            summary="Formats portfolio history points.",
        )
        path = self.project / "src" / "history" / "render_history.ts"
        path.write_text("export const changed = true;\n", encoding="utf-8")

        result = cache.lookup("src/history/render_history.ts")

        self.assertEqual("stale", result.status)
        self.assertTrue(result.requires_read)
        self.assertIsNone(result.cached_knowledge)
        self.assertEqual(1, result.metrics["cache_misses"])
        self.assertEqual(1, result.metrics["stale_entries"])

    def test_record_overwrites_one_version_and_rejects_excluded_files(self) -> None:
        cache = ReadCache(self.project)
        cache.record("python/report.py", summary="First current description.")
        cache.record("python/report.py", summary="Replacement current description.")
        self.assertEqual(1, len(cache.entries))
        self.assertEqual(
            "Replacement current description.",
            cache.get_entry("python/report.py").summary,
        )

        noise = self.project / "node_modules" / "dependency.js"
        noise.parent.mkdir(parents=True)
        noise.write_text("module.exports = {};\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            cache.record("node_modules/dependency.js", summary="Excluded dependency.")

    def test_manual_invalidation_prevents_reuse_until_recorded_again(self) -> None:
        cache = ReadCache(self.project)
        path = "python/report.py"
        cache.record(path, summary="Portfolio report.")

        self.assertTrue(cache.invalidate(path))
        result = cache.lookup(path)

        self.assertEqual("invalid", result.status)
        self.assertTrue(result.requires_read)
        self.assertIsNone(result.cached_knowledge)

    def test_cache_storage_is_confined_to_project_runtime_directory(self) -> None:
        outside = Path(self.temporary_directory.name) / "outside-cache.json"

        with self.assertRaises(ValueError):
            ReadCache(self.project, storage_path=outside)


class ChangeTrackerTests(ProjectCopyTestCase):
    def _baseline(self) -> tuple[ChangeTracker, ReadCache]:
        tracker = ChangeTracker(self.project)
        cache = ReadCache(self.project)
        tracker.scan(read_cache=cache, update_baseline=True)
        return tracker, cache

    def test_unrelated_modification_does_not_invalidate_other_entry(self) -> None:
        tracker, cache = self._baseline()
        module_a = "src/history/render_history.ts"
        module_b = "src/charts/portfolio_chart.ts"
        cache.record(module_a, summary="History formatter.")
        cache.record(module_b, summary="Portfolio chart title.")
        (self.project / module_a).write_text(
            "export const changed = true;\n", encoding="utf-8"
        )

        result = tracker.scan(read_cache=cache)

        self.assertEqual((module_a,), result.modified)
        self.assertEqual((module_a,), result.invalidated_cache_entries)
        self.assertEqual("stale", cache.get_entry(module_a).validity)
        self.assertEqual("valid", cache.get_entry(module_b).validity)
        self.assertIn(module_b, result.unchanged)

    def test_added_and_deleted_files_are_reported_and_deleted_cache_is_removed(self) -> None:
        tracker, cache = self._baseline()
        deleted = "python/report.py"
        added = "src/new_module.ts"
        cache.record(deleted, summary="Python portfolio report.")
        (self.project / deleted).unlink()
        (self.project / added).write_text("export const value = 1;\n", encoding="utf-8")

        result = tracker.scan(read_cache=cache)

        self.assertEqual((added,), result.added)
        self.assertEqual((deleted,), result.deleted)
        self.assertIn(deleted, result.invalidated_cache_entries)
        self.assertIsNone(cache.get_entry(deleted))
        self.assertTrue(result.project_map_stale)
        self.assertEqual(("python", "src"), result.project_map_refresh_directories)

    def test_same_state_produces_same_change_result(self) -> None:
        tracker, _ = self._baseline()
        path = self.project / "rust" / "src" / "lib.rs"
        path.write_text('pub fn changed() -> bool { true }\n', encoding="utf-8")

        first = tracker.scan().to_dict()
        second = tracker.scan().to_dict()

        self.assertEqual(first, second)

    def test_noise_and_runtime_state_are_not_tracked(self) -> None:
        tracker, cache = self._baseline()
        noise = self.project / "node_modules" / "dependency.js"
        noise.parent.mkdir(parents=True)
        noise.write_text("noise\n", encoding="utf-8")
        cache.record("python/report.py", summary="Portfolio report.")

        result = tracker.scan(read_cache=cache)

        self.assertEqual(0, result.metrics["changed_files"])
        self.assertFalse(result.project_map_stale)
        self.assertFalse(any("node_modules" in path for path in result.added))
        self.assertFalse(any(".efficient-dev" in path for path in result.added))


class Stage3CliTests(ProjectCopyTestCase):
    def test_cache_and_changes_commands_cover_hit_and_stale_flow(self) -> None:
        initial = self._run_cli("changes", "--root", str(self.project), "--update", "--json")
        self.assertTrue(json.loads(initial.stdout)["baseline_updated"])

        self._run_cli(
            "cache",
            "record",
            "src/history/render_history.ts",
            "--root",
            str(self.project),
            "--summary",
            "History formatter.",
            "--symbol",
            "renderHistory",
            "--json",
        )
        hit = self._run_cli(
            "cache",
            "inspect",
            "src/history/render_history.ts",
            "--root",
            str(self.project),
            "--json",
        )
        hit_data = json.loads(hit.stdout)
        self.assertEqual("valid", hit_data["status"])
        self.assertEqual(1, hit_data["metrics"]["cache_hits"])

        status = self._run_cli(
            "cache", "status", "--root", str(self.project), "--json"
        )
        status_data = json.loads(status.stdout)
        self.assertEqual(1, status_data["metrics"]["cache_entries"])
        self.assertEqual("valid", status_data["entries"][0]["validity"])

        path = self.project / "src" / "history" / "render_history.ts"
        path.write_text("export const changed = true;\n", encoding="utf-8")
        changes = self._run_cli("changes", "--root", str(self.project), "--json")
        changes_data = json.loads(changes.stdout)
        self.assertEqual(["src/history/render_history.ts"], changes_data["modified"])
        self.assertEqual(
            ["src/history/render_history.ts"],
            changes_data["invalidated_cache_entries"],
        )

        stale = self._run_cli(
            "cache",
            "inspect",
            "src/history/render_history.ts",
            "--root",
            str(self.project),
            "--json",
        )
        stale_data = json.loads(stale.stdout)
        self.assertEqual("stale", stale_data["status"])
        self.assertTrue(stale_data["requires_read"])

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
