#!/usr/bin/env python3
"""Compute the exact finite consequences of partial or projected observations."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
JOINT = HERE.parent / "JOINT-CONTRACTS-01"
sys.path.insert(0, str(JOINT))
from run import execute, native

INPUTS = (0, 1)
MODES = {
    "complete": lambda value: value,
    "result_only": lambda value: value & 1,
    "event_only": lambda value: value >> 1,
}


@dataclass(frozen=True)
class Subject:
    revision: str
    property_id: str
    target: str
    policy: str


def supports(outputs, property_):
    return all(bool(property_[input_] & (1 << value)) for input_, value in enumerate(outputs))


def decide(expected, inferred, checked, approved, *, approval_required=True):
    if not inferred and checked != expected:
        return "behavior-unestablished"
    if approval_required and approved != expected:
        return "approval-required"
    return "eligible"


def infer(code_by_provider):
    guarantees = tuple(product(range(16), repeat=2))
    metrics = Counter()
    by_mode = {mode: Counter() for mode in MODES}
    witnesses = {}
    for anchor_id, anchor in code_by_provider.items():
        for recorded, (mode, observe) in product(range(4), MODES.items()):
            basis = {input_: observe(anchor[input_]) for input_ in INPUTS if recorded & (1 << input_)}
            compatible_values = tuple(
                {out for out in range(4) if input_ not in basis or observe(out) == basis[input_]}
                for input_ in INPUTS
            )
            allowed_sets = tuple(sum(1 << out for out in bucket) for bucket in compatible_values)
            consistent = [provider for provider, value in code_by_provider.items()
                          if all(observe(value[input_]) == seen for input_, seen in basis.items())]
            if not consistent or anchor_id not in consistent:
                raise AssertionError((anchor, basis, consistent))

            for property_ in guarantees:
                counts = by_mode[mode]
                observations = {provider: supports(code_by_provider[provider], property_) for provider in consistent}
                universally_true = all(observations.values())
                proposition_check = all((allowed & ~guarantee) == 0
                                        for allowed, guarantee in zip(allowed_sets, property_))
                if universally_true != proposition_check:
                    raise AssertionError((anchor, recorded, mode, property_))
                counts["claims"] += 1
                counts["entailed"] += universally_true
                counts["existential_false_admission"] += any(observations.values()) and not universally_true
                if recorded == 3:
                    counts["complete_input_coverage_unestablished"] += observations[anchor_id] and not universally_true
                if observations[anchor_id] and not universally_true:
                    countermodel = next(identity for identity, obeys in observations.items() if not obeys)
                    witnesses.setdefault(("all_inputs_" if recorded == 3 else "some_inputs_") + mode, {
                        "anchor_provider": anchor_id, "recorded_inputs": sorted(basis),
                        "property_masks": property_, "alternative_provider": countermodel,
                        "anchor_observation": anchor,
                        "alternative_observation": code_by_provider[countermodel],
                    })
    for values in by_mode.values():
        metrics.update(values)
    return metrics, by_mode, witnesses


def approval_controls(code_by_provider):
    behavior = (1, 2)
    silent, observed = code_by_provider[4], code_by_provider[14]
    if not supports(silent, behavior) or supports(observed, behavior):
        raise AssertionError("The effect property must differ in the positive and negative control")
    if tuple(MODES["result_only"](raw) for raw in silent) != tuple(MODES["result_only"](raw) for raw in observed):
        raise AssertionError("The control should agree on all result values")
    expected = Subject("provider-v2", "identity-with-no-event", "fixture-c17", "policy-1")
    old_revision = replace(expected, revision="provider-v1")
    changed_property = replace(expected, property_id="identity-result-only")
    cases = (
        ("full_output_and_approval", True, None, expected, True, "eligible"),
        ("full_output_without_approval", True, None, None, True, "approval-required"),
        ("projected_without_approval_or_exact_check", False, None, None, True, "behavior-unestablished"),
        ("approval_cannot_discharge_behavior", False, None, expected, True, "behavior-unestablished"),
        ("exact_check_without_approval", False, expected, None, True, "approval-required"),
        ("exact_check_and_approval", False, expected, expected, True, "eligible"),
        ("wrong_revision_check", False, old_revision, expected, True, "behavior-unestablished"),
        ("wrong_property_approval", False, expected, changed_property, True, "approval-required"),
        ("proof_sufficient_for_policy_without_approval", False, expected, None, False, "eligible"),
    )
    results = {}
    for name, entailed, checked, approved, required, expected_result in cases:
        actual = decide(expected, entailed, checked, approved, approval_required=required)
        if actual != expected_result:
            raise AssertionError((name, actual, expected_result))
        results[name] = actual
    return {"request": asdict(expected), "property_masks": behavior, "decisions": results}


def run():
    families, native_sha = native()
    codes = {index: tuple(function[input_][0] + 2 * function[input_][1] for input_ in INPUTS)
             for index, function in families.items()}
    counts, modes, witnesses = infer(codes)
    if modes["complete"]["complete_input_coverage_unestablished"] != 0:
        raise AssertionError("The total exact sample should determine every pointwise property")
    if not modes["result_only"]["complete_input_coverage_unestablished"]:
        raise AssertionError("Projection erased no evidence in the control")
    return {
        "schema": "llmlang-contract-inference/1", "python": platform.python_version(),
        "gcc": execute(["gcc", "--version"], HERE).splitlines()[0],
        "sources_sha256": {
            **{name: sha256((HERE / name).read_bytes()).hexdigest()
               for name in ("run.py", "Inference.lean", "axioms.txt")},
            "joint_native_runner": sha256((JOINT / "run.py").read_bytes()).hexdigest(),
            "joint_native_probe": sha256((JOINT / "probe.c").read_bytes()).hexdigest(),
        },
        "counts": counts, "by_projection": modes, "native_rows_sha256": native_sha,
        "witnesses": witnesses, "approval_controls": approval_controls(codes),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
