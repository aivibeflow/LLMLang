"""Verify a guarded division specialization with Lean and native boundary cases."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from random import Random
import struct
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
MASK_64 = 2**64 - 1
SLOT = 0xBA0308CF_9951177B


def execute(*arguments):
    return subprocess.run(arguments, check=True, text=True, capture_output=True, timeout=40).stdout


def build(compiler, work, label, level, omit_guard):
    destination = work / f"{label}.so"
    execute(compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
            f"-O{level}", f"-DOMIT_GUARD={int(omit_guard)}",
            str(HERE / "probe.c"), "-o", str(destination))
    library = ctypes.CDLL(str(destination))
    function = library.divide
    function.argtypes = (
        ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint32),
    )
    function.restype = ctypes.c_int32
    return function, sha256(destination.read_bytes()).hexdigest()


def compare(function, inputs):
    slot = ctypes.c_uint64(SLOT)
    route = ctypes.c_uint32(777)
    status = function(*inputs, ctypes.byref(slot), ctypes.byref(route))
    return status, slot.value, route.value


def expected(n, divisor, enabled, receipt):
    if divisor == 0:
        return 1, SLOT, 0
    powers = divisor.bit_count() == 1
    return 0, n // divisor, 2 if powers and enabled and receipt == 1 else 1


def corpus():
    powers = tuple(2**value for value in range(64))
    divisors = tuple(sorted({0, MASK_64, *powers, *(p - 1 for p in powers), *(p + 1 for p in powers)}))
    numerators = (0, 1, 2, 3, 63, 255, 65535, 2**32, 2**63, MASK_64 - 1, MASK_64)
    rng = Random(331)
    pairs = (*product(numerators, divisors), *((rng.getrandbits(64), rng.getrandbits(64)) for _ in range(256)))
    return tuple((numerator, divisor, enabled, receipt)
                 for (numerator, divisor), enabled, receipt in product(pairs, (0, 1), (0, 1, 2)))


def verify(options, work):
    axioms = execute(options.lean, str(HERE / "Specialization.lean")).splitlines()
    if [row.split("'")[1] for row in axioms] != [
        "guarded_division_refines", "denominator_check_cannot_be_removed"
    ]:
        raise ValueError(axioms)
    inputs = corpus()
    validated = {}
    for (tool_name, compiler), level in product((("gcc", options.gcc), ("clang", options.clang)), (0, 3)):
        entry, identity = build(compiler, work, f"{tool_name}-O{level}", level, omit_guard=False)
        route_counts = Counter()
        observations = sha256()
        for values in inputs:
            actual = compare(entry, values)
            wanted = expected(*values)
            if actual != wanted:
                raise AssertionError((tool_name, level, values, wanted, actual))
            route_counts[actual[2]] += 1
            observations.update(struct.pack("<IQI", *actual))
        validated[f"{tool_name}-O{level}"] = {
            "artifact_sha256": identity, "observation_sha256": observations.hexdigest(),
            "route_counts": dict(sorted(route_counts.items())),
        }
    if len({profile["observation_sha256"] for profile in validated.values()}) != 1:
        raise AssertionError("Compiler profiles changed observations")

    weak, _ = build(options.gcc, work, "omitted-equality", 3, omit_guard=True)
    wrong = 0
    for values in inputs:
        actual = compare(weak, values)
        correct = expected(*values)
        wrong += actual[:2] != correct[:2]
    witness = (63, 6, 1, 1)
    if compare(weak, witness) != (0, 31, 2) or expected(*witness) != (0, 10, 1) or wrong == 0:
        raise AssertionError("The omitted-guard mutation was not distinguished")

    return {
        "toolchain": {
            "gcc": execute(options.gcc, "--version").splitlines()[0],
            "clang": execute(options.clang, "--version").splitlines()[0],
            "lean": execute(options.lean, "--version").strip(),
        },
        "proof_axioms": axioms,
        "cases_per_profile": len(inputs),
        "native_observations": len(inputs) * len(validated),
        "profiles": validated,
        "omitted_guard_control": {"wrong_value_or_status": wrong, "input": witness,
                                  "expected": expected(*witness), "observed": compare(weak, witness)},
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Specialization.lean", "probe.c", "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-guarded-specialization-") as work:
        print(json.dumps(verify(args, Path(work)), indent=2))
