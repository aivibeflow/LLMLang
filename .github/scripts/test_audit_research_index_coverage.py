from pathlib import Path
import tempfile
import unittest

from audit_research_index_coverage import audit, extract_targets, resolve_local_target


class ExtractTargetsTests(unittest.TestCase):
    def test_inline_html_and_reference_targets_are_extracted(self):
        text = (
            "[scenario](./RESEARCH-SCENARIO-01.md#claim) "
            '<a href="../README.md">index</a>\n'
            "[ref]: ./other.md\n"
        )
        self.assertEqual(
            extract_targets(text),
            ["./RESEARCH-SCENARIO-01.md#claim", "../README.md", "./other.md"],
        )

    def test_code_and_comments_are_ignored(self):
        text = (
            "[visible](visible.md)\n"
            "```md\n[code](code.md)\n```\n"
            "<!-- [comment](comment.md) -->\n"
            "`[inline](inline.md)`\n"
        )
        self.assertEqual(extract_targets(text), ["visible.md"])

    def test_external_fragment_and_root_absolute_are_not_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "research" / "README.md"
            source.parent.mkdir(parents=True)
            source.write_text("")
            self.assertIsNone(resolve_local_target(root, source, "https://example.com/doc.md"))
            self.assertIsNone(resolve_local_target(root, source, "#anchor"))
            self.assertIsNone(resolve_local_target(root, source, "/upstream/site/path.md"))


class AuditTests(unittest.TestCase):
    def test_index_inbound_and_zero_inbound_are_distinguished(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            research = root / "research"
            research.mkdir()
            (research / "README.md").write_text("[Scenario](RESEARCH-SCENARIO-01.md)\n")
            (research / "RESEARCH-SCENARIO-01.md").write_text("# scenario\n")
            (research / "RESEARCH-SCENARIO-02.md").write_text("# unlinked\n")
            result = audit(root)
            self.assertEqual(result["summary"]["scenario_documents"], 2)
            self.assertEqual(result["summary"]["scenario_documents_without_inbound_link_from_designated_index"], 1)
            self.assertEqual(
                result["scenario_documents_without_index_inbound"],
                ["research/RESEARCH-SCENARIO-02.md"],
            )
            self.assertEqual(
                result["scenario_documents_with_zero_inbound"],
                ["research/RESEARCH-SCENARIO-02.md"],
            )

    def test_existing_non_markdown_resource_is_not_a_missing_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            research = root / "research"
            research.mkdir()
            (research / "README.md").write_text("![diagram](diagram.png)\\n")
            (research / "diagram.png").write_bytes(b"png")
            result = audit(root)
            self.assertEqual(result["summary"]["unresolved_local_targets"], 0)
            self.assertEqual(result["summary"]["non_markdown_targets"], 1)

    def test_directory_target_resolves_to_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            research = root / "research"
            (research / "sub").mkdir(parents=True)
            (research / "README.md").write_text("[sub](sub/)\n")
            (research / "sub" / "README.md").write_text("# sub\n")
            result = audit(root)
            self.assertEqual(result["summary"]["unique_research_targets_with_inbound_links"], 1)


if __name__ == "__main__":
    unittest.main()
