"""Check the archived evidence for executable end-to-end research examples."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "language-design/RT-01/TYPED-CLI-01": "0daaaa03372da335608eae60222f5ff4e1ede98264a2b5f4cdc67c97fc96d9b9",
    "toolchain-and-collaboration/RT-19/TOOLCHAIN-ROUNDTRIP-01": "457cf793e805349312c6eefea7e8781c5609780285877bf981e31bfbf6787c58",
}


def read(name):
    raw = (HERE.parents[2] / name / "evidence.json").read_bytes()
    assert sha256(raw).hexdigest() == PINS[name]
    return json.loads(raw)


def verify():
    cli, toolchain = [read(name) for name in PINS]
    assert cli["case_count"] == 34
    assert set(cli["entry_artifacts"]) == {"calculator", "echo", "hello"}
    assert len(cli["route_counts"]) == 5 and set(cli["route_counts"].values()) == {34}
    assert cli["unsupported_entry_effect"] == "refused"
    assert toolchain["successful_roundtrips"] == 864
    assert sum(row["replays"] for row in toolchain["traces"]) == 864
    assert set(toolchain["controls"]) == {"semantic_failure", "malformed_domain_value",
        "direct_accept_control", "stale_validation", "external_edit", "tampered_entity_import"}
    return {"source_ledgers": PINS, "cli_entries": sorted(cli["entry_artifacts"]),
            "cli_observations": sum(cli["route_counts"].values()),
            "cli_native_and_interpreter_case_count": cli["case_count"],
            "toolchain_replays": toolchain["successful_roundtrips"],
            "toolchain_control_names": sorted(toolchain["controls"]),
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, indent=2))
