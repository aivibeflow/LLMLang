#!/usr/bin/env python3
"""Compare requested environment inputs with the native observation boundary."""

from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
DELTA = "LLMLANG_FIXTURE_DELTA"
UNRELATED = "LLMLANG_FIXTURE_OTHER"
VALUES = (None, "", "0", "1", "2", "3", "4", "01", "one")
REQUESTS = tuple(product((0, 1), (0, 2, 15, 255)))
VALID = {"0", "1", "2", "3"}
POLICIES = ("subject_only", "successful_reads", "exact_scoped_read", "parsed_observation", "whole_environment")


def execute(args, root, env, *, source=None):
    return subprocess.run(args, cwd=root, env=env, input=source, capture_output=True,
                          text=True, timeout=30, check=True).stdout


def expected(enabled, value, raw):
    if not enabled:
        return ("ok", value, 0)
    if raw is None:
        return ("missing", 0, 1)
    if raw not in VALID:
        return ("malformed", 0, 1)
    return ("ok", (value + int(raw)) % 256, 1)


def keys(enabled, raw, unrelated):
    footprint = () if not enabled else (raw,)
    classification = () if not enabled else ("missing" if raw is None else raw if raw in VALID else "malformed",)
    return {
        "subject_only": (),
        "successful_reads": footprint if raw in VALID else (),
        "exact_scoped_read": footprint,
        "parsed_observation": classification,
        "whole_environment": (raw, unrelated),
    }


def compare():
    matrix = {request: [] for request in REQUESTS}
    for raw, unrelated in product(VALUES, ("legacy", "updated")):
        for request in REQUESTS:
            matrix[request].append({
                "env_value": raw, "unrelated_value": unrelated,
                "oracle": expected(*request, raw), "projections": keys(request[0], raw, unrelated),
            })
    compare_counts = {policy: Counter({"safe": 0, "stale": 0, "missed": 0}) for policy in POLICIES}
    for rows in matrix.values():
        for first, second in combinations(rows, 2):
            same = first["oracle"] == second["oracle"]
            for policy in POLICIES:
                equal = first["projections"][policy] == second["projections"][policy]
                counter = {(True, True): "safe", (True, False): "missed", (False, True): "stale"}.get((same, equal))
                if counter:
                    compare_counts[policy][counter] += 1
    native = {}
    with TemporaryDirectory(prefix="llmlang-environment-input-") as directory:
        root = Path(directory)
        shutil.copyfile(HERE / "probe.c", root / "probe.c")
        gcc = execute(["gcc", "--version"], root, BASE_ENV).splitlines()[0]
        source = "".join(f"{enabled} {value}\n" for enabled, value in REQUESTS)
        for level in ("-O0", "-O2"):
            execute(["gcc", level, "-std=c17", "-Wall", "-Wextra", "-Werror", "probe.c", "-o", "probe"],
                    root, BASE_ENV)
            outputs = []
            for raw, unrelated in product(VALUES, ("legacy", "updated")):
                environment = BASE_ENV | {UNRELATED: unrelated}
                if raw is not None:
                    environment[DELTA] = raw
                output = execute(["./probe"], root, environment, source=source)
                expected_output = "".join(f"{status} {value} {reads}\n"
                                          for status, value, reads in (expected(*req, raw) for req in REQUESTS))
                if output != expected_output:
                    raise AssertionError(f"Native observation boundary changed under {level} with {raw!r}")
                outputs.append(output)
            native[level] = sha256("".join(outputs).encode("ascii")).hexdigest()
    return {
        "schema": "llmlang-environment-boundary/1", "python": platform.python_version(), "gcc": gcc,
        "host": {"kernel": platform.release(), "machine": platform.machine(), "libc": platform.libc_ver()},
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "probe.c", "Boundary.lean", "axioms.txt")},
        "native_observations_per_profile": len(REQUESTS) * len(VALUES) * 2, "native_rows_sha256": native,
        "compared_pairs": sum(len(rows) * (len(rows) - 1) // 2 for rows in matrix.values()),
        "comparison": compare_counts,
        "reference": [{"request": request, "observations": rows} for request, rows in matrix.items()],
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
