"""Regression tests: immutable sample vs later edits to research reports."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_research_quality import inspect
from replay_research_quality_sample import run


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


class HistoricalWarningSampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init")
        git(self.root, "config", "user.email", "research@example.invalid")
        git(self.root, "config", "user.name", "Historical test fixture")
        (self.root / "research").mkdir()
        self.rel = "research/sample.md"
        self.old = "# Probe\n## Results\nOriginal dated experiment.\n"
        (self.root / self.rel).write_text(self.old, encoding="utf-8")
        git(self.root, "add", self.rel)
        git(self.root, "commit", "-m", "fixture: first report")
        sha = git(self.root, "rev-parse", "HEAD")
        blob = git(self.root, "hash-object", self.rel)
        self.manifest = {"baseline_commit": sha, "files": [{
            "path": self.rel, "git_blob": blob,
            "expected_warnings": inspect(self.old),
            "confirmed_layout_only": [],
        }]}

    def test_frozen_sample_remains_stable_after_edit(self):
        (self.root / self.rel).write_text("# Probe\n## Model\nNew revision!\n")
        result = run(self.root, self.manifest, from_baseline=True)
        self.assertEqual(result["reports_checked"], 1)
        self.assertEqual(result["blob_mismatches"], 0)
        self.assertEqual(result["warning_snapshot_mismatches"], 0)
        self.assertEqual(result["source_mode"], "git-baseline")
        self.assertEqual(run(self.root, self.manifest)["blob_mismatches"], 1)

    def test_tampered_manifest_blob_fails(self):
        self.manifest["files"][0]["git_blob"] = "0" * 40
        result = run(self.root, self.manifest, from_baseline=True)
        self.assertEqual(result["blob_mismatches"], 1)

    def test_missing_baseline_is_reported_not_silently_replaced(self):
        self.manifest["baseline_commit"] = "0" * 40
        result = run(self.root, self.manifest, from_baseline=True)
        self.assertEqual(result["blob_mismatches"], 1)
        self.assertIn("unavailable", result["reports"][0]["error"])

    def test_unsafe_path_is_rejected(self):
        self.manifest["files"][0]["path"] = "../escape.md"
        result = run(self.root, self.manifest, from_baseline=True)
        self.assertEqual(result["blob_mismatches"], 1)
        self.assertIn("unsafe", result["reports"][0]["error"])


if __name__ == "__main__":
    unittest.main()
