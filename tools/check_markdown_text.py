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


def indexed_markdown_blobs(root: Path) -> list[tuple[str, bytes]]:
    """Read Markdown blobs from the Git index, so hooks inspect exactly staged data."""
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    entries: list[tuple[str, str]] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        _mode, oid, stage = metadata.split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if path.lower().endswith(".md"):
            if stage != b"0":
                raise ValueError(f"unmerged Markdown index entry: {path}")
            entries.append((path, oid.decode("ascii")))

    if not entries:
        return []

    blobs = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input=("\n".join(oid for _, oid in entries) + "\n").encode("ascii"),
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    result_blobs: list[tuple[str, bytes]] = []
    offset = 0
    for path, expected_oid in entries:
        header_end = blobs.index(b"\n", offset)
        oid, object_type, size_text = blobs[offset:header_end].decode("ascii").split()
        if oid != expected_oid or object_type != "blob":
            raise ValueError(f"unexpected Git index object for {path}")
        size = int(size_text)
        data_start = header_end + 1
        data_end = data_start + size
        result_blobs.append((path, blobs[data_start:data_end]))
        if blobs[data_end:data_end + 1] != b"\n":
            raise ValueError(f"malformed Git object response for {path}")
        offset = data_end + 1
    return result_blobs


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        files = indexed_markdown_blobs(root)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"Markdown text check failed: {exc}")
        return 1

    failures: list[str] = []
    for path, data in files:
        issue = markdown_issue(data)
        if issue:
            failures.append(f"{path}: {issue}")

    if failures:
        print("Markdown text check failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"Checked {len(files)} indexed Markdown files: all are UTF-8 text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
