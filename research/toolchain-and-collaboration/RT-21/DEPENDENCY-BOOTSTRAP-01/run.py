#!/usr/bin/env python3
"""Execute an authored dependency tool through a reference interpreter and C lowering."""
import argparse
from collections import Counter, deque
from copy import deepcopy
from hashlib import sha256
from itertools import permutations, product
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

from fragment import InvalidSource, admit, generate, interpret


HERE = Path(__file__).resolve().parent
BITS = (1, 2, 4, 8)
ROWS = ("r0", "r1", "r2", "r3")
REVISION = "b1b1579bd21e164c45c4c93e24dafca9945239ee"
REGISTER = "research/research-management/RESEARCH-DEPENDENCY-MAP.md"


def digest(data):
    return sha256(data).hexdigest()


def expected(record):
    nodes, start, *adjacency = record
    members = {node for node, flag in enumerate(BITS) if flag & nodes}
    origin = {node for node, flag in enumerate(BITS) if flag & start}
    if len(origin) != 1 or not origin <= members:
        return (1, 0)
    graph = {node: {neighbor for neighbor, flag in enumerate(BITS) if row & flag}
             for node, row in enumerate(adjacency)}
    if any((node not in members and edges) or not edges <= members for node, edges in graph.items()):
        return (2, 0)
    frontier = deque(origin)
    seen = set(origin)
    while frontier:
        for neighbor in graph[frontier.popleft()] - seen:
            seen.add(neighbor)
            frontier.append(neighbor)
    return (0, sum(BITS[node] for node in seen))


def corpus():
    three = []
    for graph, nodes, root in product(range(512), range(8), (0, 1, 2, 4)):
        adjacency = [(graph >> (node * 3)) & 0b111 for node in range(3)]
        three.append((nodes, root, *adjacency, 0))
    four = []
    for order in permutations(range(4)):
        adjacency = [0] * 4
        for source, dest in zip(order, order[1:]):
            adjacency[source] = BITS[dest]
        four.append((15, BITS[order[0]], *adjacency))  # path uses three edges
        four.append((15 ^ BITS[order[-1]], BITS[order[0]], *adjacency))
        adjacency[order[-1]] = BITS[order[0]]
        four.append((15, BITS[order[0]], *adjacency))  # cycle
    return three + four


def project_register():
    repository = HERE.parents[3]
    raw = subprocess.check_output(["git", "show", f"{REVISION}:{REGISTER}"], cwd=repository)
    edges = re.findall(r"^\| (DEP-\d+) \| (RT-\d+) → (RT-\d+) \|", raw.decode(), re.M)
    assert ("DEP-094", "RT-03", "RT-21") in edges
    groups = [("RT-03", "RT-05", "RT-07", "RT-21"), ("RT-03", "RT-04", "RT-05", "RT-06"),
              ("RT-11", "RT-15", "RT-19", "RT-20")]
    inputs, selections = [], []
    for nodes in groups:
        adjacency = [0] * 4
        selected = sorted((identifier, left, right) for identifier, left, right in edges
                          if left in nodes and right in nodes)
        assert selected
        for _, left, right in selected:
            adjacency[nodes.index(left)] |= BITS[nodes.index(right)]
        group_inputs = [(15, flag, *adjacency) for flag in BITS]
        inputs.extend(group_inputs)
        selections.append({"nodes": nodes, "edge_ids": [item[0] for item in selected],
                           "inputs": group_inputs, "expected": [expected(row) for row in group_inputs]})
    return inputs, {"revision": REVISION, "register_sha256": digest(raw), "groups": selections}


def cases(document):
    shallow, absent_source, absent_target = [deepcopy(document) for _ in range(3)]
    entry = shallow["functions"][-1]["body"]
    entry["if"][1]["if"][1]["result"][1] = {"call": ["expand", "root", *ROWS]}
    absent_source["functions"][1]["body"] = {"eq": [{"bits_and": ["row", "live"]}, "row"]}
    absent_target["functions"][1]["body"]["if"][2] = True
    return {
        "one-propagation": shallow,
        "allow-edges-from-absent-vertex": absent_source,
        "allow-edges-to-absent-vertex": absent_target,
    }


