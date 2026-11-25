"""Compare two-node state forwarding under read-only and mutating callbacks."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
VALUES = (0, 1, 2, 25, 127, 65535, 1 << 31, (1 << 32) - 1)
POLICIES = ("reload", "guarded", "forward", "premature")


def run(*cmd, stdin=None):
    proc = subprocess.run(cmd, text=True, input=stdin, capture_output=True, check=True, timeout=30)
    if proc.stderr:
        raise ValueError(proc.stderr)
    return proc.stdout.strip()


def oracle(produced, amount, modifies, replacement):
    current = replacement if modifies else produced
    if current >= amount:
        balance = current - amount
        return (1, balance, produced, balance)
    return (0, current, produced)


def compare(executable):
    cases = tuple(product(VALUES, VALUES, (0, 1), VALUES))
    expected = [oracle(*case) for case in cases]
    data = "".join(" ".join(map(str, case)) + "\n" for case in cases)
    evidence = {}
    for policy in POLICIES:
        rows = [tuple(map(int, line.split())) for line in run(executable, policy, stdin=data).splitlines()]
        errors = Counter({"read-only": 0, "mutates": 0})
        witnesses = {}
        for case, want, got in zip(cases, expected, rows, strict=True):
            if want != got:
                mode = "mutates" if case[2] else "read-only"
                errors[mode] += 1
                witnesses.setdefault(mode, {"input": case, "reference": want, "actual": got})
        if policy in {"reload", "guarded"} and sum(errors.values()):
            raise ValueError((policy, errors))
        if policy == "forward" and not (errors["read-only"] == 0 < errors["mutates"]):
            raise ValueError((policy, errors))
        if policy == "premature" and not errors["read-only"]:
            raise ValueError((policy, errors))
        evidence[policy] = {"differing_rows": errors, "first_witnesses": witnesses,
                            "rows_sha256": sha256(json.dumps(rows).encode()).hexdigest()}
    return {"cases": len(cases), "policies": evidence}


def lean_record(lean):
    result = run(lean, "-DwarningAsError=true", HERE / "Forward.lean")
    expected = [
        "'exact_slot_guard_suffices' depends on axioms: [propext]",
        "'rejects_after_retaining_callback' depends on axioms: [propext]",
    ]
    if result.splitlines() != expected:
        raise ValueError(result)
    return {"version": run(lean, "--version"), "axioms": expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True, type=Path)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipts = {}
    versions = {}
    with TemporaryDirectory(prefix="rt13-forward-") as temp:
        executable = Path(temp) / "probe"
        gcc_headers = run("gcc", "-print-file-name=include")
        for name, compiler, header_options in (("gcc", "gcc", ()), ("clang", args.clang, ("-isystem", gcc_headers))):
            versions[name] = run(compiler, "--version").splitlines()[0]
            for optimization in ("-O0", "-O2"):
                run(compiler, "-std=c17", optimization, "-Wall", "-Wextra", "-Werror",
                    *header_options, HERE / "probe.c", "-o", executable)
                receipts[f"{name}/{optimization}"] = compare(executable)
    first = next(iter(receipts.values()))
    if any(variant != first for variant in receipts.values()):
        raise ValueError("compiler profiles disagree")
    evidence = {
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "probe.c", "Forward.lean")},
        "lean": lean_record(args.lean), "compilers": versions, "confirmed_profiles": sorted(receipts),
        "observations_per_profile": first,
    }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
