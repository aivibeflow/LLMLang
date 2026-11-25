#!/usr/bin/env python3
"""Compare analogue rankings with exact contract coverage and call binding."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import random
import sys

HERE = Path(__file__).resolve().parent
JOINT = HERE.parent / "JOINT-CONTRACTS-01"
sys.path.insert(0, str(JOINT))
from run import Contract, candidates, execute, native

PROFILE = "toy-c17-event-observations/1"
SEED = 290
CATALOGS_PER_QUERY = 32
CATALOG_SIZE = 12


@dataclass(frozen=True)
class Binding:
    operation: str
    implementation: int
    contract: str
    profile: str
    epoch: int


def identity(parts):
    return sha256(json.dumps(parts, separators=(",", ":")).encode("ascii")).hexdigest()


def atoms(contract):
    return sum(contract.raw(value) << (4 * value) for value in (0, 1) if contract.active(value))


def ranking_score(required, provided):
    combined = required | provided
    return Fraction((required & provided).bit_count(), combined.bit_count()) if combined else Fraction(1)


def refines(required, provided):
    if (required.eligible & provided.eligible) != required.eligible:
        return False
    return all(not required.active(value) or (provided.raw(value) & ~required.raw(value)) == 0
               for value in (0, 1))


def exact_dispatch(operation, contract, current, requested_provider, receipt):
    required_scope = Binding(operation, requested_provider, contract, PROFILE, 1)
    if current.operation != operation:
        return "wrong-operation"
    if current != required_scope:
        return "wrong-binding"
    if receipt != required_scope:
        return "unverified-binding"
    return requested_provider


def compare():
    providers, native_sha = native()
    tables = candidates(providers)
    universe = [Contract(*fields) for fields in product(range(4), range(16), range(16))]
    provider_bits = {item: supported for item in universe
                     if (supported := tables[(item.effective(0), item.effective(1))])}
    catalog = list(provider_bits)
    requests = [Contract(*fields) for fields in product((1, 2, 3), (1, 4, 5), (2, 8, 10))]
    atom_map = {item: atoms(item) for item in catalog}
    rng = random.Random(SEED)
    counts = Counter()
    witnesses = {}

    for requested in requests:
        operation = identity(["explicit-call", requested.fields()])
        contract_id = identity(["requested-contract", requested.fields()])
        valid = provider_bits[requested]
        chosen = (valid & -valid).bit_length() - 1
        fixed = Binding(operation, chosen, contract_id, PROFILE, 1)
        required_atoms = atom_map[requested]
        for _ in range(CATALOGS_PER_QUERY):
            subset = rng.sample(catalog, CATALOG_SIZE)
            ranking = sorted(subset, key=lambda item: (-ranking_score(required_atoms, atom_map[item]), item.fields()))
            flags = []
            for provided in ranking:
                whole_domain_covered = (requested.eligible & provided.eligible) == requested.eligible
                every_native_provider_refines = not (provider_bits[provided] & ~valid)
                exact = refines(requested, provided)
                if exact != (whole_domain_covered and every_native_provider_refines):
                    raise AssertionError((requested, provided))
                flags.append(exact)
            counts["scored_candidates"] += len(ranking)
            counts["catalogs"] += 1
            counts["catalogs_with_refining_candidate"] += any(flags)
            counts["unsafe_top_one"] += not flags[0]
            counts["refining_candidate_outside_top_three"] += any(flags) and not any(flags[:3])
            if any(flags) and not flags[0]:
                counts["unsafe_top_one_with_refining_alternative"] += 1
                candidate = ranking[flags.index(True)]
                witnesses.setdefault("unsafe_rank_before_admissible", {
                    "request": requested.fields(), "rank_one": ranking[0].fields(),
                    "rank_one_score": str(ranking_score(required_atoms, atom_map[ranking[0]])),
                    "first_refining_candidate": candidate.fields(),
                    "refining_rank": flags.index(True) + 1,
                    "first_refining_score": str(ranking_score(required_atoms, atom_map[candidate])),
                })

            start = exact_dispatch(operation, contract_id, fixed, chosen, fixed)
            for proposed in (ranking[0], ranking[-1]):
                analogue_bits = provider_bits[proposed]
                analogue_provider = (analogue_bits & -analogue_bits).bit_length() - 1
                exact = exact_dispatch(operation, contract_id, fixed, chosen, fixed)
                if start != exact or exact != chosen:
                    raise AssertionError("Advisory ranking changed the exact call")
                unsafe = (valid & (1 << analogue_provider)) == 0
                counts["advisory_dispatch_comparisons"] += 1
                counts["unfiltered_analogue_violates_required_contract"] += unsafe
                counts["unfiltered_analogue_changes_exact_provider"] += analogue_provider != chosen

    if not witnesses or not counts["refining_candidate_outside_top_three"]:
        raise AssertionError("The corpus did not exercise the configured ranking safeguards")
    requested = requests[-1]
    op = identity(["explicit-call", requested.fields()])
    cid = identity(["requested-contract", requested.fields()])
    current = Binding(op, 4, cid, PROFILE, 1)
    if provider_bits[requested] & (1 << 4) == 0 or provider_bits[requested] & (1 << 14) == 0:
        raise AssertionError("Fixture providers must both satisfy the named contract")
    cases = (
        ("exact", current, 4, current, 4),
        ("same_contract_wrong_operation", replace(current, operation="other"), 4, current, "wrong-operation"),
        ("same_operation_different_provider", current, 14, current, "wrong-binding"),
        ("stale_receipt", current, 4, replace(current, epoch=0), "unverified-binding"),
        ("wrong_profile", current, 4, replace(current, profile="different"), "unverified-binding"),
        ("correct_provider_for_different_contract", current, 4, replace(current, contract="other"), "unverified-binding"),
    )
    controls = {}
    for name, binding, provider, receipt, wanted in cases:
        result = exact_dispatch(op, cid, binding, provider, receipt)
        if result != wanted:
            raise AssertionError((name, result, wanted))
        controls[name] = {"result": result, "binding": asdict(binding), "receipt": asdict(receipt)}
    return {
        "schema": "llmlang-analogue-dispatch/1", "python": platform.python_version(),
        "gcc": execute(["gcc", "--version"], HERE).splitlines()[0],
        "sources_sha256": {
            "run.py": sha256(Path(__file__).read_bytes()).hexdigest(),
            "joint_contract_runner": sha256((JOINT / "run.py").read_bytes()).hexdigest(),
            "native_provider_probe": sha256((JOINT / "probe.c").read_bytes()).hexdigest(),
        },
        "profile": PROFILE, "seed": SEED, "request_contracts": len(requests),
        "catalog_size": CATALOG_SIZE, "candidate_contracts": len(catalog),
        "native_comparison_sha256": native_sha, "counts": counts, "witnesses": witnesses,
        "dispatch_controls": controls,
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
