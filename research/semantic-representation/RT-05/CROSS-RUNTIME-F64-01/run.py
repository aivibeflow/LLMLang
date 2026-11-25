#!/usr/bin/env python3
"""Compare exact and quotient F64 identities across native numerical observation routes."""

from collections import Counter
from hashlib import sha256
from itertools import combinations
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
DOMAIN = b"llmlang-rt05-cross-runtime-f64/1\0"
SIGN = 1 << 63
EXPONENT = 0x7ff0000000000000
QUIET = 1 << 51
CANONICAL_NAN = EXPONENT | QUIET
MIN_NORMAL = 1 << 52
SEED = 20261125
POLICIES = ("exact_bits", "canonical_nan", "same_value_zero", "json_number")
DIRECTED = (
    0, 1, 2, MIN_NORMAL - 1, MIN_NORMAL, MIN_NORMAL + 1, 0x3fefffffffffffff, 0x3ff0000000000000,
    0x3ff0000000000001, 0x4000000000000000, 0x7fefffffffffffff, EXPONENT,
)
NAN_FRACTIONS = (1, 2, 0x100, 1 << 50, (1 << 50) + 123, QUIET - 1)


def tagged(bits):
    return json.dumps({"kind": "f64-bits", "bits": bits}, separators=(",", ":"))


def hex_bits(bits):
    return f"{bits:016x}"


CONTROLS = (
    ("tagged", tagged("8000000000000000"), "accepted"),
    ("tagged", tagged("7ff0000000000001"), "accepted"),
    ("tagged", tagged("7FF8000000000000"), "shape"),
    ("tagged", tagged("000000000000000"), "shape"),
    ("tagged", tagged("00000000000000000"), "shape"),
    ("tagged", ' {"kind":"f64-bits","bits":"0000000000000000"}', "noncanonical"),
    ("tagged", '{"bits":"0000000000000000","kind":"f64-bits"}', "noncanonical"),
    ("tagged", '{"kind":"f64-bits","bits":"8000000000000000","bits":"0000000000000000"}', "noncanonical"),
    ("tagged", '{"kind":"i64-bits","bits":"0000000000000000"}', "shape"),
    ("tagged", '{"kind":"f64-bits","bits":0}', "shape"),
    ("tagged", '{"kind":"f64-bits"', "syntax"),
    ("number", "-0", "accepted"),
    ("number", "-0.0", "accepted"),
    ("number", "1e309", "nonfinite-or-nonnumber"),
    ("number", "null", "nonfinite-or-nonnumber"),
    ("number", "NaN", "syntax"),
)


def category(bits):
    magnitude = bits & (SIGN - 1)
    if magnitude > EXPONENT:
        return "nan"
    if magnitude == EXPONENT:
        return "infinite"
    if magnitude == 0:
        return "zero"
    return "subnormal" if magnitude < MIN_NORMAL else "normal"


def corpus():
    inputs = {sign | bits for sign in (0, SIGN) for bits in DIRECTED}
    inputs.update(sign | EXPONENT | quiet | fraction for sign in (0, SIGN) for quiet in (0, QUIET)
                  for fraction in NAN_FRACTIONS)
    inputs.update((CANONICAL_NAN, SIGN | CANONICAL_NAN))
    generated = random.Random(SEED)
    target = len(inputs) + 160
    while len(inputs) < target:
        source = generated.getrandbits(64)
        if source & EXPONENT != EXPONENT:
            inputs.add(source)
    return sorted(inputs)


def projections(bits):
    normalized = CANONICAL_NAN if category(bits) == "nan" else bits
    zero_quotient = 0 if normalized == SIGN else normalized
    return bits, normalized, zero_quotient


def python_native(bits):
    value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
    decoded = struct.pack(">d", value).hex()
    boxed = struct.pack(">d", [value][0]).hex()
    class_name = category(bits)
    if math.isnan(value):
        inverse = "nan"
    else:
        reciprocal = math.copysign(math.inf, value) if value == 0.0 else 1.0 / value
        inverse = struct.pack(">d", reciprocal).hex()
    return {"scalar": decoded, "boxed": boxed, "numeric": [class_name, value == value, inverse]}


def python_number(raw):
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "syntax"}
    if type(decoded) not in (int, float) or not math.isfinite(decoded):
        return {"status": "nonfinite-or-nonnumber"}
    return {"status": "accepted", "bits": struct.pack(">d", float(decoded)).hex()}


def command(directory, *args, data=None):
    result = subprocess.run(args, cwd=directory, input=data, text=True, capture_output=True, check=True, timeout=45,
                            env={**os.environ, "LC_ALL": "C"})
    return result.stdout


def run_node(directory, inputs, *args):
    rows = [[hex_bits(bits), [tagged(hex_bits(variant)) for variant in projections(bits)]] for bits in inputs]
    controls = [[policy, wire] for policy, wire, _ in CONTROLS]
    return json.loads(command(directory, "node", *args, str(HERE / "observe.js"),
                              data=json.dumps({"rows": rows, "controls": controls})))


def run_rust(directory, inputs, opt):
    executable = directory / f"rust-O{opt}"
    command(directory, "rustc", "--edition", "2021", "-D", "warnings", "-C", f"opt-level={opt}",
            str(HERE / "observe.rs"), "-o", str(executable))
    raw = command(directory, str(executable), data="\n".join(map(hex_bits, inputs)))
    results = []
    for line in raw.splitlines():
        scalar, boxed, category_name, reflexive, inverse = line.split()
        assert reflexive in ("true", "false")
        results.append({"scalar": scalar, "boxed": boxed, "numeric": [category_name, reflexive == "true", inverse]})
    return results


