"""Fail when a tracked Markdown file contains binary or non-UTF-8 data."""

from __future__ import annotations

import subprocess
import sys
import unicodedata
from pathlib import Path


def markdown_issue(data: bytes) -> str | None:
    """Return a reason when bytes are not plain UTF-8 text suitable for Markdown."""
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return f"invalid UTF-8 at byte {exc.start}"

    for offset, char in enumerate(text):
        if unicodedata.category(char) == "Cc" and char not in "\t\n\r":
            return f"control character U+{ord(char):04X} at character {offset}"
    return None


def tracked_markdown_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [
        root / Path(raw.decode("utf-8", errors="surrogateescape"))
        for raw in result.stdout.split(b"\0")
        if raw and raw.decode("utf-8", errors="surrogateescape").lower().endswith(".md")
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = tracked_markdown_files(root)
    failures: list[str] = []
    for path in files:
        issue = markdown_issue(path.read_bytes())
        if issue:
            failures.append(f"{path.relative_to(root)}: {issue}")

    if failures:
        print("Markdown text check failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"Checked {len(files)} tracked Markdown files: all are UTF-8 text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
