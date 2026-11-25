"""Specify and cross-check the common checked scalar backend fixture."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from operator import add, mul, sub
from pathlib import Path
import platform
from random import Random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIXTURE = HERE.parents[1] / "PROTOTYPES" / "LLVM-PRESERVATION-01"
sys.path.insert(0, str(FIXTURE))

from integer_fixture import SOURCE, compile_source, evaluate
from llvm_integer_probe import _BOUNDARIES

BASELINE = "7007a14dffa2417b2dae7da5e0bbed5ce698d667"
MODULUS = 1 << 32
SIGN = 1 << 31
SENTINEL = 0xABAD1234
ARITHMETIC = {"add": add, "sub": sub, "mul": mul}
OPERATIONS = (
    "wrap_add", "wrap_sub", "wrap_mul",
    "checked_sadd", "checked_ssub", "checked_smul",
    "checked_uadd", "checked_usub", "checked_umul",
    "checked_sdiv", "checked_srem", "checked_udiv", "checked_urem",
    "checked_shl", "checked_ashr", "checked_lshr",
)


def signed(word):
    return (word + SIGN) % MODULUS - SIGN


def oracle(operation, operands, a, b, enabled):
    if any(type(word) is not int or not 0 <= word < MODULUS for word in (a, b, enabled)):
        raise ValueError("expected three 32-bit input words")
    if enabled == 0:
        return "ok", b, (a, b)
    x, y = (a if name == "a" else b for name in operands)
    kind, instruction = operation.split("_", 1)
    if kind == "wrap":
        result = ARITHMETIC[instruction](x, y)
    elif instruction in ("shl", "lshr", "ashr"):
        if y >= 32:
            return "shift_count", SENTINEL, (a,)
        if instruction == "shl":
            result = x * (1 << y)
        else:
            result = (signed(x) if instruction == "ashr" else x) // (1 << y)
    else:
        is_signed = instruction[0] == "s"
        if is_signed:
            x, y = signed(x), signed(y)
        instruction = instruction[1:]
        lower, upper = (-SIGN, SIGN) if is_signed else (0, MODULUS)
        if instruction in ARITHMETIC:
            result = ARITHMETIC[instruction](x, y)
            if not lower <= result < upper:
                return "overflow", SENTINEL, (a,)
        else:
            if y == 0:
                return "zero_divisor", SENTINEL, (a,)
            if is_signed and x == -SIGN and y == -1:
                return "overflow", SENTINEL, (a,)
            quotient, remainder = divmod(abs(x), abs(y))
            if instruction == "div":
                result = -quotient if (x < 0) != (y < 0) else quotient
            else:
                assert instruction == "rem"
                result = -remainder if x < 0 else remainder
    bits = result % MODULUS
    return "ok", bits, (a, bits)


def pin(path):
    relative = str(path.relative_to(ROOT))
    archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
    assert archived == path.read_bytes()
    return hashlib.sha256(archived).hexdigest()


def refusals():
    valid = SOURCE.replace("operation", "checked_sadd")
    source_mutations = {
        "untyped_operation": valid.replace("checked_sadd", "unchecked_add"),
        "literal_operand": valid.replace("checked_sadd(a, b)", "checked_sadd(a, 1)"),
        "changed_effect_payload": valid.replace("emit(value)", "emit(value + 1)"),
        "missing_entry_callback": valid.replace("    emit(a)\n", ""),
        "extra_parameter": valid.replace("a, b, enabled", "a, b, enabled, extra"),
        "external_call": valid.replace("emit(value)", "other(value)"),
    }
    results = {}
    for name, source in source_mutations.items():
        try:
            compile_source(source)
        except ValueError as error:
            results[name] = {"source": source, "error": str(error)}
        else:
            raise AssertionError(name)
    input_mutations = {
        "negative_word": (-1, 0, 1), "out_of_range": (0, MODULUS, 1),
        "boolean_instead_of_word": (0, 0, False), "floating_input": (1.0, 0, 1),
    }
    for name, operands in input_mutations.items():
        try:
            oracle("checked_sadd", ("a", "b"), *operands)
        except ValueError as error:
            results[name] = {"input": operands, "error": str(error)}
        else:
            raise AssertionError(name)
    return results


def assess(output):
    rng = Random(134)
    pairs = [*product(_BOUNDARIES, repeat=2),
             *((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(256))]
    flags = (0, 1, 2, 0x80000000, 0xFFFFFFFF)
    inputs = [(a, b, flags_word) for (a, b), flags_word in product(pairs, flags)]
    assert len(inputs) == 3085
    full_digest = hashlib.sha256()
    statuses = Counter()
    programs = []
    projection_deltas = {}
    for operation, operands in product(OPERATIONS, product("ab", repeat=2)):
        left, right = operands
        source = SOURCE.replace("operation(a, b)", f"{operation}({left}, {right})")
        program = compile_source(source)
        assert (program.operation, program.operands) == (operation, operands)
        programs.append({"operation": operation, "operands": operands})
        for a, b, enabled in inputs:
            expected = oracle(operation, operands, a, b, enabled)
            seen = evaluate(program, a, b, bool(enabled))
            actual = (seen.status, SENTINEL if seen.value is None else seen.value, seen.events)
            assert actual == expected, (program, a, b, enabled, expected, actual)
            line = (json.dumps([operation, operands, a, b, enabled, expected],
                               separators=(",", ":")) + "\n").encode()
            full_digest.update(line)
            if output is not None:
                output.write(line)
            status, slot, events = expected
            statuses[status] += 1
            candidates = {
                "generic_failure": ("overflow" if status != "ok" else "ok", slot, events),
                "store_on_failure": (status, 0 if status != "ok" else slot, events),
                "reverse_callbacks": (status, slot, events[::-1]),
                "exact_one_enabled": (oracle(operation, operands, a, b, 0)
                                      if enabled not in (0, 1) else expected),
            }
            for name, alternate in candidates.items():
                counts = projection_deltas.setdefault(name, Counter(status=0, status_slot=0, complete=0))
                counts["status"] += alternate[0] != status
                counts["status_slot"] += alternate[:2] != expected[:2]
                counts["complete"] += alternate != expected
    assert len(programs) == 64
    archive = HERE.parent / "COMMON-BACKEND-RECEIPTS-01" / "evidence.json"
    recorded = json.loads(archive.read_text())
    assert dict(statuses) == recorded["statuses_per_profile"]
    assert sum(statuses.values()) == recorded["observations_per_profile"] == 197440
    return {
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "archived_sha256": {path.name: pin(path) for path in (
            FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py", archive)},
        "inputs": {"words": 3, "bits_per_word": 32, "boundary_values": _BOUNDARIES,
                   "seed": 134, "generated_pairs": 256, "enabled_words": flags},
        "abi_slot_initial_word": SENTINEL, "programs": programs, "vectors_per_program": len(inputs),
        "observations": sum(statuses.values()), "status_counts": dict(statuses),
        "expanded_observation_jsonl_sha256": full_digest.hexdigest(),
        "projection_mismatches": projection_deltas, "refusals": refusals(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args()
    if args.observations:
        with args.observations.open("wb") as stream:
            result = assess(stream)
    else:
        result = assess(None)
    print(json.dumps(result, indent=2, sort_keys=True))
