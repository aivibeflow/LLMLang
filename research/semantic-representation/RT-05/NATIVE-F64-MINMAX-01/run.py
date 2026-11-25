#!/usr/bin/env python3
"""Compare native binary64 min/max behavior with explicit typed policies."""

from hashlib import sha256
from itertools import combinations, product
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SCHEMA = "llmlang-rt05-native-f64-minmax/1"
SIGN = 1 << 63
MASK = (1 << 64) - 1
INF = 0x7ff0000000000000
QUIET = 1 << 51
NAN = INF | QUIET
FINITE_AND_INFINITY = (0, 1, 0x000fffffffffffff, 0x0010000000000000, 0x3fefffffffffffff,
                       0x3ff0000000000000, 0x3ff0000000000001, INF - 1, INF)
NAN_PAYLOADS = (0, 1, 0x100, 1 << 50)
POLICIES = ("propagate", "prefer_number", "prefer_number_left", "prefer_number_right", "ordered_left", "unordered_right",
            "signal_propagates_right")
PROFILE_GROUPS = {"glibc": ("glibc_O0", "glibc_O2"), "sse2": ("sse2_O0", "sse2_O2"),
                  "rust": ("rust_O0", "rust_O3"), "node": ("node_default", "node_jitless"), "python": ("python",)}


def is_nan(bits):
    return bits & (SIGN - 1) > INF


def is_signaling(bits):
    return is_nan(bits) and not bits & QUIET


def normalize(bits):
    return NAN if is_nan(bits) else bits


def number_order(bits):
    return (bits ^ MASK) if bits & SIGN else bits | SIGN


def ordered_pair(left, right):
    if number_order(left) <= number_order(right):
        return left, right
    return right, left


def reference(policy, left, right):
    left_nan, right_nan = is_nan(left), is_nan(right)
    equal = (left == right) or ((left | right) == SIGN)
    if policy == "ordered_left" and (left_nan or right_nan or equal):
        return left, left
    if policy == "unordered_right" and (left_nan or right_nan or equal):
        return right, right
    if left_nan or right_nan:
        if (policy == "propagate" or left_nan and right_nan or
                policy == "signal_propagates_right" and (is_signaling(left) or is_signaling(right))):
            return NAN, NAN
        remaining = right if left_nan else left
        return remaining, remaining
    if equal and policy == "prefer_number_left":
        return left, left
    if equal and policy in ("prefer_number_right", "signal_propagates_right"):
        return right, right
    return ordered_pair(left, right)


def corpus():
    words = {sign | value for sign in (0, SIGN) for value in FINITE_AND_INFINITY}
    words.update(sign | INF | quiet | payload for sign, quiet, payload in product((0, SIGN), (0, QUIET), NAN_PAYLOADS)
                 if quiet or payload)
    return sorted(words)


def word(bits):
    return f"{bits:016x}"


def to_float(bits):
    return struct.unpack(">d", bits.to_bytes(8, "big"))[0]


def from_float(value):
    return int.from_bytes(struct.pack(">d", value), "big")


def python_pair(a, b):
    left, right = map(to_float, (a, b))
    return from_float(min(left, right)), from_float(max(left, right))


def cmd(directory, *arguments, data=None):
    process = subprocess.run(arguments, cwd=directory, input=data, text=True, capture_output=True, check=True, timeout=40,
                             env={**os.environ, "LC_ALL": "C"})
    return process.stdout


