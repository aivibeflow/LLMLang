"""Deterministic transport and repair fixtures for Scenario 95."""

from dataclasses import dataclass
import hashlib
import json
import re
import unittest


def position(source: bytes, offset: int, encoding: str = "utf-16") -> tuple[int, int]:
    units = {"utf-8": ("utf-8", 1), "utf-16": ("utf-16-le", 2), "utf-32": ("utf-32-le", 4)}
    if encoding not in units or not 0 <= offset <= len(source):
        raise ValueError("invalid location or encoding")
    if source[offset - 1:offset + 1] == b"\r\n":
        raise ValueError("location inside CRLF")
    lines = re.split(rb"\r\n|\r|\n", source[:offset])
    codec, width = units[encoding]
    return len(lines) - 1, len(lines[-1].decode("utf-8").encode(codec)) // width


def snapshot(files: dict[str, bytes]) -> str:
    entries = sorted((path, hashlib.sha256(data).hexdigest()) for path, data in files.items())
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


@dataclass(frozen=True)
class Report:
    snapshot_id: str
    state: str
    codes: tuple[str, ...] = ()

    def clean_at(self, files: dict[str, bytes]) -> bool:
        return self.snapshot_id == snapshot(files) and self.state == "complete" and not self.codes


@dataclass(frozen=True, order=True)
class Edit:
    path: str
    start: int
    end: int
    replacement: bytes


def stage(files: dict[str, bytes], expected: str, edits: tuple[Edit, ...]) -> dict[str, bytes]:
    if expected != snapshot(files):
        raise ValueError("stale snapshot")
    previous_by_path = {}
    for edit in sorted(edits):
        source = files.get(edit.path)
        if source is None or not 0 <= edit.start <= edit.end <= len(source):
            raise ValueError("invalid edit range or document")
        previous = previous_by_path.get(edit.path)
        if previous and (previous.end > edit.start or previous.start == edit.start):
            raise ValueError("overlapping or ambiguous edits")
        position(source, edit.start)
        position(source, edit.end)
        edit.replacement.decode("utf-8")
        previous_by_path[edit.path] = edit
    result = dict(files)
    for edit in sorted(edits, reverse=True):
        source = result[edit.path]
        result[edit.path] = source[:edit.start] + edit.replacement + source[edit.end:]
    return result


def compile_policy(files: dict[str, bytes]) -> tuple[int, bool]:
    policy = json.loads(files["policy.json"])
    if type(policy["limit"]) is not int or type(policy["guard"]) is not bool:
        raise ValueError("expected Int limit and Bool guard")
    return policy["limit"], policy["guard"]


def accepts(policy: tuple[int, bool], value: int) -> bool:
    limit, guard = policy
    return value <= limit if guard else True


class DiagnosticReplay(unittest.TestCase):
    def test_unicode_ranges_survive_all_three_transport_encodings(self):
        source = "α😀e\u0301\r\n😀Z".encode()
        start, end = len("α😀".encode()), len("α😀e\u0301".encode())
        for encoding, expected in {"utf-8": (6, 9), "utf-16": (3, 5), "utf-32": (2, 4)}.items():
            self.assertEqual((position(source, start, encoding), position(source, end, encoding)),
                             ((0, expected[0]), (0, expected[1])))
        self.assertEqual(position(source, source.index(b"Z")), (1, 2))
        for offset in (1, end + 1):
            with self.assertRaises(ValueError):
                position(source, offset)

    def test_empty_stale_and_incomplete_reports_do_not_pass(self):
        files = {"entry": b"same", "dependency": b"old"}
        report = Report(snapshot(files), "complete")
        self.assertTrue(report.clean_at(files))
        self.assertFalse(report.clean_at({**files, "dependency": b"changed"}))
        for state in ("partial", "cancelled", "unknown"):
            self.assertFalse(Report(snapshot(files), state).clean_at(files))

    def test_multi_document_staging_rejects_stale_and_overlapping_batches(self):
        files = {"a": b"abcd", "b": "😀".encode()}
        expected = snapshot(files)
        batches = (
            (expected, (Edit("a", 0, 1, b"A"), Edit("b", 1, 4, b"B"))),
            (expected, (Edit("a", 0, 2, b"A"), Edit("a", 1, 3, b"B"))),
            (expected, (Edit("a", 1, 1, b"A"), Edit("a", 1, 1, b"B"))),
            (snapshot({**files, "b": b"previous"}), (Edit("a", 0, 1, b"A"),)),
        )
        for target, edits in batches:
            with self.assertRaises(ValueError):
                stage(files, target, edits)
            self.assertEqual(snapshot(files), expected)
        edits = (Edit("a", 0, 1, b"AA"), Edit("a", 2, 3, b"C"), Edit("b", 0, 4, b"B"))
        for order in (edits, edits[::-1]):
            self.assertEqual(stage(files, expected, order), {"a": b"AAbCd", "b": b"B"})

    def test_compile_success_is_weaker_than_behavioral_validation(self):
        files = {"policy.json": b'{"limit":"5","guard":true}'}
        with self.assertRaises(ValueError):
            compile_policy(files)
        rejected = []
        for label, text in (("repair", b'{"limit":5,"guard":true}'),
                            ("weaken", b'{"limit":5,"guard":false}')):
            edits = (Edit("policy.json", 0, len(files["policy.json"]), text),)
            compiled = compile_policy(stage(files, snapshot(files), edits))
            mismatch = [n for n in range(11) if accepts(compiled, n) != (n <= 5)]
            if mismatch:
                rejected.append((label, mismatch))
        self.assertEqual(rejected, [("weaken", [6, 7, 8, 9, 10])])


if __name__ == "__main__":
    unittest.main()