def graph_hash(bits):
    return sha256(DOMAIN + bytes.fromhex(bits)).hexdigest()


def evaluate(directory, inputs):
    profiles = {"node_default": run_node(directory, inputs), "node_jitless": run_node(directory, inputs, "--jitless")}
    raw = {name: data["rows"] for name, data in profiles.items()}
    raw["rust_O0"] = run_rust(directory, inputs, 0)
    raw["rust_O3"] = run_rust(directory, inputs, 3)
    raw["python"] = [python_native(bits) for bits in inputs]
    assert all(len(rows) == len(inputs) for rows in raw.values())
    metrics = {policy: Counter({"accepted": 0, "refused": 0, "changed_literal_bits": 0,
                                "changed_numeric_observations": 0, "merged_literal_pairs": 0,
                                "merged_numerically_distinct_pairs": 0}) for policy in POLICIES}
    representation_drifts = {name: {"scalar": 0, "boxed": 0} for name in raw}
    observations = []
    for index, bits in enumerate(inputs):
        expected = hex_bits(bits)
        native = {name: rows[index] for name, rows in raw.items()}
        numeric = native["python"]["numeric"]
        assert all(result["numeric"] == numeric for result in native.values()), (expected, native)
        for name, result in native.items():
            for probe in ("scalar", "boxed"):
                representation_drifts[name][probe] += result[probe] != expected
        node = native["node_default"]
        jitless = native["node_jitless"]
        assert (node["tagged"], node["number"]) == (jitless["tagged"], jitless["number"])
        expected_projections = [hex_bits(value) for value in projections(bits)]
        for received, projection in zip(node["tagged"], expected_projections, strict=True):
            assert received["status"] == "accepted" and received["bits"] == projection
            assert received["numeric"] == python_native(int(projection, 16))["numeric"]
        python_json = python_number(node["numberWire"])
        assert python_json == {key: value for key, value in node["number"].items() if key != "numeric"}
        decisions = dict(zip(POLICIES, [*node["tagged"], node["number"]], strict=True))
        for policy, row in decisions.items():
            counts = metrics[policy]
            if row["status"] == "accepted":
                counts["accepted"] += 1
                counts["changed_literal_bits"] += row["bits"] != expected
                counts["changed_numeric_observations"] += row["numeric"] != numeric
                row["graph_hash"] = graph_hash(row["bits"])
            else:
                counts["refused"] += 1
        observations.append({"bits": expected, "category": category(bits), "numeric": numeric,
                             "representations": {key: [row["scalar"], row["boxed"]] for key, row in native.items()},
                             "number_wire": node["numberWire"], "decisions": decisions})
    for left, right in combinations(observations, 2):
        for policy in POLICIES:
            a, b = left["decisions"][policy], right["decisions"][policy]
            if a.get("graph_hash") is not None and a.get("graph_hash") == b.get("graph_hash"):
                metrics[policy]["merged_literal_pairs"] += 1
                metrics[policy]["merged_numerically_distinct_pairs"] += left["numeric"] != right["numeric"]
    controls = []
    for (policy, wire, expected), default, jitless in zip(CONTROLS, profiles["node_default"]["controls"],
                                                           profiles["node_jitless"]["controls"], strict=True):
        assert default == jitless and default["status"] == expected
        row = {"policy": policy, "wire": wire, "node": default}
        if policy == "number":
            row["python"] = python_number(wire)
            if wire == "-0":
                assert default["bits"] == "8000000000000000" and row["python"]["bits"] == "0000000000000000"
            if wire == "-0.0":
                assert default["bits"] == row["python"]["bits"] == "8000000000000000"
        controls.append(row)
    expected_same_value_zero = len(set(projections(bits)[2] for bits in inputs))
    assert all(result["nativeSameValueZeroKeys"] == expected_same_value_zero for result in profiles.values())
    assert metrics["exact_bits"]["changed_literal_bits"] == metrics["exact_bits"]["merged_literal_pairs"] == 0
    assert metrics["canonical_nan"]["changed_numeric_observations"] == 0 < metrics["canonical_nan"]["changed_literal_bits"]
    assert metrics["same_value_zero"]["merged_numerically_distinct_pairs"] == 1
    return metrics, representation_drifts, observations, controls, expected_same_value_zero


def run(directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    inputs = corpus()
    metrics, drifts, observations, controls, distinct_same_value_zero = evaluate(directory, inputs)
    return {"schema": DOMAIN.rstrip(b"\0").decode(), "python": platform.python_version(),
            "node": command(directory, "node", "--version").strip(),
            "v8": command(directory, "node", "-p", "process.versions.v8").strip(),
            "rustc": command(directory, "rustc", "-vV").splitlines(), "seed": SEED,
            "sources": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("run.py", "observe.rs", "observe.js")},
            "inputs": len(inputs), "categories": Counter(map(category, inputs)), "native_profiles": len(drifts),
            "metrics": metrics, "native_bit_copy_drifts": drifts, "native_node_set_keys": distinct_same_value_zero,
            "controls": controls, "observations": observations}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-f64-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in observations))
    print("  ]\n}")
