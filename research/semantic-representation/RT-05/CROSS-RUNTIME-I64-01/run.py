#!/usr/bin/env python3
"""Compare exact signed integers across independent Python and native Node adapters."""

from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, make_snapshot
MIN, MAX = -(2**63), 2**63 - 1
MODES = {"number": "number", "safe_number": "number", "lexeme": "number", "text": "decimal", "hex": "hex"}
DECIMAL = re.compile(r"(?:0|-?[1-9][0-9]*)", flags=re.ASCII)
HEX = re.compile(r"[0-9a-f]{16}", flags=re.ASCII)
CONTROLS = {
    "exponent": '{"codec":"number","value":1e0}',
    "fraction_spelling": '{"codec":"number","value":1.0}',
    "negative_zero": '{"codec":"number","value":-0}',
    "number_overflow": '{"codec":"number","value":9223372036854775808}',
    "number_underflow": '{"codec":"number","value":-9223372036854775809}',
    "duplicate_number": '{"codec":"number","value":1,"value":2}',
    "reordered_number": '{"value":1,"codec":"number"}',
    "spaced_number": '{"codec":"number", "value":1}',
    "unknown_field": '{"codec":"number","note":"extra","value":1}',
    "bool_number": '{"codec":"number","value":true}',
    "exponent_decimal": '{"codec":"decimal","value":"1e0"}',
    "plus_decimal": '{"codec":"decimal","value":"+1"}',
    "zero_alias_decimal": '{"codec":"decimal","value":"01"}',
    "negative_zero_decimal": '{"codec":"decimal","value":"-0"}',
    "decimal_overflow": '{"codec":"decimal","value":"9223372036854775808"}',
    "escaped_decimal": r'{"codec":"decimal","value":"\u0031"}',
    "duplicate_decimal": '{"codec":"decimal","value":"1","value":"2"}',
    "uppercase_hex": '{"codec":"hex","value":"FFFFFFFFFFFFFFFF"}',
    "short_hex": '{"codec":"hex","value":"000000000000001"}',
    "long_hex": '{"codec":"hex","value":"00000000000000001"}',
    "prefixed_hex": '{"codec":"hex","value":"0x0000000000000001"}',
    "duplicate_hex": '{"codec":"hex","value":"0000000000000001","value":"0000000000000002"}',
}


def semantic(value):
    return {"status": "accepted", "decimal": str(value),
            "semantic": sha256(b"rt05-i64/1\0" + value.to_bytes(8, "big", signed=True)).hexdigest()}


def corpus():
    values = set(range(-10, 11))
    for pivot in (*(sign * 2**power for sign in (-1, 1) for power in (31, 32, 53)), MIN, MAX):
        values.update(n for n in range(pivot - 8, pivot + 9) if MIN <= n <= MAX)
    seeds = (sha256(f"rt05 i64 candidate {index}".encode()).digest()[:8] for index in range(40))
    values.update(int.from_bytes(seed, "big", signed=True) for seed in seeds)
    return sorted(values)


def wire(codec, value):
    if codec == "number":
        serialized = str(value)
    elif codec == "decimal":
        serialized = json.dumps(str(value))
    else:
        serialized = json.dumps(value.to_bytes(8, "big", signed=True).hex())
    return f'{{"codec":"{codec}","value":{serialized}}}'


def read_python(codec, encoded):
    parsed = json.loads(encoded)
    if set(parsed) != {"codec", "value"} or parsed["codec"] != codec:
        return None
    value = parsed["value"]
    if codec == "number":
        if type(value) is not int:
            return None
    elif codec == "decimal":
        if not isinstance(value, str) or not DECIMAL.fullmatch(value):
            return None
        value = int(value)
    else:
        if not isinstance(value, str) or not HEX.fullmatch(value):
            return None
        value = int.from_bytes(bytes.fromhex(value), "big", signed=True)
    if not MIN <= value <= MAX or wire(codec, value) != encoded:
        return None
    return semantic(value)


