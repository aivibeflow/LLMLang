#!/usr/bin/env python3
"""Test typed graph sharing against the pinned executable reference."""

from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REVISION = "58c8de7873cd6996eb7be82e40eef09f49dc3c37"
REFERENCE = "research/formal-verification/RT-07/STATE-RESULT-REFERENCE-01/reference.py"
ARCHIVE = {
    REFERENCE: "83d9e003fda21fba074c060ee3db0d9023fe519b231da31fd491425b2a2497b4",
    "research/formal-verification/RT-07/THREE-SEMANTICS-01/run.py":
        "ff0036446f3cee77ef9db1c63a51a10ed0af88625b622fe0e2fbc0cb5367e5cd",
    "research/PROTOTYPES/RT-04-01/rt03_reference.py":
        "9aa14d41f837c3c0bae137f6732b72ff9edb0b70a31f1f966639124be98ed8d8",
    "research/PROTOTYPES/RT-04-01/rt03_smallstep.py":
        "79516cb51e8ec6f505ab8833646f42415eb1e5f46171aac399b41c6652ed7459",
}
COMBINATORS = ("strict", "bind", "then", "else")
UNIT, FAILURE = ("ok", None), ("error", "planned")


class InvalidGraph(ValueError):
    pass


def lower(tree):
    nodes, index = [], {}

    def intern(subtree):
        tag, *args = subtree
        wire = (tag, *map(intern, args)) if tag in COMBINATORS else subtree
        if wire not in index:
            index[wire] = len(nodes)
            nodes.append(wire)
        return index[wire]

    root = intern(tree)
    return nodes, root


def unfold(nodes, root):
    if type(root) is not int or not 0 <= root < len(nodes):
        raise InvalidGraph("root")
    terms = []
    for index, node in enumerate(nodes):
        match node:
            case ("skip" | "read" | "fail",):
                terms.append(node)
            case ("write", value) if type(value) is int and value in (0, 1):
                terms.append(node)
            case (tag, left, right) if tag in COMBINATORS:
                if any(type(ref) is not int or not 0 <= ref < index for ref in (left, right)):
                    raise InvalidGraph("child reference")
                terms.append((tag, terms[left], terms[right]))
            case _:
                raise InvalidGraph("node")
    return terms[root]


def reorder(nodes, root):
    atoms = [i for i, node in enumerate(nodes) if node[0] not in COMBINATORS]
    constructors = [i for i, node in enumerate(nodes) if node[0] in COMBINATORS]
    order = [*reversed(atoms), *constructors]
    renamed = {old: new for new, old in enumerate(order)}
    result = []
    for index in order:
        tag, *args = nodes[index]
        result.append((tag, *map(renamed.__getitem__, args))
                      if tag in COMBINATORS else nodes[index])
    return result, renamed[root]


def graph_observation(nodes, root, initial, cache_by=None):
    memo = {}

    def invoke(index, state):
        if cache_by is None:
            return execute(index, state)
        key = cache_by(index, state)
        if key in memo:
            return memo[key], state, ()
        observation = execute(index, state)
        memo[key] = observation[0]
        return observation

    def execute(index, state):
        match nodes[index]:
            case ("skip",):
                return UNIT, state, ()
            case ("fail",):
                return FAILURE, state, ()
            case ("read",):
                return ("ok", state), state, (("read", state),)
            case ("write", value):
                return UNIT, value, (("write", value),)
            case ("then", left, _):
                return invoke(left, state)
            case ("else", _, right):
                return invoke(right, state)
            case (mode, left, right):
                tag, changed, prefix = invoke(left, state)
                if mode == "bind" and tag == FAILURE:
                    return tag, changed, prefix
                last, final, suffix = invoke(right, changed)
                return last, final, prefix + suffix
        raise InvalidGraph("evaluation")

    return invoke(root, initial)


def load(directory):
    for relative, expected in ARCHIVE.items():
        data = subprocess.check_output(["git", "show", f"{REVISION}:{relative}"])
        if sha256(data).hexdigest() != expected:
            raise AssertionError(relative)
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    spec = spec_from_file_location("reference_wire", directory / REFERENCE)
    reference = module_from_spec(spec)
    spec.loader.exec_module(reference)
    return reference


def check_invalid():
    examples = {
        "root": ([("skip",)], 1),
        "cycle": ([("strict", 0, 0)], 0),
        "forward": ([("bind", 1, 1), ("read",)], 0),
        "typed_bool": ([("write", True)], 0),
        "unknown": ([("erase",)], 0),
        "negative_child": ([("skip",), ("then", 0, -1)], 1),
    }
    for name, (nodes, root) in examples.items():
        try:
            unfold(nodes, root)
        except InvalidGraph:
            continue
        raise AssertionError(f"Accepted malformed graph: {name}")
    return sorted(examples)


def compare(reference):
    model = reference.model
    extra = ((mode, ("strict", shared, between), ("bind", shared, after))
             for mode, shared, between, after in product(
                 COMBINATORS, model.LEAVES, model.LEAVES, model.LEAVES))
    programs = dict.fromkeys((*model.corpus(), *extra))
    counts = Counter()
    counterexamples = {}
    transcript = sha256()
    for tree in programs:
        nodes, root = lower(tree)
        renamed, alias = reorder(nodes, root)
        if unfold(nodes, root) != tree or unfold(renamed, alias) != tree:
            raise AssertionError((tree, nodes, renamed))
        counts["programs"] += 1
        counts["numeric_relabels"] += (renamed, alias) != (nodes, root)
        for initial in model.INITIAL:
            wire = json.dumps((reference.SCHEMA, initial, tree)).encode()
            observed = reference.evaluate_request(wire)
            expected = tuple(observed["result"].items())[0], observed["final_cell"], observed["trace"]
            settings = {"declared_effects": model.EFFECTS, "initial_state": {"cell": initial}}
            machine = model.observed(model.run_small_step(model.ast_for(tree), "D", **settings))
            actual = graph_observation(nodes, root, initial)
            reindexed = graph_observation(renamed, alias, initial)
            if not expected == machine == actual == reindexed:
                raise AssertionError((tree, expected, machine, actual, reindexed))
            counts["exact_observations"] += 1
            controls = {
                "cache_node": graph_observation(nodes, root, initial, lambda index, _: index),
                "cache_node_and_cell": graph_observation(nodes, root, initial,
                                                         lambda index, cell: (index, cell)),
            }
            for name, candidate in controls.items():
                counts[f"{name}_changed"] += actual != candidate
                counts[f"{name}_trace_only"] += actual[:2] == candidate[:2] and actual != candidate
                if actual[:2] != candidate[:2]:
                    counterexamples.setdefault(name, [tree, initial, actual, candidate])
            transcript.update(json.dumps([tree, initial, actual, controls]).encode() + b"\n")
    return counts, counterexamples, transcript.hexdigest()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        counts, witnesses, digest = compare(load(Path(directory)))
    print(json.dumps({
        "schema": "llmlang-graph-occurrence-preservation/1", "python": platform.python_version(),
        "archive_revision": REVISION, "archive_sha256": ARCHIVE,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Graph.lean", "axioms.txt")},
        "counts": counts, "counterexamples": witnesses, "malformed_graphs_refused": check_invalid(),
        "ordered_replay_sha256": digest,
    }, indent=2))