def native(directory, pairs):
    lines = "\n".join(f"{word(a)} {word(b)}" for a, b in pairs) + "\n"
    result = {}
    c_artifacts = {}
    for opt in (0, 2):
        binary = directory / f"c-O{opt}"
        cmd(directory, "gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", f"-O{opt}", "-msse2",
            "-fno-builtin-fmin", "-fno-builtin-fmax", str(HERE / "observe.c"), "-lm", "-o", str(binary))
        instructions = set(re.findall(r"\b(?:minsd|maxsd)\b", cmd(directory, "objdump", "-d", str(binary))))
        imports = set(re.findall(r"\b(?:fmin|fmax)@[^\s]+", cmd(directory, "nm", "-D", str(binary))))
        assert instructions == {"minsd", "maxsd"}
        assert {name.split("@")[0] for name in imports} == {"fmin", "fmax"}
        c_artifacts[f"O{opt}"] = {"sse2_instructions": sorted(instructions), "libm_imports": sorted(imports)}
        rows = [tuple(int(item, 16) for item in row.split()) for row in cmd(directory, str(binary), data=lines).splitlines()]
        assert all(len(row) == 4 for row in rows)
        result[f"glibc_O{opt}"] = [row[:2] for row in rows]
        result[f"sse2_O{opt}"] = [row[2:] for row in rows]
    for opt in (0, 3):
        binary = directory / f"rust-O{opt}"
        cmd(directory, "rustc", "--edition", "2021", "-D", "warnings", "-C", f"opt-level={opt}",
            str(HERE / "observe.rs"), "-o", str(binary))
        result[f"rust_O{opt}"] = [tuple(int(item, 16) for item in row.split())
                                 for row in cmd(directory, str(binary), data=lines).splitlines()]
    wire = json.dumps([[word(a), word(b)] for a, b in pairs])
    for tag, flags in (("default", []), ("jitless", ["--jitless"])):
        raw = cmd(directory, "node", *flags, str(HERE / "observe.js"), data=wire)
        result[f"node_{tag}"] = [tuple(int(item, 16) for item in row) for row in json.loads(raw)]
    result["python"] = [python_pair(a, b) for a, b in pairs]
    assert all(len(rows) == len(pairs) and all(len(row) == 2 for row in rows) for rows in result.values())
    return result, c_artifacts


def summarize(values, pairs, observations):
    for family, profiles in PROFILE_GROUPS.items():
        assert all(observations[profile] == observations[profiles[0]] for profile in profiles), family
    oracle = {policy: [tuple(map(normalize, reference(policy, a, b))) for a, b in pairs] for policy in POLICIES}
    metrics = {}
    pair_indexes = {pair: index for index, pair in enumerate(pairs)}
    for family, profiles in PROFILE_GROUPS.items():
        actual = observations[profiles[0]]
        numeric = [tuple(map(normalize, vector)) for vector in actual]
        mismatches = {policy: sum(a != b for a, b in zip(numeric, expected, strict=True))
                      for policy, expected in oracle.items()}
        swapped = [(pair_indexes[(a, b)], pair_indexes[(b, a)]) for a, b in combinations(values, 2)]
        metrics[family] = {"policy_mismatches": mismatches,
                           "unordered_pairs_changing_bits_on_swap": sum(actual[a] != actual[b] for a, b in swapped),
                           "unordered_pairs_changing_numeric_on_swap": sum(numeric[a] != numeric[b] for a, b in swapped)}
    return metrics


def run(directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    values = corpus()
    pairs = list(product(values, repeat=2))
    observations, c_artifacts = native(directory, pairs)
    metrics = summarize(values, pairs, observations)
    observed_models = {"python": "ordered_left", "node": "propagate", "sse2": "unordered_right",
                       "glibc": "signal_propagates_right", "rust": "prefer_number_left"}
    assert all(metrics[family]["policy_mismatches"][policy] == 0 for family, policy in observed_models.items())
    return {"schema": SCHEMA, "python": platform.python_version(), "gcc": cmd(directory, "gcc", "--version").splitlines()[0],
            "glibc": cmd(directory, "ldd", "--version").splitlines()[0], "rustc": cmd(directory, "rustc", "-vV").splitlines(),
            "node": cmd(directory, "node", "--version").strip(), "v8": cmd(directory, "node", "-p", "process.versions.v8").strip(),
            "sources": {name: sha256((HERE / name).read_bytes()).hexdigest()
                        for name in ("run.py", "observe.c", "observe.rs", "observe.js")},
            "input_words": list(map(word, values)), "nan_words": sum(map(is_nan, values)), "ordered_pairs": len(pairs),
            "unordered_distinct_pairs": len(values) * (len(values) - 1) // 2, "profiles": PROFILE_GROUPS,
            "objdump": cmd(directory, "objdump", "--version").splitlines()[0], "c_artifacts": c_artifacts,
            "metrics": metrics,
            "observations": [{"operands": [word(a), word(b)],
                              "results": {family: list(map(word, observations[profiles[0]][index]))
                                          for family, profiles in PROFILE_GROUPS.items()}}
                             for index, (a, b) in enumerate(pairs)]}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-minmax-") as scratch:
        outcome = run(Path(scratch))
    rows = outcome.pop("observations")
    print(json.dumps(outcome, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in rows))
    print("  ]\n}")
