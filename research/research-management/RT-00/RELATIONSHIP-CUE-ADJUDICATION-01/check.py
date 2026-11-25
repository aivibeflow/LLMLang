"""Bind reviewed replacement and conflict cues to the archived candidate screen."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
SCREEN = ROOT.parent / "CURRENT-CORPUS-RELATIONSHIPS-01" / "evidence.json"
PATTERNS = {
    "replacement": re.compile("supersed|obsolet|replac", re.I),
    "conflict": re.compile("contradict|incompatib|conflict", re.I),
}
# Numbers are one-based positions in the pinned screen's candidate array.
REVIEWS = {
    "scoped_supersession": {300, 302, 308, 371, 423, 520},
    "updated_execution_status": {472},
    "same_subject_distinct_scope": {
        1, 13, 58, 179, 180, 207, 321, 322, 324, 331, 332, 333, 334, 343, 344,
        353, 373, 374, 375, 376, 377, 383, 384, 387, 390, 391, 394, 396, 397, 399,
        404, 434, 449, 450, 451, 477, 478, 479, 495, 502, 503, 506, 510, 511,
        512, 527, 532, 535,
    },
    "index_crosswalk_or_context": {
        30, 31, 32, 36, 37, 38, 39, 45, 46, 84, 92, 126, 284, 285, 304, 307,
        309, 311, 312, 313, 318, 323, 363, 364, 366, 385, 400, 403, 416, 417, 418,
        419, 425, 429, 438, 439, 440, 453, 454, 496,
    },
}


def archive_lines(base, path, blob):
    data = subprocess.check_output(["git", "show", f"{base}:{path}"])
    actual = subprocess.check_output(["git", "hash-object", "--stdin"], input=data)
    assert actual.decode().strip() == blob, path
    return data.decode().splitlines()


def main():
    source = SCREEN.read_bytes()
    screen = json.loads(source)
    assert screen["baseline"] == "9847850c12cda140e0bdb396d611c2ec96b85c33"
    cache = {}
    matches = []
    for number, row in enumerate(screen["candidates"], 1):
        markers = []
        for cue, locations in row["sources"].items():
            for path, line in locations:
                if not isinstance(line, int):
                    continue
                blob = screen["source_blobs"][path]
                if path not in cache:
                    cache[path] = archive_lines(screen["baseline"], path, blob)
                excerpt = cache[path][line - 1]
                for family, pattern in PATTERNS.items():
                    if pattern.search(excerpt):
                        markers.append({
                            "signal": cue, "cue": family, "path": path,
                            "line": line, "blob": blob, "excerpt_sha256": hashlib.sha256(
                                excerpt.encode()).hexdigest(),
                        })
        if markers:
            dispositions = [label for label, reviewed in REVIEWS.items() if number in reviewed]
            assert len(dispositions) == 1, (number, dispositions)
            matches.append({
                "candidate": number, "first": row["first"], "second": row["second"],
                "first_blob": screen["source_blobs"][row["first"]],
                "second_blob": screen["source_blobs"][row["second"]],
                "disposition": dispositions[0], "markers": markers,
            })
    assert {row["candidate"] for row in matches} == set.union(*REVIEWS.values())
    print(json.dumps({
        "base": screen["baseline"], "candidate_screen_sha256": hashlib.sha256(source).hexdigest(),
        "all_candidates": len(screen["candidates"]), "disposition_counts": {
            label: len(reviewed) for label, reviewed in REVIEWS.items()
        },
        "cue_counts": {
            family: sum(marker["cue"] == family for row in matches for marker in row["markers"])
            for family in PATTERNS
        },
        "reviewed": matches,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
