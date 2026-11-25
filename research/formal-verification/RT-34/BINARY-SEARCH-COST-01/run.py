#!/usr/bin/env python3
"""Validate binary-search event counts and integer size bounds independently."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIZES = (*range(65), 127, 128, 129, 255, 256, 257)
SHAPES = ("distinct", "duplicates")
OUTCOMES = ("miss", "hit", "nonhalving", "stalled")
LEAN_COMMIT = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"


def call(arguments, cwd=None):
    program = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True,
                             timeout=60, check=False)
    if program.returncode or program.stderr:
        raise RuntimeError(program.stdout + program.stderr)
    return program.stdout


def digest(content):
    return sha256(content).hexdigest()


def collect_audits(lean):
    result = call([lean, "-DwarningAsError=true", str(HERE / "SearchCost.lean")])
    pattern = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[(.*)\])$")
    audits = {}
    for line in result.splitlines():
        match = pattern.fullmatch(line)
        if match is None:
            raise ValueError(line)
        name, values = match.groups()
        audits[name] = values.split(", ") if values else []
    assert len(audits) == 7
    assert all(set(names) <= {"propext", "Classical.choice", "Quot.sound"} for names in audits.values())
    return audits


def native_outputs(compiler):
    profile_results = []
    levels = ("0", "3")
    with TemporaryDirectory(prefix="llmlang-binary-search-") as directory:
        root = Path(directory)
        for level in levels:
            call([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}",
                  str(HERE / "search.c"), "-o", "search"], root)
            profile_results.append(call(["./search"], root))
    assert profile_results[0] == profile_results[1]
    return levels, profile_results[0]


def partner_arrays():
    return {(shape, size): {2 * (i if shape == "distinct" else i // 3) for i in range(size)}
            for size, shape in product(SIZES, SHAPES)}


def recover_observations(output):
    native = iter(output.splitlines())
    possible = partner_arrays()
    sizes = {}
    policies = {shape: Counter() for shape in SHAPES}
    singleton = {}
    inputs = 0
    for (shape, size), elements in possible.items():
        budget = size.bit_length()
        per_size = {"size": size, "shape": shape, "probe_budget": budget,
                    "max_probes": 0, "max_conditions": 0}
        for target in range(-1, 2 * size + 2):
            inputs += 1
            is_member = target in elements
            for flag in (0, 1):
                source_shape, *payload = next(native).split()
                n, current_target, mutated, status, probes, tests, last_size, next_size = map(int, payload)
                assert (shape, size, target, flag) == (source_shape, n, current_target, mutated)
                decision = OUTCOMES[status]
                assert tests == 2 * probes - (decision == "hit")
                if not flag:
                    assert decision == ("hit" if is_member else "miss")
                    assert probes <= budget <= size
                    assert next_size == 0
                    per_size["max_probes"] = max(per_size["max_probes"], probes)
                    per_size["max_conditions"] = max(per_size["max_conditions"], tests)
                    stats = policies[shape]
                    stats["corrected_search_cases"] += 1
                    stats["log_floor_under_counts"] += probes > max(0, budget - 1)
                    stats["linear_bound_loose"] += size > probes
                    stats["one_condition_per_probe_under_counts"] += tests > probes
                    if target == -1:
                        assert decision == "miss" and probes == budget and tests == 2 * budget
                else:
                    policies[shape][f"mutant_{decision}"] += 1
                    if decision == "nonhalving":
                        assert last_size // 2 < next_size < last_size
                    elif decision == "stalled":
                        assert next_size == last_size == 1
                        singleton.setdefault(shape, {"size": size, "target": target,
                                                     "interval_before": last_size,
                                                     "interval_after": next_size})
                    else:
                        assert decision == ("hit" if is_member else "miss")
        assert per_size["max_probes"] == budget
        assert per_size["max_conditions"] == 2 * budget
        sizes[f"{shape}/{size}"] = per_size
    unsorted = next(native).split()
    assert unsorted == ["unsorted", "4", "8", "0", "0", "2", "4", "1", "0"]
    assert next(native, None) is None
    assert all(row["mutant_stalled"] and row["mutant_nonhalving"] for row in policies.values())
    return inputs, sizes, policies, singleton


def replay(compiler, lean):
    lean_version = call([lean, "--version"]).strip()
    if LEAN_COMMIT not in lean_version:
        raise ValueError("Expected Lean 4.36.0")
    audits = collect_audits(lean)
    levels, output = native_outputs(compiler)
    inputs, sizes, policies, singleton = recover_observations(output)
    return {
        "schema": "llmlang-binary-search-cost/1",
        "compiler": call([compiler, "--version"]).splitlines()[0],
        "lean": lean_version, "python": platform.python_version(),
        "source_sha256": {name: digest((HERE / name).read_bytes())
                          for name in ("search.c", "SearchCost.lean", "run.py")},
        "optimization_levels": levels, "input_pairs_per_profile": inputs,
        "native_rows": (2 * inputs + 1) * len(levels),
        "native_stdout_sha256_per_profile": digest(output.encode()),
        "theorems": audits, "profiles": policies, "singleton_witness": singleton,
        "unsorted_control": {"values": [8, 2, 4, 6], "target": 8, "member": True,
                             "native_result": "miss", "probes": 2, "certified_budget": 3},
        "sizes": sizes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args()
    ledger = replay(args.cc, args.lean)
    sizes = ledger.pop("sizes")
    print(json.dumps(ledger, indent=2).removesuffix("\n}") + ',\n  "sizes": {')
    print(",\n".join(f"    {json.dumps(key)}: {json.dumps(row)}" for key, row in sizes.items()))
    print("  }\n}")


if __name__ == "__main__":
    main()
