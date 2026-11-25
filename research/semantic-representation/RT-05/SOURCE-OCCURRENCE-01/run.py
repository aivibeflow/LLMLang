"""Compare graph reuse and fresh source spans for two identical call occurrences."""

import ast
import hashlib
import json
import platform
import subprocess
import sys
from itertools import product
from pathlib import Path

BASELINE = "655553342a713c1f1dab611d8c8c4cecb9c4c043"
ROOT = Path(__file__).resolve().parents[4]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.persistence import dumps_graph
from src.semantic_graph import RelationStore
from src.spg_admission import validate
from src.spg_representation import Implementation, Operation, Prefix, Program, _infix, compile_program, observe

CALL = 'op("provider", x)'
POSITIONS = ("left", "right")
INPUTS = (-7, -2, 0, 1, 9)
LAYOUTS = {
    "compact": ("(", " + ", ")"),
    "trailing-comment": ("(", " + ", ") # result\n"),
    "wide-spacing": ("(  ", "   +   ", "  )\n"),
    "multiline": ("(\n    ", " +\n    ", "\n)\n"),
    "utf8-before": ("# entrée 🔍\n(", " + ", ")\n"),
    "utf8-between-crlf": ("(\r\n    ", " +  # résultat 🔍\r\n    ", "\r\n)\r\n"),
}
INPUT_FILES = (
    "src/spg_representation.py",
    "src/spg_admission.py",
    "src/semantic_graph.py",
    "src/persistence.py",
    "src/recursive_identity.py",
)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def assemble(layout, second=CALL):
    first, between, end = layout
    left = len(first.encode())
    right = left + len(CALL.encode()) + len(between.encode())
    ranges = {"left": [left, left + len(CALL.encode())], "right": [right, right + len(second.encode())]}
    return (first + CALL + between + second + end).encode(), ranges


def spans(raw, *, count_bytes=True):
    decoded = raw.decode("utf-8")
    parsed = ast.parse(decoded, mode="eval").body
    assert isinstance(parsed, ast.BinOp) and isinstance(parsed.op, ast.Add)
    lines = raw.splitlines(keepends=True) if count_bytes else decoded.splitlines(keepends=True)

    def absolute(line, column):
        return sum(map(len, lines[:line - 1])) + column

    result = {}
    for name, node in zip(POSITIONS, (parsed.left, parsed.right), strict=True):
        assert isinstance(node, ast.Call)
        result[name] = [absolute(node.lineno, node.col_offset),
                        absolute(node.end_lineno, node.end_col_offset)]
    return parsed, result


def graph_for(parsed):
    program = Program(
        contracts={"provider": (("tick",),), "entry": (("tick", "tick"),)},
        operations={"provider": Operation("Provider", ("Int",), "Int", "provider"),
                    "entry": Operation("Entry", ("Int",), "Int", "entry")},
        implementations={"provider": Implementation("provider", ("n",), 'emit("tick", n + 2)'),
                         "entry": Implementation("entry", ("x",), Prefix(json.dumps(_infix(parsed))))},
        bindings={"provider": "provider"},
    )
    graph = compile_program(program)
    validate(graph)
    encoded = dumps_graph(graph.store, RelationStore(), (graph.snapshot,))
    observations = [observe(graph, "entry", (value,)) for value in INPUTS]
    return graph.snapshot.root_hash, encoded, observations


def accepted(record, target, *, check_revision, check_occurrence):
    if record["graph_sha256"] != target["graph_sha256"]:
        return False
    if check_revision and record["source_sha256"] != target["source_sha256"]:
        return False
    if check_occurrence:
        return record["spans"] == target["spans"]
    return all(0 <= start < stop <= len(target["source_utf8"].encode())
               for start, stop in record["spans"].values())


def spans_match_lexemes(record, target):
    raw = target["source_utf8"].encode()
    return record["graph_sha256"] == target["graph_sha256"] and all(
        sha256(raw[start:stop]) == record["lexeme_sha256"][name]
        for name, (start, stop) in record["spans"].items()
    )


