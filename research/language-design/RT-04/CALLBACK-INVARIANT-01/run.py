#!/usr/bin/env python3
"""Compare a boundary-only invariant with a callback-visible state invariant."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
VALUES = range(4)
FLAGS = tuple(product((0, 1), repeat=3))


def expected(before, after, lower_first, visible, rollback):
    if before[0] > before[1] or after[0] > after[1]:
        return (2, *before, -1, -1)
    midpoint = (after[0], before[1]) if lower_first else (before[0], after[1])
    callback = midpoint if visible else (-1, -1)
    return (rollback, *(before if rollback else after), *callback)


def execute(args, root, data=None):
    return subprocess.run(args, cwd=root, input=data, check=True, capture_output=True,
                          text=True, timeout=30).stdout


def run():
    counts = Counter()
    witnesses = {}
    requests = []
    results = []
    for old_lower, old_upper, new_lower, new_upper in product(VALUES, repeat=4):
        before, after = (old_lower, old_upper), (new_lower, new_upper)
        admitted = old_lower <= old_upper and new_lower <= new_upper
        if admitted:
            counts["valid_endpoint_pairs"] += 1
            lower_safe = new_lower <= old_upper
            upper_safe = old_lower <= new_upper
            if not (lower_safe or upper_safe):
                raise AssertionError((before, after))
            counts["both_orders_safe"] += lower_safe and upper_safe
            counts["exactly_one_order_safe"] += lower_safe != upper_safe
        for lower_first, visible, rollback in FLAGS:
            observation = expected(before, after, lower_first, visible, rollback)
            status, raw_low, raw_high, callback_low, callback_high = observation
            counts["profiles"] += 1
            if not admitted:
                counts["refused_profiles"] += 1
                if status != 2 or (callback_low, callback_high) != (-1, -1):
                    raise AssertionError((before, after, observation))
            else:
                counts["admitted_profiles"] += 1
                if raw_low > raw_high:
                    raise AssertionError((before, after, observation))
                satisfies_yield = not visible or callback_low <= callback_high
                guard = not visible or (lower_safe if lower_first else upper_safe)
                if guard != satisfies_yield:
                    raise AssertionError((before, after, observation))
                if not satisfies_yield:
                    counts["final_only_false_admissions"] += 1
                    counts["false_admissions_with_rollback"] += bool(rollback)
                    key = "rollback" if rollback else "return_success"
                    witnesses.setdefault(key, {"before": before, "target": after,
                                               "lower_first": bool(lower_first), "observed": observation})
            requests.append((*before, *after, lower_first, visible, rollback))
            results.append(observation)
    if counts["exactly_one_order_safe"] + counts["both_orders_safe"] != counts["valid_endpoint_pairs"]:
        raise AssertionError(counts)
    if not counts["false_admissions_with_rollback"]:
        raise AssertionError("Missing rollback discriminator")

    stdin = "".join(" ".join(map(str, row)) + "\n" for row in requests)
    oracle = "".join(" ".join(map(str, row)) + "\n" for row in results)
    profiles = {}
    with TemporaryDirectory(prefix="llmlang-callback-invariant-") as tmp:
        root = Path(tmp)
        for optimization in ("-O0", "-O2"):
            execute(["gcc", optimization, "-std=c17", "-Wall", "-Wextra", "-Werror",
                     HERE / "probe.c", "-o", "probe"], root)
            rows = execute(["./probe"], root, stdin)
            if rows != oracle:
                raise AssertionError(f"Native callback observations differ at {optimization}")
            profiles[optimization] = sha256(rows.encode("ascii")).hexdigest()
    return {
        "schema": "llmlang-callback-invariant/1", "python": platform.python_version(),
        "gcc": execute(["gcc", "--version"], HERE).splitlines()[0],
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "probe.c", "Bounds.lean", "axioms.txt")},
        "native_rows_sha256": profiles, "counts": counts, "witnesses": witnesses,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
