#!/usr/bin/env python3
"""Compare coherent and independent reads of a declared environment pair."""

from collections import Counter
from hashlib import sha256
from itertools import combinations_with_replacement, product
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
GENERATIONS = range(5)
VALUES = tuple(product(range(2), repeat=2))
SCHEDULES = tuple(combinations_with_replacement(GENERATIONS, 4))
PROFILES = {"O0": ("-O0",), "O2-ubsan": ("-O2", "-fsanitize=undefined",
                                        "-fno-sanitize-recover=all")}


def pack(pair):
    left, right = pair
    return 2 * left + right


def compare():
    rows = sha256()
    native_inputs = []
    native_outputs = []
    counts = Counter()
    witnesses = {}
    for images in product(VALUES, repeat=len(GENERATIONS)):
        encoded = tuple(map(pack, images))
        for before, left_at, right_at, after in SCHEDULES:
            pair = images[left_at][0], images[right_at][1]
            same_origin = left_at == right_at
            interval = images[before:after + 1]
            coherent_value = pair in interval
            policies = {
                "independent": True,
                "full_epoch": before == after,
                "modulo_2": before % 2 == after % 2,
                "modulo_4": before % 4 == after % 4,
                "field_origin": same_origin,
                "pinned": True,
            }
            counts["cases"] += 1
            for policy, accepts in policies.items():
                counts[f"{policy}_accepted"] += accepts
                if accepts:
                    returned = images[before] if policy == "pinned" else pair
                    counts[f"{policy}_mixed_origins"] += policy != "pinned" and not same_origin
                    counts[f"{policy}_value_without_coherent_generation"] += returned not in interval
                    if returned not in interval:
                        witnesses.setdefault(policy, {
                            "images": images, "schedule": [before, left_at, right_at, after],
                            "returned_pair": returned,
                        })
            native_row = (pack(pair), encoded[before], *map(int, (
                policies["full_epoch"], policies["modulo_2"], policies["modulo_4"],
                policies["field_origin"],
            )))
            native_inputs.append(" ".join(map(str, (*encoded, before, left_at, right_at, after))))
            native_outputs.append(" ".join(map(str, native_row)))
            rows.update(bytes((*encoded, before, left_at, right_at, after, *native_row,
                               same_origin, coherent_value)))

    assert counts["full_epoch_mixed_origins"] == counts["field_origin_mixed_origins"] == 0
    assert counts["pinned_mixed_origins"] == 0
    assert witnesses.keys() == {"independent", "modulo_2", "modulo_4"}
    return counts, witnesses, rows, native_inputs, native_outputs


def check_native(inputs, expected):
    compiler = os.environ.get("CC", "gcc")
    native = {}
    with tempfile.TemporaryDirectory() as build:
        for profile, flags in PROFILES.items():
            executable = Path(build) / "pair"
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", *flags,
                            str(HERE / "pair.c"), "-o", str(executable)], check=True)
            run = subprocess.run([str(executable)], input="\n".join(inputs) + "\n",
                                 capture_output=True, text=True, check=True)
            result = run.stdout.splitlines()
            if result != expected or run.stderr:
                raise AssertionError(f"Native comparison failed under {profile}")
            native[profile] = {"rows": len(result),
                               "stdout_sha256": sha256(run.stdout.encode()).hexdigest()}
    return native


def main():
    counts, witnesses, rows, inputs, expected = compare()
    print(json.dumps({
        "schema": "llmlang-coherent-environment/1",
        "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Environment.lean", "pair.c", "axioms.txt")},
        "schedule_order": ["before_epoch", "left_read", "right_read", "after_epoch"],
        "generations": len(GENERATIONS),
        "schedules_per_timeline": len(SCHEDULES),
        "counts": counts,
        "witnesses": witnesses,
        "rows_sha256": rows.hexdigest(),
        "native": check_native(inputs, expected),
    }, indent=2))


if __name__ == "__main__":
    main()
