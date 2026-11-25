#!/usr/bin/env python3
"""Check earlier absence in compiler header lookup and cache reuse."""

from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
DIRECTORIES = ("a", "b", "c")
BYTES = """#include <llmlang_probe_choice.h>
#include <stdio.h>
int main(void) { return printf("%d\\n", CHOICE) < 0; }
"""
HEADER = "llmlang_probe_choice.h"
STATES = tuple(product((None, 0, 1), repeat=len(DIRECTORIES)))
ORDERS = tuple(permutations(DIRECTORIES))


def resolve(state, order):
    index = next((key for key in order if state[key] is not None), None)
    return (index, state[index]) if index else None


def native(compiler):
    reports = {}
    env = dict(os.environ)
    for variable in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "DEPENDENCIES_OUTPUT"):
        env.pop(variable, None)
    with tempfile.TemporaryDirectory() as build:
        root = Path(build)
        (root / "main.c").write_text(BYTES)
        for entry in DIRECTORIES:
            (root / entry).mkdir()
        for config in STATES:
            state = dict(zip(DIRECTORIES, config, strict=True))
            for directory, value in state.items():
                path = root / directory / HEADER
                if value is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(f"#define CHOICE {value}\n")
            for order in ORDERS:
                expected = resolve(state, order)
                source = subprocess.run(
                    [compiler, "-std=c11", "-O2", "-MMD", "-MF", "active.d",
                     *(f"-I{path}" for path in order), "main.c", "-o", "app"],
                    cwd=root, env=env, text=True, capture_output=True)
                if expected is None:
                    if source.returncode == 0 or HEADER not in source.stderr:
                        raise AssertionError((order, config, source.stderr))
                    reports[config, order] = {"status": "missing-header"}
                    continue
                if source.returncode or source.stderr:
                    raise AssertionError((order, config, source.stderr))
                directory, number = expected
                observed = subprocess.check_output([str(root / "app")], cwd=root,
                                                   text=True, env=env).strip()
                expected_deps = ["main.c", f"{directory}/{HEADER}"]
                deps = (root / "active.d").read_text().partition(":")[2].split()
                if observed != str(number) or deps != expected_deps:
                    raise AssertionError((order, config, observed, deps))
                reports[config, order] = {"status": "checked", "selection": expected,
                                          "artifact": sha256((root / "app").read_bytes()).hexdigest(),
                                          "depfile": deps}
    return reports


def compare(reports):
    counts, witnesses = Counter(), {}
    for (old, order), source in reports.items():
        if source["status"] != "checked":
            continue
        winner, previous = source["selection"]
        index = DIRECTORIES.index(winner)
        prefix = order[:order.index(winner) + 1]
        mask_required = sum(1 << DIRECTORIES.index(directory) for directory in prefix)
        for new in STATES:
            dest = reports[new, order]
            same_selection = dest.get("selection") == source["selection"]
            same_artifact = dest.get("artifact") == source["artifact"]
            reused_by_positive = new[index] == previous
            exact_prefix = all(new[DIRECTORIES.index(directory)] == old[DIRECTORIES.index(directory)]
                               for directory in prefix)
            counts["same_command_pairs"] += 1
            if reused_by_positive:
                counts["positive_only_reuses"] += 1
                counts["positive_only_stale_selection"] += not same_selection
                counts["positive_only_stale_artifact"] += not same_artifact
                if not same_artifact:
                    witnesses.setdefault("old_depfile_wrong_artifact",
                                         {"old": old, "new": new, "order": order,
                                          "old_result": source, "new_result": dest})
            if exact_prefix != same_selection or exact_prefix and not same_artifact:
                raise AssertionError((old, new, order, exact_prefix, dest))
            counts["exact_lookup_reuses"] += exact_prefix
            for available in range(1 << len(DIRECTORIES)):
                complete = available & mask_required == mask_required
                counts["availability_cases"] += 1
                if complete and exact_prefix:
                    assert same_selection and same_artifact
                    counts["complete_exact_reuses"] += 1
                elif not complete:
                    counts["fallback_for_unknown"] += 1
                    counts["unknown_where_previous_file_still_matches"] += reused_by_positive
                    counts["fallback_avoids_wrong_artifact"] += reused_by_positive and not same_artifact
                else:
                    counts["rebuild_for_changed_lookup"] += 1
    assert witnesses
    return counts, witnesses


if __name__ == "__main__":
    compiler = os.environ.get("CC", "gcc")
    artifacts = native(compiler)
    counts, witnesses = compare(artifacts)
    print(json.dumps({
        "schema": "llmlang-ordered-header-lookup-fallback/1", "python": platform.python_version(),
        "gcc": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Lookup.lean", "axioms.txt")},
        "compiler_runs": len(artifacts),
        "successful_native_runs": sum(result["status"] == "checked" for result in artifacts.values()),
        "native_records_sha256": sha256(json.dumps(
            [(config, order, row) for (config, order), row in artifacts.items()],
            separators=(",", ":"), sort_keys=True).encode()).hexdigest(),
        "counts": counts, "witnesses": witnesses,
    }, indent=2))
