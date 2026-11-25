#!/usr/bin/env python3
"""Derive exact typed proof dependencies from stored SPG call occurrences."""

from dataclasses import asdict, replace
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
REVISION = "21800dd85aa37721e2748001d307033be0b2fac1"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
RT32 = "research/formal-verification/RT-32"
CALLS = f"{RT32}/GENERATED-CALL-01"
CLOSURE = f"{RT32}/TRANSITIVE-CLOSURE-01"
PRODUCER = "synthetic-checked-receipt-fixture"
TOOLCHAIN = "ordered-int-pdg-fixture/1"


def nodes_in(term, path=()):
    match term:
        case ["literal" | "argument", _]:
            return
        case ["add" | "sub" | "eq", left, right]:
            yield from nodes_in(left, (*path, 1))
            yield from nodes_in(right, (*path, 2))
        case ["emit", _, tail]:
            yield from nodes_in(tail, (*path, 2))
        case ["if", test, yes, no]:
            for index, child in enumerate((test, yes, no), 1):
                yield from nodes_in(child, (*path, index))
        case [("op" | "pin") as mode, ref, *operands] if type(ref) is int and len(operands) == 1:
            yield path, mode, ref
            yield from nodes_in(operands[0], (*path, 2))
        case _:
            raise ValueError(f"Outside typed graph occurrence profile: {term!r}")


def build(graph, entry, calls, proof):
    inventory = {}
    sites = {}
    active = set()
    root_scope = graph.snapshot.root_hash

    def register(claim, *requires):
        ordered = tuple(sorted(set(requires)))
        if claim in inventory and inventory[claim] != ordered:
            raise ValueError(f"One claim has conflicting dependencies: {claim}")
        inventory[claim] = ordered
        return claim

    def visit(implementation):
        root = proof.Claim("closure", proof.digest([root_scope, implementation]), "all-dependencies")
        if implementation in active:
            raise ValueError("Recursive discharge is outside this fixture")
        if root in inventory:
            return root
        active.add(implementation)
        _, contract, _, body, refs = calls.read_function(graph, implementation)
        source = register(proof.Claim("source", implementation, "source-correspondence"))
        premises, discharges = [], []
        indexes = set()
        for path, mode, index in nodes_in(body):
            if index in indexes or not 0 <= index < len(refs):
                raise ValueError("Reference positions must identify distinct occurrences")
            indexes.add(index)
            identity = refs[index]["external" if mode == "op" else "exact_call"]
            binding, provider = calls.binding(graph, identity) if mode == "op" else (None, identity)
            provider_op, provided, *_ = calls.read_function(graph, provider)
            if mode == "op" and provider_op != identity:
                raise ValueError("Binding does not match the requested operation")
            caller_site = (implementation, path, mode, identity, provided)
            context = (root_scope, caller_site, binding, provider)
            premise = register(proof.Claim("call-premise", proof.digest(caller_site), provided))
            binding_claim = register(proof.Claim("binding", proof.digest(context), "exact-binding"))
            target = visit(provider)
            provider_contract = register(proof.Claim("body-proof", provider, provided), target)
            discharge = register(proof.Claim("call-discharge", proof.digest(context), provided),
                                 premise, binding_claim, provider_contract)
            premises.append(premise)
            discharges.append(discharge)
            sites[discharge] = {"caller": implementation, "path": path, "mode": mode,
                                "provider": provider, "provider_contract": provided,
                                "premise": premise.subject, "binding": binding}
        if indexes != set(range(len(refs))):
            raise ValueError("Unaccounted SPG call reference")
        active.remove(implementation)
        theorem = register(proof.Claim("modular-theorem", implementation, contract),
                           source, *premises)
        return register(root, theorem, *discharges)

    root = visit(entry)
    return root, inventory, sites


def tickets(proof, inventory):
    return {claim: proof.Receipt(claim, requires, PRODUCER, TOOLCHAIN, "checked",
                                proof.digest(asdict(claim))) for claim, requires in inventory.items()}


def closure(proof, root, inventory, receipts):
    return proof.evaluate(root, inventory, receipts, producer=PRODUCER, toolchain=TOOLCHAIN)


def result(report):
    return {"closed": report.evidence_digest is not None,
            "reasons": sorted({reason for _, reason in report.blockers})}


