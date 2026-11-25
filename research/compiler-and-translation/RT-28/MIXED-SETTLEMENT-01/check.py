"""Check a scoped C and Python migration unit with an independently evaluated contract."""

import argparse
from collections import Counter
import ctypes as ct
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SENTINEL = 123456789
MIN, MAX = -(2**31), 2**31 - 1
VALUES = (MIN, MIN + 1, -2**30, -100, -1, 0, 1, 100, 2**30, MAX - 1, MAX)
FACTORS = (-9, -8, -7, -2, -1, 0, 1, 2, 7, 8, 9)
OFFSETS = (MIN, MIN + 1, -100, -1, 0, 1, 100, MAX - 1, MAX)


class CObservation(ct.Structure):
    _fields_ = [("tag", ct.c_int32), ("output", ct.c_int32)]


def contract(value, factor, offset):
    if abs(factor) > 8:
        return 2, SENTINEL
    # The signed 32-bit interval contains exactly the values fitting this shifted range.
    unsigned_index = value * factor + offset + 2**31
    if unsigned_index in range(2**32):
        return 0, unsigned_index - 2**31
    return 1, SENTINEL


def mirror(value, factor, offset, omit_range=False):
    if not -8 <= factor <= 8:
        return (2, SENTINEL)
    result = value * factor + offset
    if not omit_range and not MIN <= result <= MAX:
        return (1, SENTINEL)
    return (0, result)


def load(path):
    library = ct.CDLL(str(path))
    library.source_update.argtypes = (ct.c_int32, ct.c_int32, ct.c_int32, ct.POINTER(ct.c_int32))
    library.source_update.restype = ct.c_int
    library.native_observation.argtypes = (ct.c_int32,) * 3
    library.native_observation.restype = CObservation
    return library


def observe(library, args, conceal_output=False):
    native = library.native_observation(*args)
    output = ct.c_int32(SENTINEL)
    tag = library.source_update(*args, ct.byref(output))
    copied = SENTINEL if conceal_output else output.value
    return (native.tag, native.output), (tag, copied)


def classify(expected, native, adapter, translated):
    if native != expected:
        return "source"
    if adapter != native:
        return "adapter"
    if translated != expected:
        return "mirror"
    return "matched"


def execute(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=60).stdout


def compare(compilers, scratch):
    cases = list(product(VALUES, FACTORS, OFFSETS))
    expected_counts = Counter(contract(*args)[0] for args in cases)
    receipts = []
    for compiler in compilers:
        metadata = execute([compiler, "--version"]).splitlines()[0]
        for optimization in ("-O0", "-O3"):
            prefix = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", optimization]
            good_path = scratch / f"good-{len(receipts)}.so"
            mutant_path = scratch / f"mutant-{len(receipts)}.so"
            execute([*prefix, HERE / "unit.c", "-o", good_path])
            execute([*prefix, "-DMUTANT_EARLY_WRITE=1", HERE / "unit.c", "-o", mutant_path])
            original, mutated = load(good_path), load(mutant_path)
            baseline = Counter()
            mutations = Counter()
            examples = {}
            for args in cases:
                expected = contract(*args)
                native, adapter = observe(original, args)
                translated = mirror(*args)
                baseline[classify(expected, native, adapter, translated)] += 1
                wrong_native, wrong_adapter = observe(mutated, args)
                hidden_native, hidden_adapter = observe(original, args, conceal_output=True)
                profiles = {
                    "source": (wrong_native, wrong_adapter, translated),
                    "adapter": (hidden_native, hidden_adapter, translated),
                    "mirror": (native, adapter, mirror(*args, omit_range=True)),
                }
                for expected_owner, observations in profiles.items():
                    source_result, adapter_result, mirror_result = observations
                    owner = classify(expected, source_result, adapter_result, mirror_result)
                    if owner != "matched":
                        assert owner == expected_owner
                        mutations[owner] += 1
                        examples.setdefault(owner, {
                            "input": args, "expected": expected, "native": source_result,
                            "adapter": adapter_result, "mirror": mirror_result,
                        })
            assert baseline == {"matched": len(cases)}
            assert mutations["source"] == mutations["mirror"] == expected_counts[1]
            assert mutations["adapter"] >= 1
            receipts.append({"compiler": metadata, "flags": optimization,
                             "baseline": baseline, "injected_divergences": mutations,
                             "first_divergences": examples,
                             "elf_sha256": {"baseline": sha256(good_path.read_bytes()).hexdigest(),
                                            "source_mutant": sha256(mutant_path.read_bytes()).hexdigest()}})
    return {"cases_per_profile": len(cases), "contract_outcomes": dict(expected_counts),
            "profiles": receipts, "python": platform.python_version(), "system": platform.machine(),
            "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                               for name in ("check.py", "unit.c")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", action="append", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt28-mixed-settlement-") as temp:
        print(json.dumps(compare(args.cc, Path(temp)), sort_keys=True, indent=2))
