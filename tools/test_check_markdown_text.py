import unittest

from check_markdown_text import markdown_issue


class MarkdownTextTest(unittest.TestCase):
    def test_accepts_ascii_and_utf8_markdown(self):
        self.assertIsNone(markdown_issue("# Привет\n\nТекст.\n".encode("utf-8")))

    def test_accepts_markdown_whitespace_controls(self):
        self.assertIsNone(markdown_issue(b"line one\r\n\tline two\n"))

    def test_rejects_invalid_utf8(self):
        self.assertIn("invalid UTF-8", markdown_issue(b"# title\n\xff"))

    def test_rejects_nul_bytes(self):
        self.assertIn("U+0000", markdown_issue(b"# title\0\n"))

    def test_rejects_non_whitespace_control_characters(self):
        self.assertIn("U+001B", markdown_issue(b"# title\x1b\n"))


if __name__ == "__main__":
    unittest.main()
