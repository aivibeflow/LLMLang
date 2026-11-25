#!/usr/bin/env python3
"""Check Boolean evaluation order with ordered state and error observations."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent


def operand(cell, tag):
    match tag:
        case 0 | 1:
            return tag, cell, ()
        case 2:
            return int(cell != 0), cell, (100 + cell,)
        case 3:
            return 1, 1, (201,)
        case 4:
            return 1, cell, (200 + ((cell + 1) % 3), 200 + cell)
        case 5:
            return -1, cell, (300,)
        case 6:
            return -1, 2, (202, 300)
    raise ValueError("Unsupported operand")


def expected(cell, disjunction, eager, left, right):
    lhs, after_left, before = operand(cell, left)
    determining = lhs == disjunction
    if lhs == -1 or (determining and not eager):
        return (lhs, after_left, *before)
    rhs, after_right, after = operand(after_left, right)
    output = -1 if rhs == -1 else int(bool(lhs or rhs) if disjunction else bool(lhs and rhs))
    return (output, after_right, *before, *after)


def execute(args, root, *, source=None):
    return subprocess.run(args, cwd=root, input=source, capture_output=True, text=True,
                          check=True, timeout=30).stdout


def compare():
    inputs = list(product(range(3), range(2), range(2), range(7), range(7)))
    records = {case: expected(*case) for case in inputs}
    payload = "".join(" ".join(map(str, case)) + "\n" for case in inputs)
    comparisons, witnesses = Counter(), {}
    for cell, disjunction, left, right in product(range(3), range(2), range(7), range(7)):
        lazy = records[(cell, disjunction, 0, left, right)]
        eager = records[(cell, disjunction, 1, left, right)]
        lhs, after_left, _ = operand(cell, left)
        rhs, after_right, right_trace = operand(after_left, right)
        should_agree = (lhs == -1 or lhs != disjunction
                        or (rhs != -1 and after_left == after_right and not right_trace))
        if (lazy == eager) != should_agree:
            raise AssertionError("Incorrect observation equality criterion")
        if lazy == eager:
            key = "agree"
        elif lazy[0] != eager[0]:
            key = "result_or_error"
        elif lazy[1] != eager[1]:
            key = "final_state_only_after_result"
        else:
            key = "ordered_trace_only"
        comparisons[key] += 1
        if key != "agree":
            witnesses.setdefault(key, {"inputs": [cell, disjunction, left, right], "lazy": lazy, "eager": eager})
    flags = ["-std=c17", "-Wall", "-Wextra", "-Werror"]
    versions, outputs = {}, {}
    with TemporaryDirectory(prefix="llmlang-boolean-order-") as directory:
        root = Path(directory)
        shutil.copyfile(HERE / "probe.c", root / "probe.c")
        version = execute(["gcc", "--version"], root).splitlines()[0]
        versions["gcc"] = version
        for optimization in ("-O0", "-O2"):
            execute(["gcc", *flags, optimization, "probe.c", "-o", "probe"], root)
            output = execute(["./probe"], root, source=payload)
            parsed = [tuple(map(int, line.split())) for line in output.splitlines()]
            if parsed != [records[case] for case in inputs]:
                raise AssertionError(f"Native observations disagree with reference at {optimization}")
            outputs[optimization] = sha256(output.encode("ascii")).hexdigest()
    return {
        "schema": "llmlang-boolean-effect-order/1", "python": platform.python_version(),
        "gcc": versions["gcc"], "compile_flags": flags,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "probe.c", "Order.lean", "axioms.txt")},
        "observations_per_native_profile": len(inputs),
        "rows_sha256": outputs, "mode_comparisons": dict(comparisons), "witnesses": witnesses,
        "reference_rows": [[*case, records[case]] for case in inputs],
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
