#!/usr/bin/env python3
"""Check sequential order constraints separately from stochastic native observations."""

import argparse
from hashlib import sha256
from itertools import permutations, product
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE_ORDERS = {
    "relaxed": ("relaxed", "relaxed"),
    "release-acquire": ("release", "acquire"),
    "seq-cst": ("seq_cst", "seq_cst"),
}
ITERATIONS = 50000
SAMPLES = 3


def total_orders(lean):
    outcomes = set()
    witnesses = []
    for order in permutations(("store-x", "load-y", "store-y", "load-x")):
        rank = {value: offset for offset, value in enumerate(order)}
        if rank["store-x"] < rank["load-y"] and rank["store-y"] < rank["load-x"]:
            values = [int(rank["store-y"] < rank["load-y"]), int(rank["store-x"] < rank["load-x"])]
            witnesses.append({"order": order, "loads": values})
            outcomes.add(tuple(values))
    assert len(witnesses) == 6 and outcomes == {(0, 1), (1, 0), (1, 1)}
    result = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Order.lean")],
                            text=True, check=True, capture_output=True)
    assert not result.stderr
    axioms = result.stdout.splitlines()
    assert len(axioms) == 2
    assert all("does not depend on any axioms" in row or "depends on axioms: [propext]" in row for row in axioms)
    return witnesses, axioms


def actual(root, compilers):
    samples = []
    for (name, compiler), (profile, (store, load)) in product(compilers.items(), NATIVE_ORDERS.items()):
        binary = root / (name + "-" + profile)
        result = subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-pthread",
             f"-DSTORE=memory_order_{store}", f"-DLOAD=memory_order_{load}", f"-DITERATIONS={ITERATIONS}",
             str(HERE / "probe.c"), "-o", str(binary)],
            cwd=root, capture_output=True, check=True,
        )
        assert not result.stderr
        for ordinal in range(1, SAMPLES + 1):
            sample = subprocess.run([str(binary)], cwd=root, capture_output=True,
                                    check=True, text=True, timeout=45)
            assert not sample.stderr
            values = list(map(int, sample.stdout.split()))
            assert len(values) == 4 and min(values) >= 0 and sum(values) == ITERATIONS
            if profile == "seq-cst":
                assert values[0] == 0
            samples.append({"compiler": name, "profile": profile, "trial": ordinal, "counts": values})
    return samples


def experiment(root):
    lean = os.environ.get("LEAN", "lean")
    tool = {"gcc": os.environ.get("GCC", "gcc"), "clang": os.environ.get("CLANG", "clang")}
    model, axioms = total_orders(lean)
    samples = actual(root, tool)
    versions = {name: subprocess.check_output([binary, "--version"], text=True).splitlines()[0]
                for name, binary in tool.items()}
    return {
        "format": "atomic-store-buffering-01", "kernels": axioms,
        "compiler": versions, "host_machine": os.uname().machine,
        "read_pair_order": ["00", "01", "10", "11"], "total_order_witnesses": model,
        "source_digests": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("Order.lean", "probe.c")},
    }, samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-atomic-buffering-") as directory:
        model, native = experiment(Path(directory))
    args.exact.write_text(json.dumps(model, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    args.native.write_text(json.dumps(native, sort_keys=True, indent=2) + "\n", encoding="utf-8")
