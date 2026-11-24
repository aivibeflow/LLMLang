"""Tests for accounting-only adjudication manifest validator."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from validate_research_quality_adjudication import validate


class AdjudicationValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "research").mkdir()
        self.path = "research/ONE.md"
        (self.root / self.path).write_text("# Sample\nexample\n", encoding="utf-8")
        self.git("init")
        self.git("add", self.path)
        self.git("-c", "user.name=Research Test", "-c", "user.email=research@example.invalid",
                 "commit", "-m", "Pin fixture")
        baseline = self.git("rev-parse", "HEAD")
        self.sample = {"baseline_commit": baseline, "files": [{
            "path": self.path, "git_blob": self.git("rev-parse", f"{baseline}:{self.path}"),
            "expected_warnings": [
                "missing section for decision boundary",
                "missing metadata: Baseline",
            ],
            "confirmed_layout_only": [{
                "warning": "missing section for decision boundary",
                "grounding": "L1",
            }],
        }]}
        self.adj = {"baseline_commit": baseline, "summary": {
            "remaining_initial": 1,
            "layout-only": 0,
            "documentation-gap": 1,
        }, "files": [{"path": "research/ONE.md", "judgments": [{
            "warning": "missing metadata: Baseline",
            "disposition": "documentation-gap",
            "source_lines": "L1–2",
            "assessment": "Original commit not stated",
            "follow_up": "Record exact revision",
        }]}]}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def test_exact_complete_set_passes(self):
        self.assertEqual(validate(self.sample, self.adj, self.root), [])

    def test_missing_classification_is_detected(self):
        self.adj["files"][0]["judgments"] = []
        self.assertTrue(any("unadjudicated" in v for v in validate(self.sample, self.adj, self.root)))

    def test_duplicate_classification_is_detected(self):
        self.adj["files"][0]["judgments"].append(dict(self.adj["files"][0]["judgments"][0]))
        self.assertTrue(any("duplicate" in v for v in validate(self.sample, self.adj, self.root)))

    def test_invalid_line_range_is_detected(self):
        self.adj["files"][0]["judgments"][0]["source_lines"] = "L999"
        self.assertTrue(any("cited lines" in v for v in validate(self.sample, self.adj, self.root)))

    def test_wrong_disposition_is_detected(self):
        self.adj["files"][0]["judgments"][0]["disposition"] = "proof established"
        self.assertTrue(any("disposition" in v for v in validate(self.sample, self.adj, self.root)))

    def test_relocated_source_keeps_archived_citations(self):
        self.git("mv", self.path, "research/RELOCATED.md")
        self.assertEqual(validate(self.sample, self.adj, self.root), [])

    def test_different_blob_cannot_authorize_citations(self):
        self.sample["files"][0]["git_blob"] = "0" * 40
        self.assertTrue(any("blob mismatch" in v for v in validate(self.sample, self.adj, self.root)))


if __name__ == "__main__":
    unittest.main()
