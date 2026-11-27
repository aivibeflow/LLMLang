import unittest

from check_repo_structure import REQUIRED_FILES, validate_paths


class RepositoryStructureTests(unittest.TestCase):
    def valid_layout(self):
        return set(REQUIRED_FILES) | {
            "research/RESEARCH-SCENARIO-01.md",
            "research/PROTOTYPES/sample.py",
        }

    def test_accepts_expected_layout(self):
        self.assertEqual(validate_paths(self.valid_layout()), [])

    def test_rejects_missing_examples_and_draft(self):
        paths = self.valid_layout()
        paths.remove("examples/0002-echo.md")
        paths.remove("draft/GLOSSARY.md")
        errors = validate_paths(paths)
        self.assertTrue(any("examples/0002-echo.md" in e for e in errors))
        self.assertTrue(any("draft/GLOSSARY.md" in e for e in errors))

    def test_rejects_research_documents_at_root(self):
        errors = validate_paths(self.valid_layout() | {"RESEARCH-SCENARIO-99.md"})
        self.assertTrue(any("RESEARCH-SCENARIO-99.md" in e for e in errors))

    def test_rejects_prototype_directory_at_root(self):
        errors = validate_paths(self.valid_layout() | {"PROTOTYPES/example/main.py"})
        self.assertTrue(any("PROTOTYPES/example/main.py" in e for e in errors))

    def test_rejects_standalone_llmlang_source_files(self):
        forbidden = {"main.llmlang", "draft/stdlib/write.llmlang", "research/sample.LLMLANG"}
        errors = validate_paths(self.valid_layout() | forbidden)
        self.assertEqual(errors, [
            f"standalone .llmlang source files are prohibited: {path}"
            for path in sorted(forbidden)
        ])

    def test_rejects_missing_research_documents(self):
        paths = {p for p in self.valid_layout() if not (p.startswith("research/") and p.endswith(".md"))}
        errors = validate_paths(paths)
        self.assertTrue(any("at least one Markdown research document" in e for e in errors))

    def test_requires_all_ci_workflows(self):
        paths = self.valid_layout()
        paths.remove(".github/workflows/logos-binding.yml")
        errors = validate_paths(paths)
        self.assertTrue(any("logos-binding.yml" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
