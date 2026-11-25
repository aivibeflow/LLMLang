#!/usr/bin/env python3
"""Compare native resource gates against a separate symbolic cost model."""

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
MODELS = ("direct", "grouped", "repeated", "erase")
OPTIMIZATIONS = ("-O0", "-O2")
WEIGHTS = (3, 7)
THEOREMS = (
    "direct_fast", "grouped_fast", "grouped_improves", "grouped_slow",
    "repeated_fast_fails", "grouped_units", "erased_units_fail",
)


def digest(data):
    return sha256(data).hexdigest()


def key(data):
    return digest(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())


def run(args, work, *, data=None):
    result = subprocess.run(args, cwd=work, text=True, capture_output=True, input=data, check=True)
    assert not result.stderr
    return result.stdout


def observations(root, optimization, weight, gcc):
    work = root / f"{optimization[1:]}-{weight}"
    work.mkdir()
    flags = ("-std=c11", "-Wall", "-Wextra", "-Werror", optimization)
    (work / "driver.c").write_bytes((HERE / "driver.c").read_bytes())
    (work / "provider.c").write_bytes((HERE / "provider.c").read_bytes())
    run([gcc, *flags, "-c", "driver.c", "-o", "driver.o"], work)
    run([gcc, *flags, f"-DUNIT_WEIGHT={weight}", "-c", "provider.c", "-o", "provider.o"], work)
    run([gcc, "driver.o", "provider.o", "-o", "measure"], work)
    trials = list(product(range(len(MODELS)), range(64), (-9, 0, 9)))
    stdout = run(["./measure"], work, data="".join(f"{kind} {n} {value}\n" for kind, n, value in trials))
    rows = list(zip(trials, stdout.splitlines(), strict=True))
    for (kind, n, value), line in rows:
        native_calls = (n, (n + 1) // 2, 2 * n, 0)[kind]
        native_units = 0 if kind == 3 else n
        assert tuple(map(int, line.split())) == (
            n * value, native_calls, native_units, 2 + native_calls + weight * native_units,
        )
    return {
        "optimization": optimization, "test_count": len(rows),
        "provider": digest((work / "provider.o").read_bytes()),
        "driver": digest((work / "driver.o").read_bytes()),
        "subject": digest((work / "measure").read_bytes()),
        "observations": digest(stdout.encode()),
    }


@dataclass(frozen=True)
class Scope:
    subject: str
    caller: str
    provider: str
    optimization: str
    cost_profile: str
    provider_weight: int
    variant: str
    size_domain: str
    budget_coeff: int
    proof: str

    def identity(self):
        return key(vars(self))


def disposition(n, request, authority):
    if authority is None:
        return "unknown-foreign-cost", None
    weight, claimed = authority
    if claimed != request.identity() or weight != request.provider_weight:
        return "stale-evidence", None
    mode = request.variant
    units = 0 if mode == "erase" else n
    calls = (n, (n + 1) // 2, 2 * n, 0)[MODELS.index(mode)]
    measured_cost = 2 + calls + weight * units
    if units != n:
        return "observation-refused", measured_cost
    if measured_cost > 2 + request.budget_coeff * n:
        return "budget-refused", measured_cost
    return "admitted", measured_cost


def experiment(work):
    gcc = os.environ.get("CC", "gcc")
    lean = os.environ.get("LEAN", "lean")
    lean_source = (HERE / "Resource.lean").read_bytes()
    (work / "Resource.lean").write_bytes(lean_source)
    axiom_output = run([lean, "-DwarningAsError=true", "Resource.lean"], work)
    lines = [f"'{name}' depends on axioms: [propext, Quot.sound]" for name in THEOREMS]
    assert axiom_output.splitlines() == lines
    builds = {
        (opt, w): observations(work, opt, w, gcc)
        for opt, w in product(OPTIMIZATIONS, WEIGHTS)
    }
    for opt in OPTIMIZATIONS:
        assert builds[opt, 3]["driver"] == builds[opt, 7]["driver"]
        assert builds[opt, 3]["provider"] != builds[opt, 7]["provider"]
        assert builds[opt, 3]["subject"] != builds[opt, 7]["subject"]

    def scope(opt, weight, mode):
        row = builds[opt, weight]
        return Scope(
            row["subject"], row["driver"], row["provider"], opt,
            "fixed-2+foreign-entry-1+provider-unit/version-1", weight, mode, "nonnegative-n",
            4, digest(lean_source),
        )

    counts = {}
    for record, mode in product(builds, MODELS):
        opt, weight = record
        active = scope(opt, weight, mode)
        evidence = (weight, active.identity())
        count = {}
        for n in range(64):
            state, _ = disposition(n, active, evidence)
            expected = "admitted"
            if n > 0:
                if mode == "erase":
                    expected = "observation-refused"
                elif weight == 7 or mode == "repeated":
                    expected = "budget-refused"
            assert state == expected
            count[state] = count.get(state, 0) + 1
        counts[f"{opt}/{weight}/{mode}"] = count

    valid = scope("-O2", 3, "grouped")
    old = (3, valid.identity())
    selection = {}
    for n in range(64):
        options = [
            (cost, index, mode)
            for index, mode in enumerate(MODELS)
            for candidate in [scope("-O2", 3, mode)]
            for decision, cost in [disposition(n, candidate, (3, candidate.identity()))]
            if decision == "admitted"
        ]
        _, _, chosen = min(options)
        assert chosen == ("direct" if n < 2 else "grouped")
        selection[chosen] = selection.get(chosen, 0) + 1
    controls = {}
    changed_scopes = {
        "foreign-rebind": scope("-O2", 7, "grouped"),
        "target-configuration": scope("-O0", 3, "grouped"),
        "lowering-variant": replace(valid, variant="repeated"),
        "provider-weight": replace(valid, provider_weight=7),
        "budget": replace(valid, budget_coeff=3),
        "size-domain": replace(valid, size_domain="at-most-63"),
        "cost-profile": replace(valid, cost_profile="later-weight-table"),
        "proof": replace(valid, proof=digest(b"another proof")),
    }
    for name, new_scope in changed_scopes.items():
        controls[name], _ = disposition(19, new_scope, old)
    assert set(controls.values()) == {"stale-evidence"}
    unknown, _ = disposition(19, valid, None)
    assert unknown == "unknown-foreign-cost"
    rebound = scope("-O2", 7, "grouped")
    assert disposition(19, rebound, (7, rebound.identity()))[0] == "budget-refused"
    return {
        "format": "resource-aware-lowering-01",
        "gcc": run([gcc, "--version"], work).splitlines()[0],
        "lean": run([lean, "--version"], work).strip(),
        "lean_axioms": lines, "proof": digest(lean_source),
        "builds": list(builds.values()),
        "native_observations": sum(row["test_count"] for row in builds.values()),
        "regression_dispositions": counts, "selection": selection, "invalidation": controls,
        "unknown_foreign": unknown, "revalidated_rebind": "budget-refused",
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-resource-lowering-") as temporary:
        ledger = experiment(Path(temporary))
    text = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
