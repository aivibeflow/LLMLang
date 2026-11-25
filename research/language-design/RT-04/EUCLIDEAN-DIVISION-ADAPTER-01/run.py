#!/usr/bin/env python3
"""Check exact adapter observations against independent integer formulas."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
INT_MIN, INT_MAX = -(1 << 31), (1 << 31) - 1
DIVIDENDS = tuple(range(-32, 33)) + (INT_MIN, INT_MIN + 1, -257, 257, INT_MAX - 1, INT_MAX)
DIVISORS = tuple(range(-2, 33)) + (INT_MIN, 127, 65537, INT_MAX)
MODES = ("verified", "return_euclidean", "stale_truncation_provider", "shift_only_quotient")


def run_command(args, root, stdin=None):
    result = subprocess.run(args, cwd=root, input=stdin, check=True, capture_output=True,
                            text=True, timeout=30)
    if result.stderr:
        raise AssertionError((args, result.stderr))
    return result.stdout


def truncated(n, d):
    magnitude = abs(n) // d
    q = -magnitude if n < 0 else magnitude
    return q, n - q * d


def expected(mode, n, d):
    if d <= 0:
        return 1, 0, 0, 0
    want_q, want_r = truncated(n, d)
    euclidean_q, euclidean_r = divmod(n, d)
    if mode == "stale_truncation_provider" and want_r < 0:
        return 2, 1, 0, 0
    if mode == "return_euclidean":
        return 0, 1, euclidean_q, euclidean_r
    if mode == "shift_only_quotient":
        return 0, 1, want_q, euclidean_r
    return 0, 1, want_q, want_r


def collect():
    results = []
    requests = []
    counts = Counter()
    differences = Counter()
    examples = {}
    for (mode_index, mode), n, d in product(enumerate(MODES), DIVIDENDS, DIVISORS):
        observation = expected(mode, n, d)
        reference = expected("verified", n, d)
        status, calls, q, r = observation
        if status == 0 and mode in ("verified", "stale_truncation_provider"):
            valid = q * d + r == n and -d < r < d and (r <= 0 if n < 0 else r >= 0)
            if not valid or calls != 1:
                raise AssertionError((mode, n, d, observation))
        if d <= 0:
            if observation[:2] != (1, 0):
                raise AssertionError("A nonpositive divisor called the provider")
            counts["precondition_refusals"] += 1
        counts["checked_rows"] += 1
        differences[mode] += reference != observation
        if reference != observation:
            examples.setdefault(mode, {"input": [n, d], "required": reference, "actual": observation})
        requests.append((mode_index, n, d))
        results.append(observation)
    if differences["verified"] or not all(differences[mode] for mode in MODES[1:]):
        raise AssertionError(differences)
    raw = "".join(" ".join(map(str, row)) + "\n" for row in requests)
    oracle = "".join(" ".join(map(str, row)) + "\n" for row in results)
    with TemporaryDirectory(prefix="llmlang-euclid-adapter-") as temp:
        root = Path(temp)
        profiles = {
            "O0": ("-O0",), "O2": ("-O2",),
            "ubsan": ("-O2", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"),
        }
        report = {}
        for name, optimization in profiles.items():
            run_command(["gcc", *optimization, "-std=c17", "-Wall", "-Wextra", "-Werror",
                         HERE / "probe.c", "-o", "probe"], root)
            output = run_command(["./probe"], root, raw)
            if output != oracle:
                raise AssertionError(f"Native signed division profile {name} differed")
            report[name] = sha256(output.encode("ascii")).hexdigest()
    return {
        "schema": "llmlang-euclidean-division-adapter/1", "python": platform.python_version(),
        "gcc": run_command(["gcc", "--version"], HERE).splitlines()[0],
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "probe.c", "Adapter.lean", "axioms.txt")},
        "input_pairs_per_variant": len(DIVIDENDS) * len(DIVISORS), "counts_per_profile": counts,
        "native_rows_sha256": report, "differences_from_required_outcome": differences,
        "counterexamples": examples,
    }


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
