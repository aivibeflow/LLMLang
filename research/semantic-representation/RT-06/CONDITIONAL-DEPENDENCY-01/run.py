"""Compare may-target closure over finite control locations and flag states."""
import argparse
from collections import deque
from dataclasses import asdict, dataclass
from itertools import product
import json
from pathlib import Path
import sys

STATES = range(4)
LOCATIONS = ("entry", "shared", "relay", "check")
PROVIDERS = ("legacy", "modern", "external-provider", "dormant", "inconsistent")
CANDIDATES = ("exact", "first-state", "ignore-guards", "assume-external-false", "allow-either")
UPDATES = ("keep", "toggle-low", "set-low", "clear-low")
ROUTES = ("any", "low-zero", "low-one", "high-one")
ENTRY_ROUTES = ("never", "low-one", "high-one", "any")


@dataclass(frozen=True)
class Edge:
    target: str
    guard: str
    update: str = "keep"


def source(entry_update, loop_update, forward_guard, extra_guard):
    return {
        "entry": (Edge("shared", "any", entry_update), Edge("relay", extra_guard)),
        "shared": (Edge("legacy", "low-zero"), Edge("relay", forward_guard),
                   Edge("external-provider", "external"), Edge("dormant", "never"),
                   Edge("check", "external")),
        "relay": (Edge("modern", "low-one"), Edge("shared", "not-external", loop_update)),
        "check": (Edge("inconsistent", "not-external"),),
    }


def reference(program, interpretation):
    """Construct complete concrete adjacency, then compute transitive closure by unions."""
    conditions = {
        "never": set(), "any": set(STATES),
        "low-zero": {0, 2}, "low-one": {1, 3}, "high-one": {2, 3},
        "external": set(interpretation), "not-external": set(STATES) - set(interpretation),
    }
    updates = {"keep": (0, 1, 2, 3), "toggle-low": (1, 0, 3, 2),
               "set-low": (1, 1, 3, 3), "clear-low": (0, 0, 2, 2)}
    keys = tuple(product(LOCATIONS, STATES))
    adjacent, calls = {}, {}
    for location, flags in keys:
        state = (location, flags)
        enabled = [edge for edge in program[location] if flags in conditions[edge.guard]]
        adjacent[state] = {(edge.target, updates[edge.update][flags]) for edge in enabled
                           if edge.target in LOCATIONS}
        calls[state] = {edge.target for edge in enabled if edge.target in PROVIDERS}
    closure = {key: peers | {key} for key, peers in adjacent.items()}
    for via in keys:
        for key in keys:
            if via in closure[key]:
                closure[key].update(closure[via])
    return {flags: set().union(*(calls[key] for key in closure[("entry", flags)])) for flags in STATES}


def condition_mask(guard, external):
    if guard == "external":
        return external if external is not None else 0b1111
    if guard == "not-external":
        return external ^ 0b1111 if external is not None else 0b1111
    return {
        "never": 0,
        "any": 0b1111,
        "low-zero": 0b0101,
        "low-one": 0b1010,
        "high-one": 0b1100,
    }[guard]


def lowering(program, external, ignore_guards=False):
    update = {"keep": lambda flags: flags, "toggle-low": lambda flags: flags ^ 1,
              "set-low": lambda flags: flags | 1, "clear-low": lambda flags: flags & ~1}
    return {
        location: tuple((edge.target, 0b1111 if ignore_guards else condition_mask(edge.guard, external),
                         update[edge.update]) for edge in edges)
        for location, edges in program.items()
    }


def reachable(lowered, entry_flags, *, first_state=False, limit=len(LOCATIONS) * len(STATES)):
    todo = deque([("entry", entry_flags)])
    seen = set()
    targets = set()
    while todo:
        location, flags = todo.popleft()
        state = location if first_state else (location, flags)
        if state in seen:
            continue
        if len(seen) == limit:
            return None
        seen.add(state)
        for target, enabling, transfer in lowered[location]:
            if not enabling & (1 << flags):
                continue
            if target in lowered:
                todo.append((target, transfer(flags)))
            else:
                targets.add(target)
    return targets


def record(rows, witnesses, name, expected, actual, flags, external, config, program):
    missed = expected - actual
    extra = actual - expected
    rows[name]["missed_targets"] += len(missed)
    rows[name]["extra_targets"] += len(extra)
    rows[name]["queries_with_misses"] += bool(missed)
    rows[name]["queries_with_extras"] += bool(extra)
    for label, difference in (("miss", missed), ("extra", extra)):
        if difference and label not in witnesses[name]:
            witnesses[name][label] = {
                "configuration": config, "entry_flags": flags, "external_truth_table": external,
                "source": {node: [asdict(edge) for edge in edges] for node, edges in program.items()},
                "expected": sorted(expected), "actual": sorted(actual), "difference": sorted(difference),
            }


def run():
    rows = {mode: dict.fromkeys(("missed_targets", "extra_targets", "queries_with_misses", "queries_with_extras"), 0)
            for mode in CANDIDATES}
    witnesses = {mode: {} for mode in CANDIDATES}
    configs = tuple(product(UPDATES, UPDATES, ROUTES, ENTRY_ROUTES))
    complete = 0
    allowed_union_extras = 0
    union_witness = None
    unknown_on_budget = 0
    for config in configs:
        program = source(*config)
        guardless = lowering(program, None, ignore_guards=True)
        unknown = lowering(program, None)
        all_possible = {flags: set() for flags in STATES}
        assumed_false = lowering(program, 0)
        for external in range(1 << len(STATES)):
            interpretation = tuple(flag for flag in STATES if external & (1 << flag))
            expected = reference(program, interpretation)
            exact = lowering(program, external)
            for flags in STATES:
                all_possible[flags].update(expected[flags])
                outcomes = {
                    "exact": reachable(exact, flags),
                    "first-state": reachable(exact, flags, first_state=True),
                    "ignore-guards": reachable(guardless, flags),
                    "assume-external-false": reachable(assumed_false, flags),
                    "allow-either": reachable(unknown, flags),
                }
                for mode, targets in outcomes.items():
                    record(rows, witnesses, mode, expected[flags], targets, flags, external, config, program)
                complete += 1
        for flags in STATES:
            uncovered = reachable(unknown, flags) - all_possible[flags]
            allowed_union_extras += len(uncovered)
            if uncovered and union_witness is None:
                union_witness = {
                    "configuration": config, "entry_flags": flags,
                    "stable_union": sorted(all_possible[flags]), "added_by_local_override": sorted(uncovered),
                }
            unknown_on_budget += reachable(unknown, flags, limit=1) is None

    assert not any(rows["exact"].values())
    assert rows["first-state"]["missed_targets"] and rows["assume-external-false"]["missed_targets"]
    assert rows["ignore-guards"]["missed_targets"] == rows["allow-either"]["missed_targets"] == 0
    assert rows["allow-either"]["extra_targets"] < rows["ignore-guards"]["extra_targets"]
    assert allowed_union_extras == len(configs) * len(STATES)
    assert union_witness["added_by_local_override"] == ["inconsistent"]
    assert unknown_on_budget == len(configs) * len(STATES)
    return {
        "format": "rt06-conditional-dependency/1", "python": sys.version.split()[0],
        "control_locations": len(LOCATIONS), "flag_states": len(STATES),
        "concrete_queries": complete, "source_programs": len(configs),
        "external_truth_tables": 1 << len(STATES), "rows": rows, "witnesses": witnesses,
        "allow_either_extras_against_full_union": allowed_union_extras,
        "union_witness": union_witness,
        "interrupted_queries_returning_unknown": unknown_on_budget,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