def native_version(name):
    return subprocess.check_output(["node", "-p", name], text=True, timeout=10).strip()


def run():
    values = corpus()
    data = [(value, policy, wire(codec, value)) for value in values for policy, codec in MODES.items()]
    negatives = [(name, policy, encoded) for name, encoded in CONTROLS.items() for policy in MODES]
    tasks = [[policy, encoded] for _, policy, encoded in [*data, *negatives]]
    completed = subprocess.run(["node", str(HERE / "decode.js")], input=json.dumps(tasks),
                               capture_output=True, text=True, check=True, timeout=20)
    native = json.loads(completed.stdout)
    assert len(native) == len(tasks)
    rows = []
    store = ContentStore()
    admitted = {policy: {} for policy in MODES}
    expected_graph = {f"literal/{index}": store.put("rt05-i64-literal-v1", {"type": "I64", "value": value})
                      for index, value in enumerate(values)}
    metrics = {policy: Counter() for policy in MODES}
    by_hash = {policy: defaultdict(list) for policy in MODES}
    for ordinal, ((value, policy, encoded), result) in enumerate(zip(data, native[:len(data)], strict=True)):
        slot = f"literal/{ordinal // len(MODES)}"
        exact = semantic(value)
        assert read_python(MODES[policy], encoded) == exact
        row = metrics[policy]
        row["accepted"] += result["status"] == "accepted"
        row["wrong_values"] += result["status"] == "accepted" and result != exact
        row["wire_bytes"] += len(encoded.encode())
        if result["status"] == "accepted":
            actual_number = int(result["decimal"])
            assert result == semantic(actual_number)
            admitted[policy][slot] = store.put("rt05-i64-literal-v1", {"type": "I64", "value": actual_number})
            by_hash[policy][result["semantic"]].append(value)
        rows.append({"input": str(value), "policy": policy, "wire": encoded,
                     "wire_sha256": sha256(encoded.encode()).hexdigest(),
                     "expected_identity": exact["semantic"], "node": result})
    for policy, classes in by_hash.items():
        metrics[policy]["merged_distinct_pairs"] = sum(
            1 for group in classes.values() for first, second in combinations(group, 2) if first != second)
    bad_rows = []
    for (name, policy, encoded), result in zip(negatives, native[len(data):], strict=True):
        if policy != "number":
            assert result["status"] != "accepted"
        metrics[policy]["accepted_controls"] += result["status"] == "accepted"
        bad_rows.append({"name": name, "policy": policy, "wire": encoded, "node": result})
    for encoded in CONTROLS.values():
        assert all(read_python(codec, encoded) is None for codec in set(MODES.values()))
    for policy in ("lexeme", "text", "hex"):
        assert metrics[policy]["accepted"] == len(values) and not metrics[policy]["wrong_values"]
    exact_root = make_snapshot(expected_graph).root_hash
    roots = {policy: make_snapshot(graph).root_hash for policy, graph in admitted.items()}
    assert {policy for policy, root in roots.items() if root == exact_root} == {"lexeme", "text", "hex"}
    assert metrics["number"]["wrong_values"] and metrics["number"]["merged_distinct_pairs"]
    assert metrics["safe_number"]["accepted"] < len(values) and not metrics["safe_number"]["wrong_values"]
    return {
        "schema": "llmlang-rt05-cross-runtime-i64/1", "python": platform.python_version(),
        "node": native_version("process.version"), "v8": native_version("process.versions.v8"),
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("run.py", "decode.js")},
        "distinct_values": len(values), "verify_routes": len(MODES), "control_inputs": len(CONTROLS),
        "baseline_snapshot": exact_root, "adapter_snapshots": roots,
        "metrics": metrics, "observations": rows, "controls": bad_rows,
    }


if __name__ == "__main__":
    result = run()
    observations = result.pop("observations")
    controls = result.pop("controls")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print('  ],\n  "controls": [')
    print(",\n".join("    " + json.dumps(row) for row in controls))
    print("  ]\n}")
