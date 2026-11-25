"""Check Cranelift JIT observations and exact generation-qualified receipts."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROLES = ("direct-before", "direct-after", "relay", "provider-before", "provider-after")
MODES = ("none", "speed")


def digest(data):
    return sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def scopes(codes, mode):
    def function(role, index):
        return digest(codes[role][index])
    return {
        "direct-before": ("direct", 1, function("direct-before", 1), function("direct-before", 0), mode),
        "direct-after": ("direct", 2, function("direct-after", 1), function("direct-after", 0), mode),
        "relay-before": ("relay", 1, function("relay", 0), function("provider-before", 0), mode),
        "relay-after": ("relay", 2, function("relay", 0), function("provider-after", 0), mode),
    }


def verify_scope_controls(receipts):
    def admits(request, evidence, generations):
        return request == evidence and request[1] in generations

    old_direct = receipts["direct-before"]
    new_direct = receipts["direct-after"]
    old_relay = receipts["relay-before"]
    new_relay = receipts["relay-after"]
    assert [old_direct[2], old_relay[2]] == [new_direct[2], new_relay[2]]
    assert old_direct[3] != new_direct[3] and old_relay[3] != new_relay[3]
    cases = {
        "exact-old-while-retained": (old_direct, old_direct, {1, 2}, True),
        "exact-new-direct": (new_direct, new_direct, {2}, True),
        "exact-new-relay": (new_relay, new_relay, {2}, True),
        "stale-direct": (new_direct, old_direct, {1, 2}, False),
        "stale-relay": (new_relay, old_relay, {1, 2}, False),
        "released-generation": (old_direct, old_direct, {2}, False),
        "current-generation-with-old-provider": (new_relay[:3] + (old_relay[3], new_relay[4]), new_relay, {2}, False),
        "different-optimization-profile": (new_relay[:4] + ("other",), new_relay, {2}, False),
    }
    result = {}
    for name, (subject, evidence, live_generations, expected) in cases.items():
        actual = admits(subject, evidence, live_generations)
        assert actual == expected, name
        result[name] = "admitted" if actual else "refused"
    return result


def collect(probe):
    result = subprocess.run([probe], text=True, capture_output=True, check=True, timeout=20)
    assert not result.stderr, result.stderr
    results = {mode: {"codes": {}, "values": [], "retained": None} for mode in MODES}
    for line in result.stdout.splitlines():
        event, mode, *fields = line.split()
        target = results[mode]
        if event == "code":
            name, index, machine = fields
            chunks = target["codes"].setdefault(name, [])
            assert int(index) == len(chunks)
            chunks.append(bytes.fromhex(machine))
        elif event == "values":
            target["values"].append(tuple(map(int, fields)))
        else:
            assert event == "retained" and target["retained"] is None
            target["retained"] = tuple(map(int, fields))

    profiles = {}
    for mode, row in results.items():
        assert set(row["codes"]) == set(ROLES)
        assert [len(row["codes"][role]) for role in ROLES] == [2, 2, 1, 1, 1]
        assert [values[0] for values in row["values"]] == [
            *range(256), 0x7fff_ffff, 0x8000_0000, 0xffff_ffef, 0xffff_ffff,
        ]
        assert row["retained"] == (33, 33)
        stale = 0
        for value, old_direct, new_direct, old_relay, new_relay in row["values"]:
            expected_old = (value + 14) % 2**32
            expected_new = (value + 30) % 2**32
            assert old_direct == old_relay == expected_old
            assert new_direct == new_relay == expected_new
            stale += old_direct != expected_new
        assert stale == 260
        receipts = scopes(row["codes"], mode)
        profiles[mode] = {
            "native_comparisons": len(row["values"]) * 4,
            "old_results_incorrect_for_new_request": stale * 2,
            "native_trace_sha256": digest(canonical(row["values"])),
            "pre_relocation_code": {
                role: [{"bytes": len(part), "sha256": digest(part)} for part in chunks]
                for role, chunks in row["codes"].items()
            },
            "receipts": receipts,
            "admission_controls": verify_scope_controls(receipts),
            "compiled_functions_on_edit": {"direct": 2, "relay": 1},
            "duplicate_definition": "refused",
            "remaining_new_entry_calls_after_release": list(row["retained"]),
        }
    return {
        "cranelift": "0.116.1",
        "source_sha256": {
            name: digest((HERE / name).read_bytes())
            for name in ("Cargo.toml", "Cargo.lock", "src/main.rs", "run.py")
        },
        "profiles": profiles,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(args.probe), indent=2, sort_keys=True) + "\n")
