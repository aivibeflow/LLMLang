#!/usr/bin/env python3
"""Validate resource Contract IR and check exact Lean evidence for a finite schema."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
import os
from shutil import which
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

PROFILE = "abstract-selection/1"
UNITS = {"work": "step", "peak_live": "entry"}
RELATION = {"n": "input.length", "k": "selected.count", "k_max": "n"}
SUBJECT = """def modelWork (n k : Nat) : Nat := 1 + 2 * n + k
def modelPeak (_ k : Nat) : Nat := k

"""
THEOREMS = {"work": "modelWork", "peak_live": "modelPeak"}
ROLE = "successful-materialization"


class Refusal(ValueError):
    pass


def fingerprint(data):
    return sha256(data).hexdigest()


def digest(data):
    return fingerprint(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())


def require(condition, message):
    if not condition:
        raise Refusal(message)


def shape(record, keys):
    require(isinstance(record, dict) and set(record) == set(keys), "invalid shape")


def natural(value):
    return type(value) is int and value >= 0


def validate(contract):
    shape(contract, ("ir", "profile", "aggregation", "outcome", "size", "bounds"))
    require(contract["ir"] == "resource-contract/1", "unsupported schema")
    require(contract["profile"] == PROFILE, "unsupported cost model")
    require(contract["aggregation"] == "worst-case", "unsupported aggregation")
    require(contract["outcome"] == ROLE, "unsupported outcome")

    size = contract["size"]
    shape(size, ("relation", "min_n"))
    require(size["relation"] == RELATION and natural(size["min_n"]), "unsupported size domain")

    shape(contract["bounds"], UNITS)
    for metric, bound in contract["bounds"].items():
        shape(bound, ("unit", "constant", "n", "k"))
        require(bound["unit"] == UNITS[metric], "metric unit mismatch")
        require(all(natural(bound[field]) for field in ("constant", "n", "k")), "invalid bound")
    return digest(contract)


def sample():
    return {
        "ir": "resource-contract/1", "profile": PROFILE,
        "aggregation": "worst-case", "outcome": ROLE,
        "size": {"relation": RELATION.copy(), "min_n": 0},
        "bounds": {
            "work": {"unit": "step", "constant": 1, "n": 2, "k": 1},
            "peak_live": {"unit": "entry", "constant": 0, "n": 0, "k": 1},
        },
    }


def build_source(contract, metric):
    validate(contract)
    require(metric in THEOREMS, "unsupported metric")
    goal = contract["bounds"][metric]
    threshold = contract["size"]["min_n"]
    function = THEOREMS[metric]
    return SUBJECT + (
        f"theorem verified (n k : Nat) (_bounded : k ≤ n) (_size : {threshold} ≤ n) :\n"
        f"    {function} n k ≤ {goal['constant']} + {goal['n']} * n + {goal['k']} * k := by\n"
        f"  unfold {function}\n"
        f"  omega\n"
        f"#print axioms verified\n"
    )


def request(contract, metric, checker):
    return {
        "contract": validate(contract),
        "metric": metric,
        "subject": fingerprint(SUBJECT.encode()),
        "assumptions": digest(contract["size"]),
        "checker": checker,
        "generated_proof": fingerprint(build_source(contract, metric).encode()),
    }


def check(work, lean, contract, metric, checker):
    source = build_source(contract, metric)
    (work / "Generated.lean").write_text(source, encoding="utf-8")
    result = subprocess.run([lean, "-DwarningAsError=true", "Generated.lean"], cwd=work,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        assert "omega could not prove the goal" in result.stdout
        assert not result.stderr
        return None
    assert result.stdout == "'verified' depends on axioms: [propext, Quot.sound]\n"
    assert not result.stderr
    return {"request": request(contract, metric, checker), "kernel_log": fingerprint(result.stdout.encode())}


def admit(certificate, exact_request, authorized):
    return (certificate is not None and certificate["request"] == exact_request
            and digest(certificate) in authorized)


def forecast(bound, n, k):
    return bound["constant"] + bound["n"] * n + bound["k"] * k


def changed(contract, path, value):
    result = deepcopy(contract)
    destination = result
    for segment in path[:-1]:
        destination = destination[segment]
    destination[path[-1]] = value
    return result


def exercise(work, lean):
    version = subprocess.check_output([lean, "--version"], cwd=work, text=True).strip()
    executable = Path(which(lean)).resolve()
    checker = digest({"tool": version, "binary": fingerprint(executable.read_bytes()),
                      "audit": ["propext", "Quot.sound"]})
    target = sample()
    candidates = {
        "exact": target,
        "domain-restricted": changed(target, ("size", "min_n"), 1),
        "work-refinement": changed(target, ("bounds", "work", "k"), 0),
        "peak-refinement": changed(target, ("bounds", "peak_live", "k"), 0),
        "uniform-n-envelope": changed(
            changed(target, ("bounds", "work"), {"unit": "step", "constant": 1, "n": 3, "k": 0}),
            ("bounds", "peak_live"), {"unit": "entry", "constant": 0, "n": 1, "k": 0},
        ),
    }
    results = {}
    certificates = {}
    for name, contract in candidates.items():
        row = {}
        for metric in UNITS:
            evidence = check(work, lean, contract, metric, checker)
            expected = (name, metric) not in {("work-refinement", "work"), ("peak-refinement", "peak_live")}
            assert (evidence is not None) == expected
            if evidence is not None:
                certificates[name, metric] = evidence
            row[metric] = "kernel-checked" if evidence is not None else "kernel-refused"
        results[name] = row

    original = certificates["exact", "work"]
    authorized = {digest(original)}
    expected = request(target, "work", checker)
    assert admit(original, expected, authorized)
    substitutions = {
        "different-aggregation": (("aggregation",), "expected"),
        "different-outcome": (("outcome",), "timeout"),
        "work-unit-entry": (("bounds", "work", "unit"), "entry"),
        "peak-unit-step": (("bounds", "peak_live", "unit"), "step"),
        "wrong-domain-measure": (("size", "relation", "k"), "cache.entries"),
        "wrong-profile": (("profile",), "abstract-selection/2"),
        "boolean-threshold": (("size", "min_n"), False),
        "negative-cost": (("bounds", "work", "constant"), -1),
        "unknown-size": (("size", "unvalidated_size"), 0),
        "unknown-bound-variable": (("bounds", "work", "m"), 5),
    }
    schema_controls = {}
    for name, (path, value) in substitutions.items():
        try:
            validate(changed(target, path, value))
        except Refusal as error:
            schema_controls[name] = str(error)
        else:
            raise AssertionError(name)
    assert validate(dict(reversed(list(target.items())))) == validate(target)
    assert validate(changed(target, ("bounds", "work"), dict(reversed(list(target["bounds"]["work"].items()))))) == validate(target)

    mismatches = {
        name: expected | {name: digest(name + " revision")}
        for name in ("subject", "checker", "generated_proof", "assumptions", "contract")
    }
    mismatches["metric"] = request(target, "peak_live", checker)
    mismatches["size-restriction"] = request(candidates["domain-restricted"], "work", checker)
    mismatches["weaker-envelope"] = request(candidates["uniform-n-envelope"], "work", checker)
    for mutation in mismatches.values():
        assert not admit(original, mutation, authorized)
    assert not admit(original, expected, set())
    other = original | {"kernel_log": digest("missing kernel transcript")}
    assert not admit(other, expected, authorized)

    domain_rows = 0
    for n, k in product(range(65), repeat=2):
        if k > n:
            continue
        selected = [index for index in range(n) if index < k]
        model = {"work": 1 + 2 * n + len(selected), "peak_live": len(selected)}
        for metric, count in model.items():
            assert count == forecast(target["bounds"][metric], n, k)
            assert count <= forecast(candidates["uniform-n-envelope"]["bounds"][metric], n, k)
        domain_rows += 1
    return {
        "format": "resource-contract-ir-01", "checker": version, "baseline_contract": target,
        "kernel_results": results, "baseline_evidence": original,
        "schema_controls": schema_controls, "evidence_mismatches": sorted(mismatches),
        "untrusted_certificate_refused": True, "substituted_log_refused": True,
        "finite_size_pairs": domain_rows,
    }


if __name__ == "__main__":
    lean = os.environ.get("LEAN", "lean")
    with TemporaryDirectory(prefix="llmlang-resource-ir-") as work:
        result = exercise(Path(work), lean)
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
