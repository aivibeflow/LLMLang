"""Compare source-bound occurrence encodings for a rooted recursive fragment."""
import argparse
from itertools import permutations, product
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, canonical_bytes

SHAPE = "rt05-ordered-occurrences-v1"
POLICIES = (frozenset(), frozenset(("read",)), frozenset(("read", "write")))
INPUTS = ((2, 7), (-3, 1))
FUEL = range(6)
MODES = ("exact", "role-local-order", "unique-steps", "unordered-arguments")
NAMES = ("open", "read_back", "finish")
CALLS = {"call", "call-positive"}


def fixtures():
    for repeated, swapped in product((False, True), repeat=2):
        arguments = ("y", "x") if swapped else ("x", "y")
        invoke = ("call", "read_back", *arguments)
        steps = (("emit", "begin", "x"), invoke, ("call", "finish", 4, 9), ("emit", "end", "y"))
        if repeated:
            steps += (invoke,)
        for shape in sorted(set(permutations(steps))):
            yield {
                "open": (("read", "write"), shape),
                "read_back": (("read",), (("emit", "left", "x"), ("call-positive", "open", 0, "y"))),
                "finish": (("write",), (("emit", "right", "y"),)),
            }


def source(program, names, declarations, reverse_facts):
    renamed = dict(zip(NAMES, names))
    lines = [f"entry {renamed[NAMES[0]]}"]
    for name in declarations:
        facts, steps = program[name]
        lines.append(f"def {renamed[name]}")
        lines.extend(f"requires {fact}" for fact in (facts[::-1] if reverse_facts else facts))
        for opcode, target, *operands in steps:
            words = (opcode, renamed[target] if opcode in CALLS else target, *operands)
            lines.append(" ".join(map(str, words)))
    return "\n".join(lines)


def parse(text):
    first, *lines = text.splitlines()
    marker, entry = first.split(" ")
    assert marker == "entry"
    bodies = {}
    for line in lines:
        opcode, target, *operands = line.split(" ")
        if opcode == "def":
            assert target not in bodies and not operands
            facts, steps = [], []
            bodies[target] = facts, steps
        elif opcode == "requires":
            assert not operands and target in {"read", "write"} and target not in facts
            facts.append(target)
        else:
            assert opcode in CALLS | {"emit"}
            assert len(operands) == (1 if opcode == "emit" else 2)
            values = tuple(operand if operand in {"x", "y"} else int(operand) for operand in operands)
            steps.append((opcode, target, *values))
    assert entry in bodies
    assert all(target in bodies for _, steps in bodies.values() for kind, target, *_ in steps if kind in CALLS)
    return entry, bodies


def lower(entry, bodies, mode):
    """Assign operation numbers by first encounter along the exact ordered graph."""
    discovery = {entry: 0}
    agenda = [entry]
    output = []
    for name in agenda:
        facts, source_steps = bodies[name]
        steps = []
        for opcode, target, *operands in source_steps:
            if opcode in CALLS:
                if target not in discovery:
                    discovery[target] = len(agenda)
                    agenda.append(target)
                target = discovery[target]
            if opcode in CALLS and mode == "unordered-arguments":
                operands.sort(key=canonical_bytes)
            steps.append((opcode, target, *operands))
        if mode == "role-local-order":
            steps.sort(key=lambda step: step[0] == "emit")
        if mode == "unique-steps":
            steps = list(dict.fromkeys(steps))
        output.append((sorted(facts), steps))
    assert len(discovery) == len(bodies)
    return output


def exhaustive_class(program):
    alternatives = []
    for rest in permutations(NAMES[1:]):
        order = (NAMES[0], *rest)
        index = {name: position for position, name in enumerate(order)}
        graph = []
        for name in order:
            facts, occurrences = program[name]
            graph.append((sorted(facts), [
                (kind, index[target] if kind in CALLS else target, *operands)
                for kind, target, *operands in occurrences
            ]))
        alternatives.append(canonical_bytes(graph))
    return min(alternatives)


