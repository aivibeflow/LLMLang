"""Tests for fixed-baseline census and warning-independent reviewer selection."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from research_quality_corpus_census import choose_sample, kind, paths_at_commit, run


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


class CensusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Census tests")
        git(self.root, "config", "user.email", "census@example.invalid")
        (self.root / "research" / "preparation").mkdir(parents=True)
        for name in ("RT-02-FOO.md", "RESEARCH-SCENARIO-02-FOO.md", "README.md"):
            (self.root / "research" / name).write_text("# Report\n## Results\nBounded.\n")
        (self.root / "research" / "preparation" / "NESTED.md").write_text("# Out of scope\n")
        (self.root / "outside.md").write_text("# Not research\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "baseline")
        self.sha = git(self.root, "rev-parse", "HEAD")

    def test_scopes_exact_root_markdown_not_nested(self):
        self.assertEqual(
            paths_at_commit(self.root, self.sha),
            ["research/README.md", "research/RESEARCH-SCENARIO-02-FOO.md", "research/RT-02-FOO.md"],
        )

    def test_pinned_content_not_changed_by_uncommitted_worktree(self):
        a = run(self.root, self.sha)
        (self.root / "research" / "README.md").write_text("# Replaced in worktree\n")
        b = run(self.root, self.sha)
        self.assertEqual(a, b)
        self.assertEqual(a["summary"]["documents"], 3)
        self.assertFalse(a["scientific_truth_validated"])
        self.assertFalse(a["human_review_completed"])

    def test_different_warning_counts_do_not_affect_sampling(self):
        rows = [
            {"path": f"research/RT-{i:02d}.md", "kind": "rt", "blob": f"b{i}", "warnings": []}
            for i in range(20)
        ]
        first = choose_sample(rows, seed="seed", per_stratum=8)
        for r in rows:
            r["warnings"] = ["artificial warning"] * 7
        second = choose_sample(rows, seed="seed", per_stratum=8)
        self.assertEqual([r["path"] for r in first], [r["path"] for r in second])
        self.assertEqual(len(first), 8)

    def test_reject_ambiguous_commit_identifier(self):
        with self.assertRaises(ValueError):
            run(self.root, self.sha[:8])

    def test_categories_are_not_evidence_types(self):
        self.assertEqual(kind("research/RT-24.md"), "rt")
        self.assertEqual(kind("research/RESEARCH-SCENARIO-99.md"), "scenario")
        self.assertEqual(kind("research/QUALITY-REVIEW-PROTOCOL.md"), "other-root")


if __name__ == "__main__":
    unittest.main()
