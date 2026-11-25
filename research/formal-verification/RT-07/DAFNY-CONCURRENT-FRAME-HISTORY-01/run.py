"""Check Dafny frame gates and native increment histories."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RELEASE = "a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179"
BASES = (0, 1, 17, 1 << 31, (1 << 32) - 4)
ACTORS = (2, 3)
ROUTES = ("split", "rmw")
OPTIONS = ("--reads-clauses-on-methods", "--cores", "1", "--verification-time-limit", "20")


def run(directory, *args, data=None, check=True):
    return subprocess.run(list(map(str, args)), cwd=directory, input=data, text=True,
                          capture_output=True, check=check, timeout=60,
                          env={**os.environ, "LC_ALL": "C"})


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def proof_record(process):
    text = process.stdout + process.stderr
    match = re.search(r"Dafny program verifier finished with (\d+) verified, (\d+) errors?", text)
    if match is None:
        raise ValueError(text)
    good, errors = map(int, match.groups())
    return {"verified": good, "errors": errors, "exit": process.returncode}


def check_dafny(directory, dafny, solvers):
    results = {}
    for name, solver in solvers.items():
        prefix = (dafny, "verify", *OPTIONS, "--solver-path", solver)
        valid = run(directory, *prefix, "Frames.dfy")
        failed = run(directory, *prefix, "FrameControls.dfy", check=False)
        positive = proof_record(valid)
        negative = proof_record(failed)
        assert positive == {"verified": 9, "errors": 0, "exit": 0}
        assert negative == {"verified": 1, "errors": 4, "exit": 4}
        controls = (directory / "FrameControls.dfy").read_text(encoding="utf-8").splitlines()
        diagnostics = {}
        for number, frame in re.findall(r"^FrameControls\.dfy\((\d+),\d+\): Error: (reads|modifies) clause could not be proved to be empty",
                                        failed.stdout, flags=re.MULTILINE):
            match = re.search(r"\b(SharedRead|DefaultReadFrame|DistinctButShared|AssumedFunctionRead)\(", controls[int(number) - 1])
            assert match is not None
            diagnostics[match[1]] = frame
        assert diagnostics == {"SharedRead": "reads", "DefaultReadFrame": "reads",
                               "DistinctButShared": "modifies", "AssumedFunctionRead": "reads"}
        results[name] = {"positive": positive, "controls": negative, "diagnostics": diagnostics}
    assert results["4.12.1"] == results["4.14.1"]
    audit = directory / "audit.md"
    run(directory, dafny, "audit", "--reads-clauses-on-methods", "--report-file", audit, "Frames.dfy")
    contents = audit.read_text(encoding="utf-8")
    issues = [line for line in contents.splitlines() if "clause has" in line and "assume_concurrent" in line]
    assert len(issues) == 2 and all("AssumedSharedBump" in line for line in issues), contents
    assert any("Reads clause" in row for row in issues) and any("Modifies clause" in row for row in issues)
    explicit = [row.split("|")[3].strip() for row in issues]
    assert explicit == ["False", "False"]
    return results, {"rows": issues, "explicit_assumption_column": explicit, "sha256": sha(audit)}


def orders(actors):
    return [order for order in permutations(range(2 * actors))
            if all(order.index(2 * actor) < order.index(2 * actor + 1) for actor in range(actors))]


def simulate(base, actors, order, route):
    state = base
    old = [None] * actors
    replies = [None] * actors
    for event in order:
        actor, phase = divmod(event, 2)
        if phase == 0 and route == "split":
            old[actor] = state
        if phase == 1:
            if route == "rmw":
                old[actor] = state
            state = old[actor] + 1
            replies[actor] = state
    return {"state": state, "prior_values": old, "replies": replies}


def serial_witness(base, actors, events, outcome):
    """Return a legal abstract sequential order respecting completed-before-started calls."""
    if outcome["state"] != base + actors:
        return None
    elapsed = [(a, b) for a, b in product(range(actors), repeat=2)
               if events.index(2 * a + 1) < events.index(2 * b)]
    for abstract in permutations(range(actors)):
        positions = {actor: rank for rank, actor in enumerate(abstract)}
        if any(positions[a] >= positions[b] for a, b in elapsed):
            continue
        expected = [base + 1 + positions[actor] for actor in range(actors)]
        if expected == outcome["replies"]:
            return list(abstract)
    return None


def observe(directory, binary, route, cases, encoded):
    rows = run(directory, binary, route, data=encoded).stdout.splitlines()
    results = []
    for (base, actors, order), row in zip(cases, rows, strict=True):
        final, *items = map(int, row.split())
        assert len(items) == 2 * actors
        outcome = {"state": final, "prior_values": items[::2], "replies": items[1::2]}
        assert outcome == simulate(base, actors, order, route)
        outcome["serial_witness"] = serial_witness(base, actors, order, outcome)
        results.append(outcome)
    return results


def native(directory, gcc):
    schedules = {actors: orders(actors) for actors in ACTORS}
    assert {actors: len(order) for actors, order in schedules.items()} == {2: 6, 3: 90}
    cases = [(base, actors, order) for actors, samples in schedules.items() for base in BASES for order in samples]
    encoded = "\n".join(" ".join(map(str, (actors, base, *order))) for base, actors, order in cases) + "\n"
    profiles = {}
    for opt in (0, 2):
        binary = directory / f"counter-O{opt}"
        run(directory, gcc, "-std=c11", "-Wall", "-Wextra", "-Werror", f"-O{opt}", "-pthread",
            "counter.c", "-o", binary.name)
        profiles[f"O{opt}"] = {route: observe(directory, binary, route, cases, encoded) for route in ROUTES}
    assert profiles["O0"] == profiles["O2"]
    results = profiles["O0"]
    summary = {route: {actors: Counter() for actors in ACTORS} for route in ROUTES}
    rows = []
    for index, (base, actors, order) in enumerate(cases):
        routes = {route: results[route][index] for route in ROUTES}
        for route, observed in routes.items():
            values = summary[route][actors]
            values["histories"] += 1
            values["linearizable"] += observed["serial_witness"] is not None
            values["wrong_final_count"] += observed["state"] != base + actors
        rows.append({"base": base, "actors": actors, "events": order, "routes": routes})
    assert all(values["histories"] == values["linearizable"] for values in summary["rmw"].values())
    assert any(values["wrong_final_count"] > 0 for values in summary["split"].values())
    return rows, summary


def compare(args, directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    assert sha(args.archive) == RELEASE
    dafny = args.dafny.resolve()
    solvers = {version: dafny.parent / "z3" / "bin" / f"z3-{version}" for version in ("4.12.1", "4.14.1")}
    for name in ("Frames.dfy", "FrameControls.dfy", "counter.c"):
        shutil.copyfile(HERE / name, directory / name)
    proofs, audit = check_dafny(directory, dafny, solvers)
    histories, summary = native(directory, args.gcc)
    return {"schema": "llmlang-dafny-concurrent-frame-history/1", "release_sha256": RELEASE,
            "tools": {"dafny": run(directory, dafny, "--version").stdout.strip(),
                      "z3": {version: run(directory, solver, "--version").stdout.strip()
                             for version, solver in solvers.items()},
                      "gcc": run(directory, args.gcc, "--version").stdout.splitlines()[0],
                      "python": platform.python_version()},
            "inputs_sha256": {name: sha(HERE / name) for name in ("Frames.dfy", "FrameControls.dfy", "counter.c", "run.py")},
            "solver_sha256": {version: sha(solver) for version, solver in solvers.items()},
            "proof_options": list(OPTIONS), "proofs": proofs, "assumption_audit": audit,
            "base_values": BASES, "native_profiles": ["O0", "O2"], "metrics_per_profile": summary,
            "input_histories_per_route": len(histories), "histories": histories}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dafny", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--gcc", default="gcc")
    with TemporaryDirectory(prefix="llmlang-dafny-concurrent-frame-") as scratch:
        result = compare(parser.parse_args(), Path(scratch))
    histories = result.pop("histories")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "histories": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in histories))
    print("  ]\n}")