def oracle(program, permits, inputs, fuel):
    """Evaluate raw source operations by recursive calls, with no canonical IDs."""
    events = []

    def evaluate(name, args, remaining):
        if remaining == 0:
            return "exhausted"
        facts, steps = program[name]
        if any(fact not in permits for fact in facts):
            return "denied"
        bindings = dict(zip(("x", "y"), args))
        for kind, target, *operands in steps:
            values = tuple(bindings.get(operand, operand) for operand in operands)
            if kind == "emit":
                events.append((target, values[0]))
            elif kind == "call" or args[0] > 0:
                status = evaluate(target, values, remaining - 1)
                if status != "ok":
                    return status
        return "ok"

    return evaluate(NAMES[0], inputs, fuel), events


def execute(graph, permits, inputs, fuel):
    """Interpret canonical operation numbers with an explicit continuation stack."""
    events = []
    frames = [(0, 0, inputs, fuel)]
    while frames:
        node, pc, arguments, depth = frames.pop()
        facts, steps = graph[node]
        if pc == 0:
            if not depth:
                return "exhausted", events
            if not permits.issuperset(facts):
                return "denied", events
        if pc < len(steps):
            frames.append((node, pc + 1, arguments, depth))
            kind, target, *operands = steps[pc]
            values = tuple(arguments[("x", "y").index(value)] if isinstance(value, str) else value
                           for value in operands)
            if kind == "emit":
                events.append((target, values[0]))
            elif kind == "call" or arguments[0] > 0:
                frames.append((target, 0, values, depth - 1))
    return "ok", events


def configs():
    for permits, inputs, fuel in product(POLICIES, INPUTS, FUEL):
        yield permits, inputs, fuel


def run():
    store = ContentStore()
    groups = {mode: {} for mode in MODES}
    mismatches = dict.fromkeys(MODES, 0)
    status_mismatches = dict.fromkeys(MODES, 0)
    examples = {}
    collisions = {}
    programs = tuple(fixtures())
    variants = tuple(product(tuple(permutations(NAMES)), (False, True)))
    for program in programs:
        reference = exhaustive_class(program).decode()
        expected = [oracle(program, *config) for config in configs()]
        default = source(program, NAMES, NAMES, False)
        for mode in MODES:
            graph = lower(*parse(default), mode)
            key = store.put(SHAPE, graph)
            group = groups[mode].setdefault(key, {})
            if reference not in group and mode != "exact" and mode not in collisions:
                for previous_source, previous_observations in group.values():
                    for config, previous, wanted in zip(configs(), previous_observations, expected):
                        if previous != wanted:
                            permits, inputs, fuel = config
                            collisions[mode] = {
                                "shared_key": key, "sources": [previous_source, default],
                                "permits": sorted(permits), "inputs": inputs, "fuel": fuel,
                                "source_outcomes": [previous, wanted],
                            }
                            break
                    if mode in collisions:
                        break
            group[reference] = default, expected
            actual = [execute(graph, *config) for config in configs()]
            for config, wanted, got in zip(configs(), expected, actual):
                if wanted != got:
                    mismatches[mode] += 1
                    status_mismatches[mode] += int(wanted[0] != got[0])
                    if mode not in examples:
                        permits, inputs, fuel = config
                        examples[mode] = {"source": default, "permits": sorted(permits), "inputs": inputs,
                                          "fuel": fuel, "source_outcome": wanted, "graph_outcome": got}
            for declarations, reverse_facts in variants:
                renaming = ("q9", "z2", "a1")
                variant = source(program, renaming, declarations, reverse_facts)
                assert store.put(SHAPE, lower(*parse(variant), mode)) == key
    assert len(groups["exact"]) == len({item for group in groups["exact"].values() for item in group})
    assert all(len(group) == 1 for group in groups["exact"].values())
    assert mismatches["exact"] == 0
    assert all(mismatches[mode] > 0 for mode in MODES[1:])
    assert set(collisions) == set(MODES[1:])
    return {
        "format": SHAPE,
        "python": sys.version.split()[0],
        "source_programs": len(programs),
        "surface_variants_per_program": len(variants),
        "configurations_per_program": len(tuple(configs())),
        "results": {mode: {
            "distinct_keys": len(groups[mode]),
            "collapsed_groups": sum(len(group) > 1 for group in groups[mode].values()),
            "largest_group": max(map(len, groups[mode].values())),
            "disagreeing_observations": mismatches[mode],
            "different_status": status_mismatches[mode],
            "first_mismatch": examples.get(mode),
            "behavioral_collision": collisions.get(mode),
        } for mode in MODES},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
