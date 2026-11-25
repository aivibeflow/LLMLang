#!/usr/bin/env python3
"""Compare arithmetic proof roles against one checked-byte experiment."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
INPUTS = range(-128, 128)
MIN_SUM, MAX_SUM = -256, 254
INITIAL = -999
TRACE = {"-": 0, "W": 1, "WC": 2, "CW": 3}


@dataclass(frozen=True)
class Variant:
    upper: int = 127
    success_trace: str = "WC"
    error_trace: str = "-"
    error_writes_sum: bool = False

    def observe(self, sum_):
        if -128 <= sum_ <= self.upper:
            return 0, sum_, self.success_trace
        return 1, sum_ if self.error_writes_sum else INITIAL, self.error_trace


VARIANTS = {
    "base": Variant(),
    "inclusive_overflow": Variant(upper=128),
    "restored_error_store": Variant(error_trace="W"),
    "omitted_callback": Variant(success_trace="W"),
    "reordered_callback": Variant(success_trace="CW"),
    "sum_stored_on_error": Variant(error_trace="W", error_writes_sum=True),
}
BASE = VARIANTS["base"]


def call(args, root, stdin=None):
    result = subprocess.run(args, cwd=root, input=stdin, text=True, capture_output=True,
                            check=True, timeout=45)
    return result.stdout


def breaks(variant):
    return {MIN_SUM, -128, variant.upper + 1, MAX_SUM + 1}


def check_partition(variant, cuts):
    if not cuts or cuts != sorted(set(cuts)) or cuts[0] != MIN_SUM or cuts[-1] != MAX_SUM + 1:
        return {"status": "invalid-cover", "endpoints": []}
    if not (breaks(BASE) | breaks(variant)) <= set(cuts):
        return {"status": "missing-branch-boundary", "endpoints": []}
    endpoints = sorted({point for lo, end in zip(cuts, cuts[1:]) for point in (lo, end - 1)})
    witness = next((total for total in endpoints if BASE.observe(total) != variant.observe(total)), None)
    return {"status": "refuted" if witness is not None else "checked",
            "endpoints": endpoints, "counterexample_sum": witness}


def smt_values(variant):
    inside = f"(and (<= (- 128) s) (<= s {variant.upper}))"
    error_cell = "s" if variant.error_writes_sum else "(- 999)"
    return [f"(ite {inside} 0 1)", f"(ite {inside} s {error_cell})",
            f"(ite {inside} {TRACE[variant.success_trace]} {TRACE[variant.error_trace]})"]


def smt_query(variant):
    overflow = "(or (< s (- 128)) (> s 127))"
    reference = [f"(ite {overflow} 1 0)", f"(ite {overflow} (- 999) s)",
                 f"(ite {overflow} {TRACE['-']} {TRACE['WC']})"]
    unequal = [f"(distinct {expected} {actual})" for expected, actual in zip(reference, smt_values(variant))]
    return "\n".join([
        "(set-logic QF_LIA)", "(set-option :produce-models true)", "(declare-const a Int)",
        "(declare-const b Int)", "(define-fun s () Int (+ a b))",
        "(assert (and (<= (- 128) a) (<= a 127) (<= (- 128) b) (<= b 127)))",
        "(assert (or " + " ".join(unequal) + "))", "(check-sat)", "",
    ])


def checked_model(text, variant):
    pattern = r"\(\(a\s*((?:\(-\s*\d+\))|(?:-?\d+))\)\s*\(b\s*((?:\(-\s*\d+\))|(?:-?\d+))\)\)"
    found = re.fullmatch(pattern, text.strip())
    if not found:
        raise AssertionError(text)
    values = tuple(int(re.sub(r"[()\s]", "", token)) for token in found.groups())
    left, right = values
    if left not in INPUTS or right not in INPUTS or BASE.observe(left + right) == variant.observe(left + right):
        raise AssertionError((variant, values))
    return values


def solvers():
    records = {}
    for backend in (("cvc5", "--lang=smt2"), ("z3", "-smt2", "-in")):
        by_variant = {}
        for name, variant in VARIANTS.items():
            query = smt_query(variant)
            base = name == "base"
            full = query + ("" if base else "(get-value (a b))\n") + "(exit)\n"
            answer, _, rest = call(backend, HERE, full).partition("\n")
            if answer != ("unsat" if base else "sat"):
                raise AssertionError((backend, name, answer, rest))
            if base and rest:
                raise AssertionError(rest)
            by_variant[name] = {"raw_status": answer, "smt_sha256": sha256(full.encode()).hexdigest(),
                                "validated_witness": None if base else checked_model(rest, variant)}
        records[backend[0]] = {
            "version": call([backend[0], "--version"], HERE).splitlines()[0],
            "checks": by_variant,
        }
    return records


def native():
    reference = []
    coverage = {}
    for name, variant in VARIANTS.items():
        count = Counter()
        for left, right in product(INPUTS, repeat=2):
            sum_ = left + right
            expected = BASE.observe(sum_)
            observed = variant.observe(sum_)
            count["complete"] += expected != observed
            count["status_and_cell"] += expected[:2] != observed[:2]
            count["status"] += expected[0] != observed[0]
            reference.append(" ".join(map(str, observed)) + "\n")
        coverage[name] = count
    expected_output = "".join(reference)
    hashes = {}
    with TemporaryDirectory(prefix="llmlang-checked-byte-") as tmp:
        root = Path(tmp)
        for flag in ("-O0", "-O2"):
            call(["gcc", flag, "-std=c17", "-Wall", "-Wextra", "-Werror", HERE / "probe.c", "-o", "probe"], root)
            observed = call(["./probe"], root)
            if expected_output != observed:
                raise AssertionError(f"Native observation differs from the declared variant model at {flag}")
            hashes[flag] = sha256(observed.encode()).hexdigest()
    return {
        "gcc": call(["gcc", "--version"], HERE).splitlines()[0],
        "rows_per_optimization": len(reference), "profile_sha256": hashes, "differences": coverage,
    }


def run():
    specialized = {name: check_partition(variant, sorted(breaks(BASE) | breaks(variant)))
                   for name, variant in VARIANTS.items()}
    if any(row["status"] != ("checked" if key == "base" else "refuted") for key, row in specialized.items()):
        raise AssertionError(specialized)
    coarse = check_partition(VARIANTS["inclusive_overflow"], [MIN_SUM, MAX_SUM + 1])
    if coarse["status"] != "missing-branch-boundary":
        raise AssertionError(coarse)
    if any(BASE.observe(s) != VARIANTS["inclusive_overflow"].observe(s) for s in (MIN_SUM, MAX_SUM)):
        raise AssertionError("The incomplete endpoint control should miss the boundary defect")
    return {
        "schema": "llmlang-checked-byte-proof-routes/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "probe.c", "Regions.lean", "axioms.txt")},
        "input_pairs": len(INPUTS) ** 2, "initial_cell": INITIAL, "native": native(),
        "solvers": solvers(), "specialized": specialized, "coarse_partition_control": coarse,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
