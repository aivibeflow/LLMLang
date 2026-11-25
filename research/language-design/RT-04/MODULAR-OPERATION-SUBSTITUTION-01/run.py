#!/usr/bin/env python3
"""Compose scoped provider conformance, refinement and binding evidence."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CROSS_TARGET = HERE.parent / "CROSS-TARGET-CONFORMANCE-01"
sys.path.insert(0, str(CROSS_TARGET))
from run import VALUES, canonical, compare, digest, expected

PROFILE = "bounded-executable-contracts/1"
REQ = ("exact_marker", "value_only", "in_range_quiet")
PROVIDED = ("exact_marker", "value_only", "quiet", "in_range_quiet")


@dataclass(frozen=True)
class Binding:
    operation: str
    implementation: str
    provided: str
    context: str


def key(*fields):
    return digest(canonical(fields))


def contract(mode, active):
    domain = (0, 1, 2, 3) if mode == "in_range_quiet" else VALUES
    result = {}
    for value in domain:
        clamped = 2 * min(3, max(0, value))
        if mode == "value_only":
            result[value] = {clamped, clamped + 1}
        elif mode == "exact_marker":
            result[value] = {clamped + int(active and not 0 <= value <= 3)}
        else:
            result[value] = {clamped}
    return result


def conformance(outputs, obligations):
    return all(value in outputs and outputs[value] in permitted
               for value, permitted in obligations.items())


def refinement(provided, required):
    return all(value in provided and provided[value] <= permitted for value, permitted in required.items())


def identity(mode, obligations, active):
    return key("contract", PROFILE, mode, active,
               [(entry, sorted(allowed)) for entry, allowed in obligations.items()])


def rebuild_outputs(sample):
    active = sample["subject"]["assumption"]["callback_observable"]
    wrong = {value: observed for value, _, observed in sample["refutations"]}
    actual = [(value, flag, wrong.get(value, reference)) for value, flag, reference in expected(active)]
    if digest(canonical(actual)) != sample["observations_sha256"]:
        raise AssertionError("The reconstructed observation table differs from the execution digest")
    return {value: output for value, _, output in actual}


def body_subject(binding):
    return key("body", binding.implementation, binding.provided, binding.context)


def refinement_subject(binding):
    return key("refinement", binding.provided, binding.operation, binding.context)


def authorize(operation, binding, body, refining, approval, recognized):
    if operation != binding.operation:
        return "operation-mismatch"
    if approval != binding:
        return "binding-approval-missing"
    if body != body_subject(binding) or body not in recognized["body"]:
        return "body-evidence-missing"
    if refining != refinement_subject(binding) or refining not in recognized["refinement"]:
        return "refinement-evidence-missing"
    return "eligible"


def run(clang, linker):
    previous = json.loads((CROSS_TARGET / "evidence.json").read_text())
    native = compare(argparse.Namespace(clang=clang, wasm_ld=linker))
    if canonical(native) != canonical(previous):
        raise AssertionError("Cross-target conformance ledger does not reproduce")
    count = Counter()
    witnesses = {}
    results = []
    recognized = {"body": set(), "refinement": set()}
    for sample, required_mode, offered_mode in product(native["samples"], REQ, PROVIDED):
        subject = sample["subject"]
        active = subject["assumption"]["callback_observable"]
        required = contract(required_mode, active)
        offered = contract(offered_mode, active)
        outputs = rebuild_outputs(sample)
        direct = conformance(outputs, required)
        body = conformance(outputs, offered)
        refining = refinement(offered, required)
        if body and refining and not direct:
            raise AssertionError("Valid body and refinement must imply direct behavior for every required input")
        required_id = identity(required_mode, required, active)
        provided_id = identity(offered_mode, offered, active)
        operation = key("operation", "bounded-value", required_id)
        impl = key("implementation", [subject[field] for field in ("semantic_input", "artifact_sha256",
                     "target", "recipe", "compiler", "linker")])
        context = key("conformance-scope", subject["target"], subject["assumption"],
                      subject["checker"], subject["executor"])
        binding = Binding(operation, impl, provided_id, context)
        if body:
            recognized["body"].add(body_subject(binding))
        if refining:
            recognized["refinement"].add(refinement_subject(binding))
        results.append((sample, required_mode, offered_mode, binding, direct, body, refining))

    published = None
    validated = sha256()
    for sample, required_mode, offered_mode, binding, direct, body, refining in results:
        eligible = authorize(binding.operation, binding, body_subject(binding), refinement_subject(binding),
                             binding, recognized) == "eligible"
        if eligible != (body and refining):
            raise AssertionError((sample["key"], required_mode, offered_mode, binding, eligible))
        count["cases"] += 1
        count["directly_conforming"] += direct
        count["modular_admissions"] += eligible
        count["direct_but_missing_modular_requirement"] += direct and not eligible
        count["false_admissions_with_refinement_only"] += refining and not body
        count["false_admissions_with_body_only"] += body and not refining
        row = (sample["profile"], sample["provider"], sample["subject"]["assumption"],
               required_mode, offered_mode, direct, body, refining, eligible)
        if direct and not eligible:
            witnesses.setdefault("direct_behavior_without_modular_closure", row)
        if refining and not body:
            witnesses.setdefault("refining_declaration_without_body_conformance", row)
        if eligible and sample["profile"] == "gcc_native_O0" and sample["provider"] == "exact" and (
                sample["subject"]["assumption"]["callback_observable"] and required_mode == offered_mode == "exact_marker"):
            published = binding
        validated.update(canonical(row) + b"\n")
    if published is None:
        raise AssertionError("Missing published reference binding")

    controls = {}
    body = body_subject(published)
    refine = refinement_subject(published)
    for name, op, requested, proof, refinement_, approval, expected_decision in (
        ("exact", published.operation, published, body, refine, published, "eligible"),
        ("wrong_operation", "unrelated", published, body, refine, published, "operation-mismatch"),
        ("same_body_new_contract", published.operation, replace(published, provided="new-contract"),
         body, refine, replace(published, provided="new-contract"), "body-evidence-missing"),
        ("wrong_scope", published.operation, replace(published, context="new-target"),
         body, refine, replace(published, context="new-target"), "body-evidence-missing"),
        ("refinement_receipt_missing", published.operation, published, body, "unknown", published,
         "refinement-evidence-missing"),
        ("binding_approval_missing", published.operation, published, body, refine, None,
         "binding-approval-missing"),
    ):
        decision = authorize(op, requested, proof, refinement_, approval, recognized)
        if decision != expected_decision:
            raise AssertionError((name, decision, expected_decision))
        controls[name] = decision
    return {
        "schema": "llmlang-modular-operation-substitution/1",
        "python": native["python"], "tools": native["tools"],
        "source_evidence_sha256": digest((CROSS_TARGET / "evidence.json").read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "observed_artifact_scopes": len(native["samples"]), "counts": count,
        "distinct_body_receipts": len(recognized["body"]),
        "distinct_refinement_receipts": len(recognized["refinement"]),
        "matrix_sha256": validated.hexdigest(), "witnesses": witnesses, "binding_controls": controls,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--wasm-ld", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.clang, args.wasm_ld), indent=2))
