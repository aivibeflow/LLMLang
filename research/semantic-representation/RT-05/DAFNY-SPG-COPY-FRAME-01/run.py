"""Check typed copy contracts, proof receipts and generated Python observations."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from render import PROFILES, canonical, render

HERE = Path(__file__).resolve().parent
SEED = 20261125
RELEASE = "a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179"
METHODS = {
    "SnapshotCopy": "full", "DirectedCopy": "full", "ForwardOnly": "forward", "SnapshotWithWrite": "weak",
}


def digest(value):
    return sha256(value).hexdigest()


def read_digest(path):
    return digest(path.read_bytes())


def run(directory, *args, data=None, check=True):
    return subprocess.run(list(map(str, args)), cwd=directory, input=data, check=check, text=True,
                          capture_output=True, timeout=90, env={**os.environ, "LC_ALL": "C"})


def verified(run_result):
    output = run_result.stdout + run_result.stderr
    match = re.search(r"Dafny program verifier finished with (\d+) verified, (\d+) errors?", output)
    if not match:
        raise ValueError((run_result.returncode, output))
    good, errors = (int(item) for item in match.groups())
    return {"verified": good, "errors": errors, "exit": run_result.returncode}


def generated_source(directory, graph, profile):
    source = directory / "Copy.dfy"
    source.write_text(render(graph, profile), encoding="utf-8")
    return source


def verify_profiles(directory, graph, cases, dafny, solvers, distribution):
    receipts = {}
    outputs = {}
    graph_digest = digest(canonical(graph))
    contracts = {method: digest(canonical(graph["contracts"][variant])) for method, variant in METHODS.items()}
    arguments = ("--cores", "1", "--verification-time-limit", "20")
    for profile in PROFILES:
        scratch = directory / profile
        scratch.mkdir()
        source = generated_source(scratch, graph, profile)
        solver_observations = {}
        for version, solver in solvers.items():
            result = verified(run(scratch, dafny, "verify", *arguments, "--solver-path", solver, source.name))
            assert result == {"verified": 8, "errors": 0, "exit": 0}
            receipt_inputs = {
                "schema": "llmlang-study-copy-frame-receipt/1",
                "typed_graph": graph_digest,
                "method_contracts": contracts,
                "surface_bindings": PROFILES[profile],
                "emitted_source": read_digest(source),
                "verifier_distribution": digest(canonical(distribution)),
                "solver": read_digest(solver),
                "proof_arguments": list(arguments),
                "assumptions": graph["assumptions"],
                "observation": result,
            }
            solver_observations[version] = {"inputs": receipt_inputs, "sha256": digest(canonical(receipt_inputs))}
        result = verified(run(scratch, dafny, "build", "--target", "py", *arguments, "--solver-path",
                              solvers["4.12.1"], source.name))
        assert result == {"verified": 8, "errors": 0, "exit": 0}
        generated = scratch / "Copy-py"
        python_files = {
            str(path.relative_to(generated)): read_digest(path) for path in sorted(generated.rglob("*.py"))
        }
        process = run(scratch, sys.executable, "-B", HERE / "observe.py", generated,
                      data=json.dumps(cases, separators=(",", ":")))
        outputs[profile] = json.loads(process.stdout)
        receipts[profile] = {"source_sha256": read_digest(source), "generated_python_sha256": python_files,
                             "solver_receipts": solver_observations}
    assert outputs["short"] == outputs["named"]
    assert receipts["short"]["source_sha256"] != receipts["named"]["source_sha256"]
    fingerprints = {record["sha256"] for profile in receipts.values()
                    for record in profile["solver_receipts"].values()}
    assert len(fingerprints) == len(PROFILES) * len(solvers)
    return receipts, outputs["short"]


def verify_controls(directory, graph, dafny, solvers):
    checks = {}
    for control, variant, field, marker in (
        ("no_overlap_premise", "forward", "requires", "assertion might not hold"),
        ("outside_frame_promised", "weak", "ensures", "a postcondition could not be proved"),
    ):
        changed = deepcopy(graph)
        if field == "requires":
            changed["contracts"][variant][field].remove("safe-forward-order")
        else:
            changed["contracts"][variant][field].append("outside-target-unchanged")
        branch = directory / control
        branch.mkdir()
        source = generated_source(branch, changed, "short")
        observations = {}
        for version, solver in solvers.items():
            process = run(branch, dafny, "verify", "--cores", "1", "--verification-time-limit", "20",
                          "--solver-path", solver, source.name, check=False)
            result = verified(process)
            assert result["errors"] > 0 and result["exit"] == 4, result
            assert marker in process.stdout, process.stdout
            observations[version] = result
        checks[control] = {"graph_sha256": digest(canonical(changed)), "source_sha256": read_digest(source),
                           "verifier_message": marker, "observations": observations}
    broken = deepcopy(graph)
    broken["effects"]["write_span"] = "source"
    try:
        render(broken, "short")
    except ValueError as error:
        assert str(error) == "unsupported effect footprint"
    else:
        raise AssertionError("unsupported effect projection was rendered")
    checks["foreign_write_region"] = {"result": "rejected before emission"}
    return checks


def corpus():
    cases = []
    for size in range(5):
        for words in product((-1, 0, 1), repeat=size):
            for length in range(size + 1):
                for source, target in product(range(size - length + 1), repeat=2):
                    cases.append([list(words), source, target, length])
    count = len(cases)
    rng = random.Random(SEED)
    for _ in range(256):
        size = rng.randrange(5, 33)
        words = [rng.randrange(-100, 101) for _ in range(size)]
        length = rng.randrange(size + 1)
        source, target = (rng.randrange(size - length + 1) for _ in range(2))
        cases.append([words, source, target, length])
    return cases, count


def trace_for(method, source, target, length):
    writes = [["write", i] for i in range(target, target + length)]
    reads = [["read", i] for i in range(source, source + length)]
    if method.startswith("Snapshot"):
        trace = reads + writes
        if method == "SnapshotWithWrite" and target > 0:
            trace += [["read", 0], ["write", 0]]
        return trace
    order = range(length - 1, -1, -1) if method == "DirectedCopy" and target > source else range(length)
    return [entry for i in order for entry in (reads[i], writes[i])]


def summarize(cases, outcomes):
    metrics = {method: Counter({"result_mismatches": 0, "outside_spans": 0, "trace_differences": 0})
               for method in METHODS}
    forward_scope = Counter()
    records = []
    for case, routes in zip(cases, outcomes, strict=True):
        before, source, target, length = case
        expected = before[:target] + before[source:source + length] + before[target + length:]
        safe_forward = target <= source or source + length <= target
        forward_scope["admitted" if safe_forward else "refused"] += 1
        observed = {}
        for method, (result, trace) in routes.items():
            assert trace == trace_for(method, source, target, length), (case, method, trace)
            if method in ("SnapshotCopy", "DirectedCopy") or (method == "ForwardOnly" and safe_forward):
                assert result == expected, (case, method, result)
            outside = any(not (source <= i < source + length if action == "read"
                               else target <= i < target + length) for action, i in trace)
            metrics[method]["result_mismatches"] += result != expected
            metrics[method]["outside_spans"] += outside
            metrics[method]["trace_differences"] += trace != routes["SnapshotCopy"][1]
            observed[method] = {"result": result, "in_spans": not outside,
                                "trace_sha256": digest(canonical(trace))}
        records.append({"input": case, "expected": expected, "forward_admitted": safe_forward, "routes": observed})
    witness_case = [[-1, 1, 0], 0, 1, 2]
    witness = outcomes[cases.index(witness_case)]
    assert metrics["ForwardOnly"]["result_mismatches"] > 0
    assert metrics["SnapshotWithWrite"]["outside_spans"] > 0
    return metrics, forward_scope, records, {"input": witness_case, "routes": witness}


def check_distribution(archive, dafny, solvers):
    files = {"dafny", "Dafny.dll", "DafnyCore.dll", "DafnyDriver.dll", "DafnyPipeline.dll", "DafnyPrelude.bpl"}
    files.update(path.relative_to(dafny.parent).as_posix() for path in solvers.values())
    with ZipFile(archive) as release:
        files.update(name.removeprefix("dafny/") for name in release.namelist()
                     if name.startswith("dafny/Boogie.") and name.endswith(".dll"))
        fingerprints = {}
        for name in sorted(files):
            actual = read_digest(dafny.parent / name)
            assert actual == digest(release.read(f"dafny/{name}")), name
            fingerprints[name] = actual
    return {"archive_sha256": RELEASE, "installed_files": fingerprints}


def compare(args, directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    archive = read_digest(args.archive)
    assert archive == RELEASE
    dafny = args.dafny.resolve()
    solvers = {version: dafny.parent / "z3" / "bin" / f"z3-{version}" for version in ("4.12.1", "4.14.1")}
    distribution = check_distribution(args.archive, dafny, solvers)
    graph = json.loads((HERE / "graph.json").read_text(encoding="utf-8"))
    cases, enumerated = corpus()
    receipts, outcomes = verify_profiles(directory, graph, cases, dafny, solvers, distribution)
    controls = verify_controls(directory, graph, dafny, solvers)
    metrics, forward_scope, records, witness = summarize(cases, outcomes)
    return {"schema": "llmlang-study-dafny-spg-copy-frame/1", "dafny": run(directory, dafny, "--version").stdout.strip(),
            "python": platform.python_version(), "distribution": distribution,
            "typed_graph_sha256": digest(canonical(graph)),
            "source_sha256": {name: read_digest(HERE / name) for name in
                              ("copy.dfy.in", "graph.json", "observe.py", "render.py", "run.py")},
            "receipt_profiles": receipts, "negative_controls": controls, "inputs": len(cases),
            "enumerated": enumerated, "seed": SEED, "metrics": metrics,
            "forward_scope": forward_scope, "witness": witness, "observations": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dafny", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    with TemporaryDirectory(prefix="llmlang-dafny-spg-copy-") as scratch:
        result = compare(parser.parse_args(), Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in observations))
    print("  ]\n}")
