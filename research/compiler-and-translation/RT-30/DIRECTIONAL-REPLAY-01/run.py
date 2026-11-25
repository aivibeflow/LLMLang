"""Independently replay and audit forward, reverse and cross-target RT-30 evidence."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
RT30 = HERE.parent
ROOT = HERE.parents[3]
LANGUAGES = ("c", "cpp", "go", "rust")
IR = "llmlang-fixture"
ROUTES = {
    "c_family": "C-FAMILY-ROUNDTRIP-01/roundtrip.py",
    "go": "GO-ROUNDTRIP-01/roundtrip.py",
    "rust": "RUST-WRAPPING-ROUNDTRIP-01/roundtrip.py",
    "matrix": "WRAPPING-TRANSLATION-MATRIX-01/matrix.py",
}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data):
    return sha256(data).hexdigest()


def remove_install_directory(evidence):
    data = deepcopy(evidence)
    if isinstance(data.get("toolchain"), list):
        data["toolchain"] = [
            line for line in data["toolchain"] if not line.startswith("InstalledDir:")
        ]
    elif isinstance(data.get("toolchain"), dict) and "clang" in data["toolchain"]:
        data["toolchain"]["clang"] = [
            line for line in data["toolchain"]["clang"] if not line.startswith("InstalledDir:")
        ]
    return data


def verify_sources(evidence):
    sources = evidence["source_sha256"]
    assert sources, "no source inventory"
    for filename, expected in sources.items():
        source = ROOT / filename
        assert source.resolve().is_relative_to(ROOT) and digest(source.read_bytes()) == expected, filename


def replay(name, flags):
    path = RT30 / ROUTES[name]
    archived = path.parent / "evidence.json"
    archived_bytes = archived.read_bytes()
    baseline = json.loads(archived_bytes)
    verify_sources(baseline)
    result = subprocess.run(
        [sys.executable, "-B", path, *flags], cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "LC_ALL": "C", "TZ": "UTC", "PYTHONHASHSEED": "997"},
        timeout=180,
    )
    live = json.loads(result.stdout)
    verify_sources(live)
    portable = remove_install_directory(live)
    expected = remove_install_directory(baseline)
    differences = sorted(key for key in expected.keys() | portable.keys() if portable.get(key) != expected.get(key))
    assert not differences, (name, differences)
    return portable, {
        "archived_ledger_sha256": digest(archived_bytes),
        "replayed_normalized_ledger_sha256": digest(encode(portable)),
        "source_files_checked": len(live["source_sha256"]),
    }


def audit_matrix(evidence):
    count = 37020
    trace = evidence["required_trace_sha256"]
    grid = evidence["matrix"]
    assert evidence["programs_per_source"] == 12
    assert evidence["observed_fields"] == ["status", "output_slot", "ordered_callbacks"]
    assert set(grid) == {IR, *LANGUAGES}
    assert all(set(row) == {IR, *LANGUAGES} for row in grid.values())
    assert grid[IR][IR] == {"status": "not-a-translation"}
    totals = dict(forward=0, reverse=0, reexport=0, cross_target=0)
    for source, row in grid.items():
        if source != IR:
            assert row[IR] == {"status": "restricted-checked-import", "checked_programs": 12}
            totals["reverse"] += 1
        for target in LANGUAGES:
            receipt = row[target]
            assert receipt == {
                "status": "restricted-differential-pass", "observations": count, "trace_sha256": trace,
            }
            direction = "forward" if source == IR else "reexport" if source == target else "cross_target"
            totals[direction] += 1
    assert totals == {"forward": 4, "reverse": 4, "reexport": 4, "cross_target": 12}
    assert evidence["observed_native_routes"] == 20
    assert evidence["total_native_observations"] == count * 20
    return totals


def negative_matrix_controls(evidence):
    results = {}
    for control in (
        "route deleted", "cross-target receipt digest changed", "re-export marked merely emitted",
        "reverse direction incorrectly counted as native", "reverse import missing one program",
        "direction inventory contains an unsupported route",
    ):
        changed = deepcopy(evidence)
        grid = changed["matrix"]
        if control == "route deleted":
            del grid[IR]["go"]
        elif control == "cross-target receipt digest changed":
            grid["c"]["cpp"]["trace_sha256"] = "f" * 64
        elif control == "re-export marked merely emitted":
            grid["rust"]["rust"]["status"] = "emitted"
        elif control == "reverse direction incorrectly counted as native":
            changed["observed_native_routes"] += 4
        elif control == "reverse import missing one program":
            grid["go"][IR]["checked_programs"] -= 1
        else:
            grid["rust"]["python"] = grid["rust"]["go"]
        try:
            audit_matrix(changed)
        except AssertionError:
            results[control] = "refused"
        else:
            raise AssertionError(control)
    return results


def collect(args, cache):
    common_rust = ["--rustc", args.rustc, "--cargo", args.cargo]
    common_go = ["--go", args.go, "--cache", cache]
    commands = {
        "c_family": ["--clang", args.clang],
        "go": common_go,
        "rust": common_rust,
        "matrix": ["--clang", args.clang, *common_rust, *common_go],
    }
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending = {name: executor.submit(replay, name, flags) for name, flags in commands.items()}
        reports = {name: job.result() for name, job in pending.items()}
    c_family, go, rust, matrix = (reports[name][0] for name in ROUTES)
    count = 37020
    trace = matrix["required_trace_sha256"]
    assert c_family["imported_per_language"] == c_family["reimported_per_direction"] == 12
    assert len(go["approved_programs"]) == go["successful_reimports"] == 12
    assert rust["original_distinct_programs"] == rust["successful_reimports"] == 12
    assert len(c_family["native_results"]) == 8
    assert len(rust["native_profiles"]) == 8
    native = [*c_family["native_results"].values(), *rust["native_profiles"].values()]
    assert all(row["records"] == count and row["trace_sha256"] == trace for row in native)
    assert len(go["native_comparison"]) == 2
    assert all(row["observations"] == count and row["statuses"] == {"ok": count}
               for row in go["native_comparison"].values())
    importer_refusals = {
        **{name: len(rows) for name, rows in c_family["negative_cases"].items()},
        "go": len(go["negative"]), "rust": len(rust["negative"]),
    }
    assert importer_refusals == {"c": 8, "cpp": 9, "go": 10, "rust": 10}
    return {
        "directions": audit_matrix(matrix),
        "scope_controls": negative_matrix_controls(matrix),
        "importer_refusals": importer_refusals,
        "matrix_native_observations": matrix["total_native_observations"],
        "roundtrip_native_observations": (len(native) + len(go["native_comparison"])) * count,
        "relative_install_directory_ignored": "Clang InstalledDir only",
        "replays": {name: ledger for name, (_, ledger) in reports.items()},
        "runner_sha256": digest(Path(__file__).read_bytes()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("clang", "go", "rustc", "cargo"):
        parser.add_argument(f"--{name}", default=name)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt30-directional-replay-") as directory:
        evidence = collect(args, Path(directory) / "go-cache")
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
