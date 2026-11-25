#!/usr/bin/env python3
"""Compare exact provider sets for joint contracts and two incorrect shortcuts."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
INPUTS = (0, 1)
VALUES = tuple(range(4))
ALL_OBSERVATIONS = 15


@dataclass(frozen=True)
class Contract:
    eligible: int
    first: int
    second: int

    def raw(self, value):
        return (self.first, self.second)[value]

    def active(self, value):
        return bool(self.eligible & (1 << value))

    def effective(self, value):
        return self.raw(value) if self.active(value) else ALL_OBSERVATIONS

    def fields(self):
        return self.eligible, self.first, self.second


def execute(args, root):
    return subprocess.run(args, cwd=root, check=True, capture_output=True, text=True, timeout=30).stdout


def native():
    expected = "".join(f"{index} {input_} {code & 1} {code >> 1}\n"
                       for index in range(16) for input_ in INPUTS
                       for code in ((index >> (2 * input_)) & 3,))
    hashes = {}
    families = {}
    with TemporaryDirectory(prefix="llmlang-joint-contracts-") as temp:
        root = Path(temp)
        for flags in ("-O0", "-O2"):
            execute(["gcc", flags, "-std=c17", "-Wall", "-Wextra", "-Werror", HERE / "probe.c", "-o", "probe"], root)
            observed = execute(["./probe"], root)
            if observed != expected:
                raise AssertionError((flags, observed, expected))
            hashes[flags] = sha256(observed.encode("ascii")).hexdigest()
            for row in observed.splitlines():
                index, input_, value, event = map(int, row.split())
                families.setdefault(index, {})[input_] = (value, event)
    return families, hashes


def candidates(families):
    outputs = {}
    for cap in product(range(16), repeat=2):
        identity = 0
        for index, function in families.items():
            if all(cap[input_] & (1 << (result + 2 * event))
                   for input_, (result, event) in function.items()):
                identity |= 1 << index
        outputs[cap] = identity
    return outputs


def make_witness(left, right, implementation=None):
    return {"left": left.fields(), "right": right.fields(), "implementation": implementation}


def first_provider(providers):
    return (providers & -providers).bit_length() - 1


def summarize():
    families, binary_hashes = native()
    provider_tables = candidates(families)
    contracts = [Contract(*record) for record in product(range(4), range(16), range(16))]
    effective = {contract: (contract.effective(0), contract.effective(1)) for contract in contracts}
    supporters = {contract: provider_tables[caps] for contract, caps in effective.items()}
    counts = Counter()
    witnesses = {}
    for left, right in product(contracts, repeat=2):
        left_allowed, right_allowed = effective[left], effective[right]
        joint = supporters[left] & supporters[right]
        pointwise = (left_allowed[0] & right_allowed[0], left_allowed[1] & right_allowed[1])
        if provider_tables[pointwise] != joint or bool(joint) != all(pointwise):
            raise AssertionError((left, right))
        counts["ordered_contract_pairs"] += 1
        if supporters[left] and supporters[right]:
            counts["individually_feasible_pairs"] += 1
            if not joint:
                counts["individually_feasible_but_disjoint_pairs"] += 1
                witnesses.setdefault("no_common_provider", make_witness(left, right))
        if joint:
            counts["jointly_feasible_pairs"] += 1

        common_inputs = left.eligible & right.eligible
        any_input = left.eligible | right.eligible
        overlap_only = provider_tables[(
            pointwise[0] if common_inputs & 1 else ALL_OBSERVATIONS,
            pointwise[1] if common_inputs & 2 else ALL_OBSERVATIONS,
        )]
        raw_intersection = provider_tables[(
            left.first & right.first if any_input & 1 else ALL_OBSERVATIONS,
            left.second & right.second if any_input & 2 else ALL_OBSERVATIONS,
        )]
        extra, missed = overlap_only & ~joint, joint & ~raw_intersection
        if joint & ~overlap_only or raw_intersection & ~joint:
            raise AssertionError("The candidate shortcuts changed direction")
        if extra:
            counts["overlap_only_false_admission_pairs"] += 1
            counts["overlap_only_false_provider_admissions"] += extra.bit_count()
            witnesses.setdefault("overlap_hides_obligation", make_witness(left, right, first_provider(extra)))
        if missed:
            counts["unconditional_intersection_false_refusal_pairs"] += 1
            counts["unconditional_intersection_false_provider_refusals"] += missed.bit_count()
            witnesses.setdefault("inactive_postcondition_restricts", make_witness(left, right, first_provider(missed)))

    for contract, bits in supporters.items():
        if bits.bit_count() > 1:
            counts["contracts_with_multiple_conforming_providers"] += 1
        active = [value for value in INPUTS if contract.active(value)]
        admitted = [index for index in families if bits & (1 << index)]
        if any(all(families[a][state][0] == families[b][state][0] for state in active)
               and any(families[a][state][1] != families[b][state][1] for state in active)
               for a, b in combinations(admitted, 2)):
            counts["contracts_allow_same_values_with_distinct_effects"] += 1
    witness_contract = Contract(3, 5, 10)
    silent, emitted = families[4], families[14]
    if not all(supporters[witness_contract] & (1 << provider) for provider in (4, 14)):
        raise AssertionError("Both concrete providers must satisfy the result-only contract")
    witnesses["exact_operation_can_allow_distinct_effects"] = {
        "contract": witness_contract.fields(), "provider_4": silent, "provider_14": emitted,
    }
    return {
        "schema": "llmlang-joint-contracts/1", "python": platform.python_version(),
        "gcc": execute(["gcc", "--version"], HERE).splitlines()[0],
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Contracts.lean", "axioms.txt", "probe.c")},
        "contracts": len(contracts), "implementations": len(families),
        "native_rows_per_optimization": len(families) * len(INPUTS),
        "native_rows_sha256": binary_hashes, "counts": counts, "witnesses": witnesses,
    }


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
