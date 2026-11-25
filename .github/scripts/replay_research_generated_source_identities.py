#!/usr/bin/env python3
"""Regenerate the 25 generated-source digests in the RT-00 identity audit."""

import argparse
from hashlib import sha256
import importlib.util
from itertools import permutations, product
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory

EXTREMA = "research/formal-verification/RT-32/F64-EXTREMA-GUARD-01"
ROUNDING = "research/compiler-and-translation/RT-13/LLVM-DYNAMIC-ROUNDING-01"
SPG = "research/semantic-representation/RT-05"
BASELINE = "d2e32df3ff25ef28dc66750b3e14e777d7cd7d35"


def load_runner(fixture):
    spec = importlib.util.spec_from_file_location(fixture.name, fixture / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_ledger(root, fixture):
    return json.loads((root / fixture / "evidence.json").read_bytes())


def generate_sources(root, scratch):
    fixture = root / EXTREMA
    extrema = load_runner(fixture)
    native_bytes = (extrema.NATIVE / "evidence.json").read_bytes()
    if sha256(native_bytes).hexdigest() != extrema.NATIVE_DIGEST:
        raise ValueError("The native extrema archive differs from the runner's pinned input")
    rows = json.loads(native_bytes)["observations"]
    yield EXTREMA, "archive_replay_sources_sha256", {
        f"Replay{first}.lean": extrema.replay_code(rows, first, min(first + 64, len(rows))).encode("utf-8")
        for first in range(0, len(rows), 64)
    }

    rounding = load_runner(root / ROUNDING)
    ir, header = rounding.generate()
    yield ROUNDING, "source_sha256", {"generated_ir": ir.encode("utf-8"), "generated_header": header.encode("utf-8")}

    fixture_path = f"{SPG}/CROSS-PROFILE-CLEANUP-01"
    cleanup = load_runner(root / fixture_path)
    cases = [(index, decl, init, mode) for index, (decl, init, mode)
             in enumerate(product(cleanup.ORDERS, cleanup.ORDERS, cleanup.MODES))]
    yield fixture_path, "source_sha256", {
        "rust": cleanup.rust_source(cases).encode("utf-8"),
        "cpp": cleanup.cpp_source(cases).encode("utf-8"),
    }

    fixture_path = f"{SPG}/NAMED-RECORD-01"
    records = load_runner(root / fixture_path)
    universe = []
    for index, (order, kinds) in enumerate(product(permutations(records.FIELDS), product(records.OPERANDS, repeat=3))):
        choices = dict(zip(records.FIELDS, kinds))
        fields = [(name, choices[name], records.FIELDS.index(name), records.VALUES[name]) for name in order]
        universe.append((index, order, choices, fields))
    yield fixture_path, "source_sha256", {
        key: path.read_bytes() for key, path in records.emit(universe, scratch).items()
    }

    fixture_path = f"{SPG}/UNICODE-BINDING-01"
    unicode_binding = load_runner(root / fixture_path)
    yield fixture_path, "source_sha256", {
        key: path.read_bytes() for key, path in unicode_binding.sources(scratch).items()
    }


def replay(root, audit_register):
    expected_rows = {
        (entry["path"], observation["field"], observation["label"]): observation["expected_sha256"]
        for entry in audit_register["ledgers"]
        for observation in entry["identity_observations"]
        if observation["outcome"] == "generated-source-requires-replay"
    }
    dispositions = []
    with TemporaryDirectory(prefix="llmlang-source-replay-") as tmp:
        for fixture, field, artifacts in generate_sources(root, Path(tmp)):
            ledger_path = fixture + "/evidence.json"
            ledger = read_ledger(root, fixture)
            for label, artifact in sorted(artifacts.items()):
                expected = expected_rows.pop((ledger_path, field, label))
                if ledger[field][label] != expected:
                    raise ValueError(f"Audit register and fixture ledger disagree for {ledger_path}:{label}")
                actual = sha256(artifact).hexdigest()
                dispositions.append({
                    "ledger": ledger_path, "field": field, "label": label, "bytes": len(artifact),
                    "expected_sha256": expected, "replayed_sha256": actual, "matched": expected == actual,
                })
    if expected_rows:
        raise ValueError(f"Missing generated inputs: {sorted(expected_rows)}")
    return {
        "schema": "rt00-generated-source-identity-replay-v1",
        "baseline": BASELINE,
        "python": platform.python_version(),
        "count": len(dispositions),
        "matched": sum(row["matched"] for row in dispositions),
        "observations": dispositions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--audit-register", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    register = json.loads(args.audit_register.read_bytes())
    if register["baseline"] != BASELINE:
        parser.error("The audit register does not identify the required source tree")
    result = replay(args.archive_dir.resolve(), register)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if result["matched"] != result["count"]:
        raise SystemExit("Generated source digest mismatch")
