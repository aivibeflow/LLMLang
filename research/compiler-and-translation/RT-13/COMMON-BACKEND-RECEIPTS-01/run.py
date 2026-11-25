"""Audit common inputs and recorded observations across implemented scalar backends."""

import hashlib
import json
from pathlib import Path
import platform


HERE = Path(__file__).resolve()
RT13 = HERE.parents[1]
SOURCES = HERE.parents[2] / "PROTOTYPES" / "LLVM-PRESERVATION-01"
NATIVE = {
    "cpp": ("GENERATED-CPP-INTEGERS-01", "input_sha256", "lower_cpp.py"),
    "go": ("GENERATED-GO-INTEGERS-01", "input_sha256", "lower_go.py"),
    "java": ("GENERATED-JAVA-INTEGERS-01", "input_sha256", "lower_java.py"),
    "rust-and-llvm": ("GENERATED-RUST-INTEGERS-01", "input_sources_sha256", "lower_rust.py"),
}
EXPECTED_PROFILES = {
    "cpp": {"clangxx_O0", "clangxx_O3", "gxx_O0", "gxx_O3"},
    "go": {"c_shared", "standalone"},
    "java": {"compiled", "interpreted"},
    "rust-and-llvm": {"llvm_O0", "llvm_O3", "rust_O0", "rust_O3"},
}


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def study():
    pins = {name: digest(SOURCES / name) for name in ("integer_fixture.py", "llvm_integer_probe.py")}
    rows = {}
    expected_statuses = {"ok": 146048, "overflow": 25120, "shift_count": 25056, "zero_divisor": 1216}
    observations = sum(expected_statuses.values())
    for group, (directory, input_key, emitter) in NATIVE.items():
        receipt = RT13 / directory / "evidence.json"
        evidence = json.loads(receipt.read_text())
        documented = evidence[input_key]
        assert all(documented[name] == value for name, value in pins.items())
        assert documented[emitter] == digest(RT13 / directory / emitter)
        assert evidence["programs"] == 64 and evidence["vectors"] == 3085
        assert evidence["programs"] * evidence["vectors"] == observations
        assert set(evidence["profiles"]) == EXPECTED_PROFILES[group]
        for profile in evidence["profiles"].values():
            assert profile["observations"] == observations
            assert profile["statuses"] == expected_statuses
        rows[group] = {
            "receipt_sha256": digest(receipt), "emitter_sha256": documented[emitter],
            "profiles": sorted(evidence["profiles"]),
        }

    count = sum(len(row["profiles"]) for row in rows.values())
    assert count == 12
    return {
        "python": platform.python_version(), "common_source_pins": pins, "programs": 64,
        "vectors_per_program": 3085, "observations_per_profile": observations,
        "observations_across_archived_profiles": count * observations,
        "statuses_per_profile": expected_statuses, "groups": rows,
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