def compare(calls, proof):
    base = calls.dispatch_program()
    paired = (*base.contracts["forward"], ("first", "last", "first", "last"))
    base = replace(base, contracts={**base.contracts, "forward": paired},
                   bindings={**base.bindings, "other": "other"})
    repeated = calls.replace_body(base, "late", 'op("provider", n) + op("provider", n)')
    mixed = calls.replace_body(base, "late", 'op("provider", n) + pin("primary", n)')
    nested = calls.replace_body(base, "late", 'op("provider", op("provider", n))')
    rebound = replace(mixed, bindings={**base.bindings, "provider": "alternate"})
    deep = calls.replace_body(repeated, "primary",
                              'emit("first", emit("last", op("other", n)))')
    edited = calls.replace_body(deep, "other", "n - 8")
    corpus = {
        "repeated": (repeated, ((1,), (2,)), 1, 2, lambda n: 2 * (n + 1)),
        "mixed": (mixed, ((1,), (2,)), 1, 2, lambda n: 2 * (n + 1)),
        "nested": (nested, ((), (2,)), 1, 2, lambda n: n + 2),
        "rebound_mixed": (rebound, ((1,), (2,)), 2, 2, lambda n: 2 * n + 3),
        "transitive": (deep, ((1,), (2,)), 1, 3, lambda n: 2 * (n - 2)),
        "transitive_edit": (edited, ((1,), (2,)), 1, 3, lambda n: 2 * (n - 8)),
    }
    runs = {}
    saved = {}
    controls = {}
    for name, (program, paths, provider_count, sites_count, expected) in corpus.items():
        graph = calls.compile_program(program)
        entry = graph.snapshot.mapping["implementation:late"]
        root, inventory, sites = build(graph, entry, calls, proof)
        selected = sorted((site for site in sites.values() if site["caller"] == entry),
                          key=lambda site: site["path"])
        if (tuple(site["path"] for site in selected) != paths or
            len({site["provider"] for site in selected}) != provider_count or
            len(sites) != sites_count):
            raise AssertionError((name, selected, sites))
        receipts = tickets(proof, inventory)
        full = closure(proof, root, inventory, receipts)
        if not full.evidence_digest:
            raise AssertionError((name, full))
        observations = []
        for input_value in (-4, -1, 0, 1, 4):
            observed = calls.observe(graph, "late", (input_value,))
            assert observed == (expected(input_value), ("first", "last", "first", "last"))
            observations.append((input_value, *observed))
        runs[name] = {"spg_root": graph.snapshot.root_hash, "entry": entry,
                      "root_proof": root.subject, "closure": full.evidence_digest,
                      "node_count": len(inventory), "sites": selected,
                      "transitive_site_count": len(sites), "observations": observations}
        saved[name] = root, inventory, receipts, sites

    root, expected, receipts, sites = saved["repeated"]
    site = min(sites)
    reduced = {**expected, root: tuple(child for child in expected[root] if child != site)}
    dropped_edge = {**receipts, root: tickets(proof, reduced)[root]}
    controls["occurrence_inference_from_receipts"] = result(closure(proof, root, reduced, dropped_edge))
    controls["missing_occurrence_exact_inventory"] = result(closure(proof, root, expected, dropped_edge))
    controls["missing_occurrence_receipt"] = result(
        closure(proof, root, expected, {key: value for key, value in receipts.items() if key != site}))
    wrong_claim = replace(receipts[site], toolchain="different-checker")
    controls["stale_checker"] = result(closure(proof, root, expected, {**receipts, site: wrong_claim}))
    root, expected, receipts, sites = saved["transitive"]
    entry = runs["transitive"]["entry"]
    leaf = next(claim for claim, scope in sites.items() if scope["caller"] != entry)
    controls["missing_transitive_discharge"] = result(
        closure(proof, root, expected, {key: value for key, value in receipts.items() if key != leaf}))
    new_root, new_expected, *_ = saved["transitive_edit"]
    controls["old_snapshot_after_transitive_edit"] = result(closure(proof, new_root, new_expected, receipts))
    assert controls["occurrence_inference_from_receipts"]["closed"]
    assert not any(row["closed"] for key, row in controls.items()
                   if key != "occurrence_inference_from_receipts")
    assert runs["transitive"]["entry"] == runs["transitive_edit"]["entry"]
    assert runs["transitive"]["closure"] != runs["transitive_edit"]["closure"]
    return runs, controls


def main():
    with tempfile.TemporaryDirectory() as directory:
        archive = subprocess.check_output(["git", "archive", REVISION, PROTOTYPE, CALLS, CLOSURE])
        with open_tar(fileobj=BytesIO(archive), mode="r:") as extracted:
            extracted.extractall(directory, filter="data")
        sys.path.insert(0, str(Path(directory) / CLOSURE))
        import closure as proof
        spec = spec_from_file_location("pinned_spg_calls", Path(directory) / CALLS / "run.py")
        calls = module_from_spec(spec)
        spec.loader.exec_module(calls)
        cases, negative = compare(calls, proof)

    print(json.dumps({
        "schema": "llmlang-spg-pdg-occurrences/1", "python": platform.python_version(),
        "archive_revision": REVISION,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Occurrences.lean", "axioms.txt")},
        "cases": cases, "negative_controls": negative,
    }, indent=2))


if __name__ == "__main__":
    main()
