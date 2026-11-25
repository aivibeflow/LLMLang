#!/usr/bin/env python3
"""Check parallel DAG costs, exact distribution-weighted probes, and emitted bytes."""

from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
THEOREMS = (
    "uniform_probe_sum", "full_tree_nodes", "tree_messages",
    "padded_path", "bounded_width", "no_n_only_bound",
)


def parallel(values, depth):
    """Build an explicit unit-cost DAG and count its communication separately."""
    lanes = 1 << depth
    block = (len(values) + lanes - 1) // lanes
    ops = []

    def task(consumes, value):
        index = len(ops)
        ops.append((tuple(i for i in consumes if i is not None), value))
        return index

    def result(index):
        return False if index is None else ops[index][1]

    roots = []
    for lane in range(lanes):
        previous = None
        for bit in values[lane * block:(lane + 1) * block]:
            previous = task((previous,), result(previous) or bit)
        roots.append(previous)
    communication = 0
    while len(roots) > 1:
        left_children = roots[::2]
        right_children = roots[1::2]
        roots = [
            task((left, right), result(left) or result(right))
            for left, right in zip(left_children, right_children, strict=True)
        ]
        communication += len(left_children) + len(right_children)

    # Compute a longest path by evaluating the dependency list, independently
    # of how lanes, depth, or expected quantities are defined.
    path_lengths = []
    for inputs, _ in ops:
        path_lengths.append(1 + max((path_lengths[i] for i in inputs), default=0))
    return result(roots[0]), len(ops), max(path_lengths, default=0), communication


def parallel_cells():
    cases = 0
    max_work = max_span = max_messages = 0
    for n in range(11):
        for values in product((False, True), repeat=n):
            for depth in range(5):
                lanes = 1 << depth
                result, work, span, messages = parallel(values, depth)
                assert result == any(values)
                assert work == n + lanes - 1
                assert span == (n + lanes - 1) // lanes + depth
                assert messages == 2 * (lanes - 1)
                cases += 1
                max_work = max(work, max_work)
                max_span = max(span, max_span)
                max_messages = max(messages, max_messages)
    return {"cases": cases, "max_work": max_work, "max_span": max_span, "max_messages": max_messages}


def scanned(values):
    for index, value in enumerate(values, 1):
        if value:
            return index
    return len(values)


def probability_cells():
    table = {}
    positive_runs = changed = 0
    for n in range(1, 129):
        observations = [
            scanned(tuple(index == selected for index in range(n)))
            for selected in range(n)
        ]
        absent = scanned((False,) * n)
        assert absent == n
        uniform = sum((Fraction(value, n) for value in observations))
        bias_last = Fraction(3, 4) * uniform + Fraction(1, 4) * observations[-1]
        possibly_absent = Fraction(1, 2) * uniform + Fraction(1, 2) * absent
        assert uniform == Fraction(n + 1, 2)
        assert bias_last == Fraction(5 * n + 3, 8)
        assert possibly_absent == Fraction(3 * n + 1, 4)
        if n > 1:
            assert uniform < bias_last < possibly_absent < n
            changed += 1
        positive_runs += n
        table[n] = [str(uniform), str(bias_last), str(possibly_absent), absent]
    return {"positive_inputs": positive_runs, "absent_inputs": len(table),
            "size_cells_detecting_change": changed, "examples": {
                n: table[n] for n in (1, 2, 16, 128)
            }}


def output_cells():
    comparisons = 0
    for n in range(17):
        for selected in range(n + 1):
            for width in (1, 4, 17, 33):
                pieces = [(b"\0", False) if index >= selected else (bytes([index]) * width, True)
                          for index in range(n)]
                result = b"".join(data for data, keep in pieces if keep)
                assert len(result) == selected * width
                assert len(result) <= n * width <= n * 33
                assert [result[i:i + width] for i in range(0, len(result), width)] == [
                    bytes([index]) * width for index in range(selected)
                ]
                comparisons += 1
    return {"cases": comparisons, "one_item_output_widths": [1, 4, 17, 33]}


def proof_axioms():
    lean = os.environ.get("LEAN", "lean")
    check = subprocess.run([lean, "-DwarningAsError=true", "Costs.lean"], cwd=HERE,
                           check=True, capture_output=True, text=True)
    assert not check.stderr
    axioms = {}
    for line in check.stdout.splitlines():
        no_axioms = re.fullmatch(r"'([^']+)' does not depend on any axioms", line)
        if no_axioms:
            axioms[no_axioms[1]] = []
            continue
        name, dependencies = re.fullmatch(r"'([^']+)' depends on axioms: \[([^\]]+)\]", line).groups()
        axioms[name] = dependencies.split(", ")
    assert tuple(axioms) == THEOREMS
    assert all(set(names) <= {"propext", "Quot.sound"} for names in axioms.values())
    return axioms


if __name__ == "__main__":
    evidence = {
        "format": "parallel-expected-output-01",
        "parallel": parallel_cells(), "probability": probability_cells(),
        "output": output_cells(), "axioms": proof_axioms(),
        "lean_source": sha256((HERE / "Costs.lean").read_bytes()).hexdigest(),
    }
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
