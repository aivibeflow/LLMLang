"""Frozen claim register structural tests (not evidence truth testing)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from validate_research_claim_cohort import validate


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True,
        text=True, check=True,
    ).stdout.strip()


class ClaimCohortValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init")
        git(self.root, "config", "user.name", "Cohort test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "research").mkdir()
        (self.root / "source").mkdir()
        reports = []
        for i in range(12):
            report = f"research/report_{i}.md"
            source = f"source/fixture_{i}.py"
            (self.root / report).write_text("# Research\n## Result\nA bounded claim.\n## Limit\nUnproven bridge.\n")
            (self.root / source).write_text("print('fixture')\n")
            reports.append((report, source))
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "baseline")
        sha = git(self.root, "rev-parse", "HEAD")
        items = []
        for i, (report, source) in enumerate(reports):
            items.append({
                "report_path": report,
                "report_blob": git(self.root, "hash-object", report),
                "reference_path": source,
                "reference_blob": git(self.root, "hash-object", source),
                "evidence_shape": "fixture",
                "claims": [
                    {
                        "id": f"T{i}-{j}",
                        "primary_evidence_class": "Experimental result",
                        "report_line_start": 2, "report_line_end": 3,
                        "boundary_line_start": 4, "boundary_line_end": 5,
                        "statement": "bounded", "scope": "fixture only",
                        "unproven_or_negative": "generalization",
                        "evidence_level": "report-only",
                        "draft_impact": "none", "review_status": "preliminary",
                    } for j in range(2)
                ],
            })
        self.manifest = {"baseline_commit": sha, "reports": items}

    def test_fixed_sample_passes_and_is_not_claim_truth_check(self):
        x = validate(self.root, self.manifest)
        self.assertEqual(x["errors"], [])
        self.assertEqual((x["reports"], x["claims"]), (12, 24))
        self.assertFalse(any(row["technical_truth_reviewed_by_script"] for row in x["checked"]))

    def test_modified_working_file_does_not_change_baseline(self):
        (self.root / "research/report_0.md").write_text("# New claim\n")
        self.assertEqual(validate(self.root, self.manifest)["errors"], [])

    def test_wrong_source_blob_fails(self):
        self.manifest["reports"][0]["reference_blob"] = "0" * 40
        self.assertTrue(any("reference blob" in e for e in validate(self.root, self.manifest)["errors"]))

    def test_out_of_bounds_citation_fails(self):
        self.manifest["reports"][0]["claims"][0]["boundary_line_end"] = 1000
        self.assertTrue(any("line range" in e for e in validate(self.root, self.manifest)["errors"]))

    def test_duplicate_claim_identifier_fails(self):
        a = self.manifest["reports"][0]["claims"][0]["id"]
        self.manifest["reports"][1]["claims"][0]["id"] = a
        self.assertTrue(any("duplicate claim ID" in e for e in validate(self.root, self.manifest)["errors"]))

    def test_missing_evidence_class_fails(self):
        self.manifest["reports"][0]["claims"][0]["primary_evidence_class"] = "Trust me"
        self.assertTrue(any("unknown evidence class" in e for e in validate(self.root, self.manifest)["errors"]))


if __name__ == "__main__":
    unittest.main()
