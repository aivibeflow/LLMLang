#!/usr/bin/env python3
"""Compare binary64 to signed i64 conversion constraints with exact native evidence."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import math
import os
from pathlib import Path
import platform
import random
import struct
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIGN = 1 << 63
FRACTION_MASK = (1 << 52) - 1
LIMIT = 1 << 63
UPPER_BITS = 0x43e0000000000000
SEED = 20261125
ORDINARY = (0, 1, FRACTION_MASK, 1 << 52, 0x3fdfffffffffffff, 0x3fe0000000000000,
            0x3fe0000000000001, 0x3fefffffffffffff, 0x3ff0000000000000, 0x3ff0000000000001,
            0x3ff8000000000000, 0x4004000000000000, 0x4330000000000000, 0x4340000000000000,
            0x7fefffffffffffff, 0x7ff0000000000000, 0x7ff0000000000001, 0x7ff8000000000000,
            0x7fffffffffffffff)
STRATA = (0, 1, 1021, 1022, 1023, 1074, 1075, 1076, 1085, 1086, 1087, 2046)


def corpus():
    directed = set(ORDINARY) | {UPPER_BITS + distance for distance in range(-8, 9)}
    values = {source | sign for source, sign in product(directed, (0, SIGN))}
    draw = random.Random(SEED)
    for exponent in STRATA:
        added = set()
        while len(added) < 12:
            candidate = draw.choice((0, SIGN)) | (exponent << 52) | draw.getrandbits(52)
            if candidate not in values:
                added.add(candidate)
        values.update(added)
    return sorted(values)


def decode(bits):
    negative = bool(bits & SIGN)
    exponent = (bits >> 52) & 0x7ff
    fraction = bits & FRACTION_MASK
    if exponent == 0x7ff:
        return {"kind": "nan" if fraction else "infinite", "negative": negative}
    mantissa = fraction if exponent == 0 else (1 << 52) | fraction
    shift = (max(exponent, 1) - 1023) - 52
    if shift >= 0:
        magnitude, remainder = mantissa << shift, 0
    else:
        magnitude, remainder = divmod(mantissa, 1 << -shift)
    return {"kind": "finite", "integer": -magnitude if negative else magnitude,
            "fractional": remainder != 0, "negative": negative}


def outcome(value):
    return f"v{value}"


def oracle(decoded):
    if decoded["kind"] != "finite":
        clamped = 0 if decoded["kind"] == "nan" else (-LIMIT if decoded["negative"] else LIMIT - 1)
        return {"trunc": "nonfinite", "exact": "nonfinite", "saturate": outcome(clamped),
                "wrap": "nonfinite", "weak_range": False, "python": "nonfinite"}
    integer = decoded["integer"]
    in_range = -LIMIT <= integer < LIMIT
    truncation = outcome(integer) if in_range else "range"
    clamped = min(LIMIT - 1, max(-LIMIT, integer))
    wrapped = (integer + LIMIT) % (2 * LIMIT) - LIMIT
    return {"trunc": truncation, "exact": "fraction" if decoded["fractional"] else truncation,
            "saturate": outcome(clamped), "wrap": "fraction" if decoded["fractional"] else outcome(wrapped),
            "weak_range": -LIMIT <= integer <= LIMIT, "python": outcome(integer)}


def word(bits):
    return f"{bits:016x}"


def python_int(bits):
    value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
    try:
        return outcome(int(value))
    except (OverflowError, ValueError):
        assert not math.isfinite(value)
        return "nonfinite"


def command(directory, *args, data=None):
    return subprocess.run(args, cwd=directory, input=data, check=True, capture_output=True, text=True,
                          timeout=45, env={**os.environ, "LC_ALL": "C"}).stdout


def native(directory, values):
    raw = "\n".join(map(word, values)) + "\n"
    configured = {}
    rounded_max = {}
    for opt in (0, 2):
        binary = directory / f"c-O{opt}"
        command(directory, "gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", f"-O{opt}",
                str(HERE / "observe.c"), "-lm", "-o", str(binary))
        first, *rows = command(directory, str(binary), data=raw).splitlines()
        rounded_max[f"c_O{opt}"] = first
        configured[f"c_O{opt}"] = [line.split() for line in rows]
    for opt in (0, 3):
        binary = directory / f"rust-O{opt}"
        command(directory, "rustc", "--edition", "2021", "-D", "warnings", "-C", f"opt-level={opt}",
                str(HERE / "observe.rs"), "-o", str(binary))
        first, *rows = command(directory, str(binary), data=raw).splitlines()
        rounded_max[f"rust_O{opt}"] = first
        configured[f"rust_O{opt}"] = [line.split() for line in rows]
    encoded = json.dumps(list(map(word, values)))
    for name, flags in (("node_default", []), ("node_jitless", ["--jitless"])):
        result = json.loads(command(directory, "node", *flags, str(HERE / "observe.js"), data=encoded))
        rounded_max[name] = result["roundedMax"]
        configured[name] = result["rows"]
    configured["python"] = [python_int(bits) for bits in values]
    rounded_max["python"] = struct.pack(">d", float(LIMIT - 1)).hex()
    assert set(rounded_max.values()) == {word(UPPER_BITS)}
    assert all(len(result) == len(values) for result in configured.values())
    assert configured["c_O0"] == configured["c_O2"]
    assert configured["rust_O0"] == configured["rust_O3"]
    assert configured["node_default"] == configured["node_jitless"]
    return configured, rounded_max


def evaluate(bits, profiles, index):
    spec = decode(bits)
    expected = oracle(spec)
    c = profiles["c_O0"][index]
    rust = profiles["rust_O0"][index]
    node = profiles["node_default"][index]
    assert c == [expected["trunc"], expected["exact"], str(int(expected["weak_range"]))], (word(bits), c, expected)
    assert rust == [expected["trunc"], expected["exact"], expected["saturate"]]
    assert node == [expected["trunc"], expected["exact"], expected["wrap"], expected["weak_range"]]
    assert profiles["python"][index] == expected["python"]
    if spec["kind"] == "finite":
        spec["integer"] = str(spec["integer"])
    return {"input": word(bits), "exact_source": spec, "checked_trunc": c[0], "checked_integral": c[1],
            "rust_saturate": rust[2], "node_wrap_integral": node[2], "weak_float_bound_admits": node[3],
            "cpython_unbounded_int": profiles["python"][index]}


def run(directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    words = corpus()
    profiles, rounded_max = native(directory, words)
    observations = [evaluate(bits, profiles, index) for index, bits in enumerate(words)]
    fields = ("checked_trunc", "checked_integral", "rust_saturate", "node_wrap_integral", "cpython_unbounded_int")
    summary = {}
    for field in fields:
        counts = Counter({"accepted": 0, "range": 0, "fraction": 0, "nonfinite": 0})
        for row in observations:
            status = row[field]
            counts["accepted" if status.startswith("v") else status] += 1
        summary[field] = {**counts, "different_from_checked_trunc": sum(row[field] != row["checked_trunc"] for row in observations)}
    weak_mistakes = [row["input"] for row in observations if row["weak_float_bound_admits"] and row["checked_trunc"] == "range"]
    assert weak_mistakes == [word(UPPER_BITS)]
    assert summary["rust_saturate"]["accepted"] == len(words)
    return {"schema": "llmlang-rt05-f64-i64-conversion/1", "python": platform.python_version(),
            "gcc": command(directory, "gcc", "--version").splitlines()[0], "rustc": command(directory, "rustc", "-vV").splitlines(),
            "node": command(directory, "node", "--version").strip(), "v8": command(directory, "node", "-p", "process.versions.v8").strip(),
            "sources": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("run.py", "observe.c", "observe.rs", "observe.js")},
            "seed": SEED, "inputs": len(words), "profiles": list(profiles), "metrics": summary,
            "rounded_INT64_MAX": rounded_max, "weak_bound_false_admissions": weak_mistakes,
            "observations": observations}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-f64-i64-") as scratch:
        result = run(Path(scratch))
    values = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in values))
    print("  ]\n}")
