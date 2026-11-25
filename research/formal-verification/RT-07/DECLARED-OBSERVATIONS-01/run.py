#!/usr/bin/env python3
"""Compare declared observations and reproduce the studies supplying the fields."""

from collections import Counter
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as tar_open
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "078704760dd2434923c73ac34aaa8973fa57c64f"
FORMAL = Path("research/formal-verification/RT-07")
RUNTIME = Path("research/runtime-and-systems")
LANGUAGE = Path("research/language-design/RT-04")
OLD_PROTOTYPE = Path("research/PROTOTYPES/RT-04-01")
ENV = {**os.environ, "LC_ALL": "C", "PYTHONHASHSEED": "1"}
FIELDS = {
    "return": ({"value": 7}, {"value": 8}),
    "error": ({"tag": "planned"}, {"tag": "denied"}),
    "state": ({"cell": 0}, {"cell": 1}),
    "io": ({"accepted_bytes": "41", "status": "error"}, {"accepted_bytes": "4142", "status": "error"}),
    "resources": ({"spent": 2, "reserved": 1, "live": 0}, {"spent": 3, "reserved": 0, "live": 0}),
    "concurrency": ({"flag": 1, "reads_from": "release"}, {"flag": 1, "reads_from": "relaxed"}),
    "declared_effects": ([["write", 1], ["write", 0]], [["write", 0], ["write", 1]]),
}
SCOPE = "closed-observation-profile/1"


def execute(args, root):
    return subprocess.run(args, cwd=root, env=ENV, check=True, capture_output=True, timeout=45).stdout


def digest(raw):
    return sha256(raw).hexdigest()


def compare(scope, required, left, right):
    if left["scope"] != scope or right["scope"] != scope:
        return "scope-mismatch"
    a, b = left["observations"], right["observations"]
    if any(field in a and field in b and a[field] != b[field] for field in required):
        return "different"
    if any(field not in a or field not in b for field in required):
        return "incomplete"
    return "matches"


def profile_matrix():
    fields = tuple(FIELDS)
    required_sets = [{field for i, field in enumerate(fields) if mask & (1 << i)}
                     for mask in range(1 << len(fields))]
    left = {"scope": SCOPE, "observations": {axis: values[0] for axis, values in FIELDS.items()}}
    counts = Counter()
    for states in product(range(3), repeat=len(fields)):
        row = {field: FIELDS[field][state] for field, state in zip(fields, states) if state != 2}
        changed = {field for field, state in zip(fields, states) if state == 1}
        unavailable = {field for field, state in zip(fields, states) if state == 2}
        right = {"scope": SCOPE, "observations": row}
        for required in required_sets:
            expected = ("different" if required & changed else "incomplete" if required & unavailable
                        else "matches")
            decision = compare(SCOPE, required, left, right)
            if decision != expected:
                raise AssertionError((states, required, decision, expected))
            counts[decision] += 1
            counts["profiles"] += 1
            shared_only = compare(SCOPE, required & row.keys(), left, right)
            if shared_only == "matches" and decision == "incomplete":
                counts["shared_only_false_admissions"] += 1
        full = compare(SCOPE, fields, left, right)
        if compare(SCOPE, {"return", "error"}, left, right) == "matches" and full == "different":
            counts["terminal_only_misses_definite_full_profile_difference"] += 1

    missing = {"scope": SCOPE, "observations": {}}
    if compare(SCOPE, ["error"], missing, left) != "incomplete":
        raise AssertionError("Missing field on the left was accepted")
    if compare(SCOPE, ["error"], left, {**left, "scope": "foreign"}) != "scope-mismatch":
        raise AssertionError("Observation profile mismatch was accepted")
    return counts


def replays():
    cases = (
        ("state_result", FORMAL / "STATE-RESULT-REFERENCE-01", "validate.py", None),
        ("output", FORMAL / "PARTIAL-OUTPUT-01", "run.py", "Prefix.lean"),
        ("quota", RUNTIME / "RT-26/DELEGATED-QUOTA-01", "run.py", "Quota.lean"),
        ("concurrent_history", RUNTIME / "RT-10/RELEASE-SEQUENCE-MEMBERSHIP-01", "run.py", None),
        ("nondeterministic_outcomes", FORMAL / "NONDETERMINISTIC-REFINEMENT-01", "run.py", "Refinement.lean"),
        ("callback_observer", LANGUAGE / "CALLBACK-INVARIANT-01", "run.py", "Bounds.lean"),
    )
    paths = [path for _, path, _, _ in cases] + [
        FORMAL / "THREE-SEMANTICS-01", OLD_PROTOTYPE / "rt03_reference.py", OLD_PROTOTYPE / "rt03_smallstep.py",
    ]
    archive = execute(["git", "archive", BASELINE, *paths], ROOT)
    result = {}
    with TemporaryDirectory(prefix="llmlang-declared-observations-") as directory:
        root = Path(directory)
        with tar_open(fileobj=BytesIO(archive)) as bundle:
            bundle.extractall(root, filter="data")
        for label, relative, runner, proof in cases:
            fixture = root / relative
            result[label] = {"fixture": relative.as_posix()}
            if proof:
                tried = execute(["lean", "-DwarningAsError=true", proof], fixture)
                if tried != (fixture / "axioms.txt").read_bytes():
                    raise AssertionError(f"Lean transcript mismatch: {label}")
                result[label]["axioms_sha256"] = digest(tried)
            actual = execute([sys.executable, "-B", runner], fixture)
            if actual != (fixture / "evidence.json").read_bytes():
                raise AssertionError(f"Scoped comparison mismatch: {label}")
            result[label]["evidence_sha256"] = digest(actual)
    return result


def run():
    return {
        "schema": "llmlang-declared-observations/1", "baseline": BASELINE,
        "python": platform.python_version(), "scope": SCOPE,
        "sources_sha256": {name: digest((HERE / name).read_bytes())
                           for name in ("run.py", "Profile.lean", "axioms.txt")},
        "replays": replays(), "fixture_axes": FIELDS, "counts": profile_matrix(),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