def refusal_cases(document):
    wrong_type, call_arity, recursion, effect, bad_literal = [deepcopy(document) for _ in range(5)]
    wrong_type["functions"][0]["body"]["if"][0] = 1
    call_arity["functions"][-1]["body"]["if"][0]["call"].pop()
    recursion["functions"][0]["body"] = {"call": ["take_row", "seen", "node", "row"]}
    effect["functions"][0]["body"] = {"perform": []}
    bad_literal["functions"][0]["body"]["if"][1] = 16
    return {
        "non-Boolean-guard": json.dumps(wrong_type),
        "wrong-call-arity": json.dumps(call_arity),
        "self-recursion": json.dumps(recursion),
        "unsupported-effect": json.dumps(effect),
        "out-of-range-literal": json.dumps(bad_literal),
        "duplicate-member": '{"profile":"a","profile":"b","entry":"x","functions":[]}',
    }


def launch(command, directory, data=b"", *, check=True):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("LD_", "GCC_", "CPATH", "C_INCLUDE_PATH"))}
    environment.update({"LC_ALL": "C", "TZ": "UTC"})
    result = subprocess.run(command, cwd=directory, env=environment, input=data,
                            capture_output=True, timeout=30)
    if check:
        assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def build(directory, program, flag):
    source = directory / "tool.c"
    source.write_text(generate(program))
    binary = directory / ("tool" + flag)
    # Mutations can leave a valid source parameter or procedure unused.
    launch(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
            "-Wno-unused-parameter", flag, source, "-o", binary], directory)
    return source, binary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = (HERE / "dependency-tool.json").read_bytes()
    document = json.loads(raw)
    program = admit(raw)
    formatted = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=4).encode()
    assert digest(formatted) != digest(raw) and admit(formatted).semantic_sha256 == program.semantic_sha256
    archive_inputs, register = project_register()
    inputs = corpus() + archive_inputs
    wire = b"".join(bytes(item) for item in inputs)
    oracle = [expected(item) for item in inputs]
    oracle_bytes = b"".join(bytes(item) for item in oracle)
    assert [interpret(program, item) for item in inputs] == oracle

    with tempfile.TemporaryDirectory(prefix="rt21-bootstrap-") as directory:
        root = Path(directory)
        native = {}
        for option in ("-O0", "-O2"):
            source, binary = build(root, program, option)
            actual = launch([binary], root, wire).stdout
            assert actual == oracle_bytes
            native[option] = {"matched": len(inputs), "output_sha256": digest(actual),
                              "binary_sha256": digest(binary.read_bytes()),
                              "generated_source_sha256": digest(source.read_bytes())}
        rejections = {}
        for name, item in refusal_cases(document).items():
            try:
                admit(item)
            except InvalidSource as error:
                rejections[name] = str(error)
            else:
                raise AssertionError(name)
        invalid_wire = {"truncated-record": b"\x00\x00", "out-of-range-carrier": b"\x10\x00\x00\x00\x00\x00"}
        for name, item in invalid_wire.items():
            result = launch([binary], root, item, check=False)
            assert result.returncode == 2 and not result.stdout
            rejections[name] = "native carrier refused"
        mutants = {}
        for name, candidate in cases(document).items():
            alternate = admit(json.dumps(candidate))
            assert alternate.semantic_sha256 != program.semantic_sha256
            source, binary = build(root, alternate, "-O2")
            alternative = [interpret(alternate, item) for item in inputs]
            assert launch([binary], root, wire).stdout == b"".join(bytes(pair) for pair in alternative)
            changes = [(index, reference, changed) for index, (reference, changed)
                       in enumerate(zip(oracle, alternative)) if reference != changed]
            assert changes
            index, reference, changed = changes[0]
            mutants[name] = {"different_cases": len(changes), "first_input": inputs[index],
                             "expected_result": reference, "mutant_result": changed,
                             "semantic_sha256": alternate.semantic_sha256,
                             "binary_sha256": digest(binary.read_bytes())}
        tool = launch(["gcc", "--version"], root).stdout.decode().splitlines()[0]
        report = {"compiler": tool, "input_sha256": digest(wire), "oracle_sha256": digest(oracle_bytes),
                  "source_sha256": digest(raw), "profile_implementation_sha256":
                      digest((HERE / "fragment.py").read_bytes()),
                  "semantic_sha256": program.semantic_sha256, "equivalent_presentation_sha256": digest(formatted),
                  "case_count": len(inputs), "three_node_cases": len(inputs) - 72 - len(archive_inputs),
                  "four_node_cases": 72, "register_cases": len(archive_inputs),
                  "register_projections": register,
                  "outcomes_by_status": dict(Counter(result[0] for result in oracle)),
                  "native_routes": native, "refused_controls": rejections, "semantic_mutants": mutants}
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
