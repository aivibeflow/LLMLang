#!/usr/bin/env python3
"""Compare sequential contract handoff rules over a finite observation family."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
FIRST = (
    ("success", 0, ("prefix-write-0",)), ("success", 1, ("prefix-write-1",)),
    ("error", 0, ("prefix-write-0", "raise")), ("error", 1, ("prefix-write-1", "raise")),
)
RIGHT = {
    cell: (("success", cell, (f"read-{cell}",)),
           ("error", 1 - cell, (f"read-{cell}", f"write-{1 - cell}", "raise")))
    for cell in (0, 1)
}


def selected(items, mask):
    return tuple(item for position, item in enumerate(items) if mask & (1 << position))


def compose(prefixes, ready, resumes):
    allowed = set()
    for status, cell, history in prefixes:
        if status == "error":
            allowed.add((status, cell, history))
            continue
        if cell not in ready:
            raise ValueError("unmet intermediate precondition")
        for next_status, next_cell, trace in resumes[cell]:
            allowed.add((next_status, next_cell, history + trace))
    return allowed


def compare():
    gates = {name: Counter() for name in ("all_successful", "some_successful", "all_final_states", "unchecked")}
    actual_cases = 0
    output_traces = 0
    controls = {}
    cases = []
    for mask, precondition in product(range(1, 16), range(4)):
        first = selected(FIRST, mask)
        admitted = set(selected((0, 1), precondition))
        issues = tuple(outcome for outcome in first if outcome[0] == "success" and outcome[1] not in admitted)
        expected = not issues
        decisions = {
            "all_successful": all(state in admitted for status, state, _ in first if status == "success"),
            "some_successful": any(state in admitted for status, state, _ in first if status == "success"),
            "all_final_states": all(state in admitted for _, state, _ in first),
            "unchecked": True,
        }
        for policy, decision in decisions.items():
            gates[policy]["admitted"] += decision
            gates[policy]["false_admission"] += decision and not expected
            gates[policy]["false_refusal"] += expected and not decision
        if decisions["all_successful"] != expected:
            raise AssertionError("Universal handoff disagrees with execution availability")
        if decisions["some_successful"] and issues:
            controls.setdefault("mixed_legal_and_illegal_successes", [mask, precondition, issues])
        if expected and not decisions["all_final_states"]:
            controls.setdefault("error_state_needs_no_second_precondition", [mask, precondition, first])
        if expected:
            allowed = compose(first, admitted, RIGHT)
            for concrete_first in range(1, 1 << len(first)):
                for choice0, choice1 in product(range(1, 4), repeat=2):
                    actual_first = selected(first, concrete_first)
                    actual_second = {0: selected(RIGHT[0], choice0), 1: selected(RIGHT[1], choice1)}
                    execution = compose(actual_first, admitted, actual_second)
                    # Independently compute all failure or successful-composition paths.
                    direct = {observation for observation in actual_first if observation[0] == "error"}
                    direct.update(
                        (last[0], last[1], tuple([*prefix[2], *last[2]]))
                        for prefix in actual_first if prefix[0] == "success"
                        for last in actual_second[prefix[1]]
                    )
                    if execution != direct or not execution <= allowed:
                        raise AssertionError("Contract composition lost an exact trace")
                    actual_cases += 1
                    output_traces += len(execution)
        cases.append({"first_mask": mask, "second_precondition_mask": precondition,
                      "declared_outcomes": first, "unmet_outcomes": issues, "dispositions": decisions})
    return {
        "schema": "llmlang-sequential-contracts/1", "python": platform.python_version(),
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "Sequence.lean", "axioms.txt")},
        "first_outcome_order": FIRST, "second_outcome_order_by_state": RIGHT,
        "contract_pairs": len(cases), "concrete_refinement_checks": actual_cases,
        "concrete_outcomes_checked": output_traces, "gates": gates, "controls": controls, "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
