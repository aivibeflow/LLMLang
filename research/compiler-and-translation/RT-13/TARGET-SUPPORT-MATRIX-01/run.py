"""Check evidence pins and model the scopes that a target support claim may use."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
EXPECTED_FIELDS = {
    "architecture_and_cpu", "os", "abi", "object_format", "linker", "sysroot_and_libraries",
    "runtime", "toolchain", "level", "evidence", "claim", "id",
}


def load_studies(sources):
    verified = {}
    for name, source in sources.items():
        path = (RESEARCH / source["path"]).resolve()
        assert path.is_relative_to(RESEARCH)
        blob = path.read_bytes()
        assert sha256(blob).hexdigest() == source["sha256"], path
        verified[name] = json.loads(blob)
    return verified


def check_ledgers(studies):
    linux = studies["linux"]["builds"]
    assert linux["x86_64"]["0"]["observation"] == "native"
    assert linux["aarch64"]["0"]["observation"] == "qemu_linux_user"
    assert sum(len(row["cases"]) for builds in linux.values() for row in builds.values()) == 24
    assert studies["cortex"]["profiles"]["exact_sections"]["uart"] == "20c 207!"
    wasm = studies["wasm"]
    assert len(wasm["builds"]) == 3 and len(wasm["node"]) == 2
    for row in wasm["builds"].values():
        assert all(host["scenarios"]["selected"]["effectMismatches"] == 0
                   for host in row["host_observations"].values())
    atomic = studies["atomics"]
    assert atomic["native_machine"] == "rv64-virt" and atomic["native_harts"] == 2
    assert set(atomic["rv64_no_a_undefined"]) == {
        "__atomic_fetch_add_1", "__atomic_fetch_add_4", "__atomic_load_1", "__atomic_store_1",
    }
    assert {"rv64_O0", "rv64_zabha_O0", "aarch64_O0", "aarch64_lse_O0"} <= atomic["profiles"].keys()
    assert studies["by_value"]["native_observations"] == 2048


def exact_scope(profile, required_level, required_claim):
    covered = profile["level"] == required_level and profile["claim"] == required_claim and profile["evidence"]
    return "covered" if covered else "unverified"


def study():
    path = HERE / "matrix.json"
    matrix = json.loads(path.read_text())
    assert matrix["schema"] == "target-support-evidence-v1"
    studies = load_studies(matrix["sources"])
    check_ledgers(studies)
    profiles = {}
    for row in matrix["profiles"]:
        assert set(row) == EXPECTED_FIELDS
        assert all(row[name] for name in EXPECTED_FIELDS - {"evidence"})
        assert row["id"] not in profiles
        assert (row["evidence"] in matrix["sources"]) == (row["level"] != "unknown")
        profiles[row["id"]] = row
    counts = Counter(row["level"] for row in profiles.values())
    assert dict(counts) == {"native": 2, "user-emulated": 1, "machine-emulated": 3,
                            "hosted-engine": 1, "unresolved-runtime": 1, "object-only": 2, "unknown": 1}

    controls = {
        "native_x86_64_linux": ("x86_64-linux-raw", "native", "covered"),
        "aarch64_user_emulation": ("aarch64-linux-raw", "user-emulated", "covered"),
        "physical_aarch64_from_emulation": ("aarch64-linux-raw", "native", "unverified"),
        "physical_cortex_from_machine_emulation": ("cortex-m3-freestanding", "native", "unverified"),
        "unresolved_atomic_runtime_as_linked": ("rv64-atomic-no-a", "machine-emulated", "unverified"),
        "aarch64_lse_object_from_codegen": ("aarch64-atomic-lse", "object-only", "covered"),
        "runtime_aarch64_lse_from_object_only": ("aarch64-atomic-lse", "native", "unverified"),
        "windows_from_linux_calling_convention": ("x86_64-windows-native", "native", "unverified"),
    }
    receipts = {}
    for label, (row_id, required, expected) in controls.items():
        row = profiles[row_id]
        found = exact_scope(row, required, row["claim"])
        assert found == expected
        receipts[label] = found
    alternate = exact_scope(profiles["x86_64-linux-raw"], "native", "all POSIX operations")
    assert alternate == "unverified"
    receipts["unrelated_native_operation"] = alternate
    return {"python": platform.python_version(), "matrix_sha256": sha256(path.read_bytes()).hexdigest(),
            "levels": dict(counts), "controls": receipts, "verified_source_ledgers": len(studies)}


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
