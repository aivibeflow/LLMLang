"""Probe stripped providers and scope acceptance to exact finite observations."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SPEC = {"input": "integer[-32,32]", "observation": "stdout line",
        "postcondition": ["eq", "result", ["sum", ["multiply", 2, "value"], 1]]}
SAMPLE = (-32, -16, -1, 0, 1, 16, 32)
FULL = tuple(range(-32, 33))
CONTROLS = (-33, 33)


def canonical_digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def command(args, payload=None):
    return subprocess.run(args, input=payload, text=True, capture_output=True,
                          check=True, timeout=40).stdout


def observe(path, inputs):
    payload = "".join(f"{value}\n" for value in inputs)
    return dict(zip(inputs, command([path], payload).splitlines(), strict=True))


def expected(value):
    return "outside" if not -32 <= value <= 32 else f"ok:{value + value + 1}"


def classify(receipt, expected_key, inputs):
    if receipt["key"] != expected_key:
        return "receipt-mismatch"
    if not set(inputs) <= set(receipt["observed_inputs"]):
        return "unverified-scope"
    if set(inputs) & set(receipt["failures"]):
        return "observed-divergence"
    return "finite-check-passed"


def run(cc, work):
    toolchain = command([cc, "--version"]).splitlines()[0]
    machine = platform.machine()
    contract = canonical_digest(SPEC)
    outcomes = []
    for optimization in ("-O0", "-O3"):
        binary_keys = {}
        for label in ("reference", "unsampled-change"):
            path = work / f"provider-{label}-{optimization[2:]}"
            flags = [] if label == "reference" else ["-DMUTANT_UNSAMPLED_CASE=1"]
            command([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-s", optimization,
                     *flags, HERE / "provider.c", "-o", path])
            key = {"artifact_sha256": sha256(path.read_bytes()).hexdigest(), "contract": contract,
                   "target": machine, "toolchain": toolchain, "observation": "stdio-int-line:v1"}
            binary_keys[label] = key
            sample_data = observe(path, SAMPLE)
            full_data = observe(path, (*FULL, *CONTROLS))
            assert all(full_data[value] == expected(value) for value in CONTROLS)
            assert all(sample_data[value] == full_data[value] for value in SAMPLE)

            def receipt(inputs, observations):
                return {"key": key, "observed_inputs": inputs,
                        "failures": [value for value in inputs if observations[value] != expected(value)],
                        "trace": canonical_digest([(value, observations[value]) for value in inputs])}

            sample = receipt(SAMPLE, sample_data)
            complete = receipt(FULL, full_data)
            assert sample["failures"] == []
            assert complete["failures"] == ([] if label == "reference" else [17])
            outcomes.append({
                "profile": [optimization, label], "sample": sample, "finite_domain": complete,
                "sample_receipt_on_sample_scope": classify(sample, key, SAMPLE),
                "sample_receipt_on_full_domain": classify(sample, key, FULL),
                "finite_domain_receipt": classify(complete, key, FULL),
            })
        assert binary_keys["reference"]["artifact_sha256"] != binary_keys["unsampled-change"]["artifact_sha256"]
        model = outcomes[-2]["sample"]
        assert classify(model, binary_keys["unsampled-change"], SAMPLE) == "receipt-mismatch"
        for field in ("contract", "target", "toolchain", "observation"):
            changed = {**model["key"], field: "other"}
            assert classify(model, changed, SAMPLE) == "receipt-mismatch"
    return {"python": platform.python_version(), "contract": SPEC,
            "profiles": outcomes,
            "profile_results": Counter(row["finite_domain_receipt"] for row in outcomes),
            "scope_controls": ["artifact_sha256", "contract", "target", "toolchain", "observation"],
            "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("provider.c", "check.py")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt12-opaque-") as temp:
        print(json.dumps(run(args.cc, Path(temp)), sort_keys=True, indent=2))