def sample(layout, second=CALL, increment=0):
    raw, expected = assemble(layout, second)
    parsed, byte_spans = spans(raw)
    assert byte_spans == expected
    root, encoded, observations = graph_for(parsed)
    assert observations == [(2 * value + 4 + increment, ("tick", "tick")) for value in INPUTS]
    _, codepoint_spans = spans(raw, count_bytes=False)
    return {
        "source_utf8": raw.decode(),
        "source_sha256": sha256(raw),
        "graph_root": root,
        "graph_sha256": sha256(encoded),
        "spans": byte_spans,
        "lexeme_sha256": {name: sha256(raw[start:stop]) for name, (start, stop) in byte_spans.items()},
        "codepoint_line_start_control": codepoint_spans,
        "observations": observations,
    }, encoded


def pinned_inputs():
    result = {}
    for name in INPUT_FILES:
        local = PROTOTYPE / name
        spec = f"{BASELINE}:{local.relative_to(ROOT)}"
        archived = subprocess.check_output(["git", "show", spec], cwd=ROOT)
        assert local.read_bytes() == archived, spec
        result[name] = sha256(archived)
    return result


def main():
    inputs = pinned_inputs()
    samples = {}
    graphs = []
    for name, layout in LAYOUTS.items():
        record, graph = sample(layout)
        samples[name] = record
        graphs.append(graph)
    assert len(set(graphs)) == 1
    assert len({case["source_sha256"] for case in samples.values()}) == len(samples)
    comparisons = []
    for (old_name, old), (new_name, new) in product(samples.items(), repeat=2):
        comparisons.append({
            "old": old_name, "new": new_name,
            "graph_key_reuse": old["graph_sha256"] == new["graph_sha256"],
            "graph_and_lexemes_accept": spans_match_lexemes(old, new),
            "source_revision_accept": accepted(old, new, check_revision=True, check_occurrence=False),
            "occurrence_revalidation_accept": accepted(old, new, check_revision=True, check_occurrence=True),
            "coordinates_equal": old["spans"] == new["spans"],
        })

    original = samples["compact"]
    swapped = original | {"spans": dict(zip(POSITIONS, reversed(original["spans"].values()), strict=True))}
    modified, changed_graph = sample(LAYOUTS["compact"], 'op("provider", x + 1)', increment=1)
    assert changed_graph != graphs[0]
    swapped_distinct = modified | {"spans": dict(zip(POSITIONS, reversed(modified["spans"].values()), strict=True))}
    assert not spans_match_lexemes(swapped_distinct, modified)
    assert spans_match_lexemes(swapped, original)
    assert accepted(swapped, original, check_revision=True, check_occurrence=False)
    assert not accepted(swapped, original, check_revision=True, check_occurrence=True)
    assert modified["graph_sha256"] != original["graph_sha256"]
    assert not accepted(original, modified, check_revision=False, check_occurrence=False)

    cross_revision = [row for row in comparisons if row["old"] != row["new"]]
    assert all(row["graph_key_reuse"] and not row["source_revision_accept"] for row in cross_revision)
    print(json.dumps({
        "baseline": BASELINE,
        "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "input_sha256": inputs,
        "layouts": samples,
        "ordered_layout_pairs": comparisons,
        "cross_revision_pairs": len(cross_revision),
        "cross_revision_lexeme_admissions": sum(row["graph_and_lexemes_accept"] for row in cross_revision),
        "cross_revision_coordinate_mismatches": sum(not row["coordinates_equal"] for row in cross_revision),
        "codepoint_line_start_failures": [name for name, case in samples.items()
                                           if case["spans"] != case["codepoint_line_start_control"]],
        "swapped_spans": {"source": "compact", "spans": swapped["spans"], "lexemes_match": True,
                          "revision_and_bounds_accept": True, "occurrence_revalidation_accept": False},
        "changed_program": modified,
        "swapped_distinct_spans_match_lexemes": False,
    }, indent=2))


if __name__ == "__main__":
    main()
