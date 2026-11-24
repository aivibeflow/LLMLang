"""Compare completeness-aware closure with fixed-point and local-only policies."""

from dataclasses import asdict, replace
from itertools import product
import json

from closure import Claim, Receipt, digest, evaluate


PRODUCER = "fixture-checker"
TOOLCHAIN = "lean-profile-a"


def receipt(claim, adjacency, *, artifact="fixture-artifact"):
    return Receipt(claim, tuple(sorted(adjacency[claim])), PRODUCER, TOOLCHAIN, "checked", artifact)


def closure(root, adjacency, receipts):
    return evaluate(root, adjacency, receipts, producer=PRODUCER, toolchain=TOOLCHAIN)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fixed_point(inventory, present):
    complete = set()
    while True:
        updated = complete | {claim for claim in present if set(inventory[claim]) <= complete}
        if updated == complete:
            return complete
        complete = updated


def finite_oracle():
    nodes = tuple(Claim("proof", name, "p") for name in ("a", "b", "c"))
    possible = tuple(product(nodes, repeat=2))
    checked = closed = local_false_admission = 0
    for edge_mask in range(1 << len(possible)):
        adjacency = {node: [] for node in nodes}
        for index, (start, end) in enumerate(possible):
            if edge_mask & 1 << index:
                adjacency[start].append(end)
        all_receipts = {node: receipt(node, adjacency) for node in nodes}
        for flags in product((False, True), repeat=len(nodes)):
            local = {node: all_receipts[node] for node, available in zip(nodes, flags) if available}
            complete = fixed_point(adjacency, local)
            for root in nodes:
                exact = closure(root, adjacency, local).evidence_digest is not None
                require(exact == (root in complete), "Transitive closure differs from least fixed point")
                shallow = root in local and all(child in local for child in adjacency[root])
                checked += 1
                closed += exact
                local_false_admission += shallow and not exact
    return {"directed_graphs": 1 << len(possible), "receipt_coverage_masks": 1 << len(nodes),
            "root_cases": checked, "closed_cases": closed, "local_only_false_admissions": local_false_admission}


def provider(pinned_body, contract, *, assumption=False):
    profile = "integer/ordered-effects-v1"
    root = Claim("composition", f"caller-1@{pinned_body}", contract, profile)
    caller = Claim("modular-caller", "caller-1", contract, profile)
    body = Claim("body-proof", pinned_body, "provided-contract-1", profile)
    refinement = Claim("refinement-proof", pinned_body, contract, profile)
    source = Claim("source-correspondence", pinned_body, "source-to-model-1", profile)
    binding = Claim("binding", f"binding-{pinned_body}", contract, profile)
    premise = Claim("assumption", pinned_body, "foreign-model-adequate", profile)
    graph = {root: (caller, body, refinement, binding), caller: (), binding: (),
             body: (source, premise) if assumption else (source,), refinement: (source,),
             source: (), **({premise: ()} if assumption else {})}
    return root, graph, {claim.role: claim for claim in graph}


def scenarios():
    root, base, claims = provider("provider-1", "public-contract-1")
    original = {claim: receipt(claim, base) for claim in base}
    good = closure(root, base, original)
    require(good.evidence_digest is not None and len(good.evidence) == 6, "Diamond did not close")

    source = claims["source-correspondence"]
    body = claims["body-proof"]
    modular = claims["modular-caller"]
    changed_root, changed, names = provider("provider-2", "public-contract-1")
    new_body = names["body-proof"]
    new_receipts = {claim: receipt(claim, changed) for claim in changed if claim != new_body}
    new_receipts[new_body] = original[body]
    contract_root, changed_contract, fresh = provider("provider-1", "public-contract-2")
    stale_modular = {claim: receipt(claim, changed_contract) for claim in changed_contract}
    stale_modular[fresh["modular-caller"]] = original[modular]
    conditional_root, conditional, conditional_claims = provider("provider-1", "public-contract-1", assumption=True)
    premise = conditional_claims["assumption"]
    conditional_receipts = {c: receipt(c, conditional) for c in conditional if c != premise}
    discharged = closure(conditional_root, conditional,
                         {**conditional_receipts, premise: receipt(premise, conditional, artifact="premise-proof")})
    require(discharged.evidence_digest is not None, "Exact premise receipt did not close composition")

    def result_label(result):
        return sorted({reason for _, reason in result.blockers})

    negative = {
        "missing_grandchild": (root, base, {c: r for c, r in original.items() if c != source}, "pending-receipt"),
        "dropped_proof_edge": (root, base, {**original, body: replace(original[body], requires=())},
                               "incomplete-or-different-dependencies"),
        "changed_provider_body": (changed_root, changed, new_receipts, "wrong-claim"),
        "changed_public_contract": (contract_root, changed_contract, stale_modular, "wrong-claim"),
        "wrong_toolchain": (root, base, {**original, source: replace(original[source], toolchain="lean-profile-b")},
                            "wrong-provenance"),
        "wrong_producer": (root, base, {**original, body: replace(original[body], producer="unrecognized")},
                           "wrong-provenance"),
        "unsupported_source_binding": (root, base, {**original, source: replace(original[source], result="unsupported")},
                                        "unsupported"),
        "unresolved_premise": (conditional_root, conditional, conditional_receipts, "unresolved-assumption"),
        "missing_expected_subject": (root, {c: dependencies for c, dependencies in base.items() if c != source},
                                     original, "missing-expected-claim"),
    }
    cyclic = {**base, source: (body,)}
    negative["cyclic_discharge"] = (root, cyclic, {c: receipt(c, cyclic) for c in cyclic}, "cyclic-discharge")
    checked = {}
    for label, (target, inventory, receipts, expected) in negative.items():
        report = closure(target, inventory, receipts)
        require(report.evidence_digest is None and result_label(report) == [expected],
                f"Expected {expected} for {label}: {report}")
        checked[label] = expected

    rebound = {claim: receipt(claim, changed) for claim in changed}
    require(rebound[modular] == original[modular], "Modular proof changed despite the same public contract")
    refreshed = closure(changed_root, changed, rebound)
    require(refreshed.evidence_digest is not None and refreshed.evidence_digest != good.evidence_digest,
            "Rebinding failed to create a fresh closure")
    reran = closure(root, base, {**original, source: replace(original[source], artifact="fixture-artifact-rerun")})
    require(reran.evidence_digest is not None and reran.evidence_digest != good.evidence_digest,
            "Closure did not bind artifact identity")
    return {"base_closure": good.evidence_digest, "rebound_closure": refreshed.evidence_digest,
            "replacement_artifact_closure": reran.evidence_digest,
            "discharged_premise_closure": discharged.evidence_digest,
            "modular_receipt": digest(asdict(original[modular])),
            "distinct_receipts_in_diamond": len(good.evidence), "negative_controls": checked}


if __name__ == "__main__":
    print(json.dumps({"exhaustive": finite_oracle(), "scenarios": scenarios()}, sort_keys=True, indent=2))
