#!/usr/bin/env python3
"""Check the signed byte codec and exact projections from the pinned native archive."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[2] / "semantic-representation" / "RT-05" / "CROSS-RUNTIME-I64-01"
NATIVE_DIGEST = "27960e4b6ca7dcb498ebef299b8d390fafa0dd048bad907200c38ce2fb4c2f29"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
ALLOWED_AXIOMS = {"propext", "Quot.sound", "Classical.choice"}


def digest(data):
    return sha256(data).hexdigest()


def lean_call(lean, directory, *arguments):
    return subprocess.run([lean, "-DwarningAsError=true", *arguments], cwd=directory,
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, "LEAN_PATH": str(directory)})


def audit(result, prefix):
    assert result.returncode == 0, result.stdout + result.stderr
    theorems = {}
    for line in result.stdout.splitlines():
        row = re.fullmatch(rf"'{re.escape(prefix)}(\w+)' depends on axioms: \[(.*)\]", line)
        if row:
            name, entries = row.groups()
            axioms = entries.split(", ")
        else:
            row = re.fullmatch(rf"'{re.escape(prefix)}(\w+)' does not depend on any axioms", line)
            assert row, line
            name, axioms = row[1], []
        assert name not in theorems and set(axioms) <= ALLOWED_AXIOMS, line
        theorems[name] = axioms
    return theorems


def replay_code(native):
    data = (native / "evidence.json").read_bytes()
    assert digest(data) == NATIVE_DIGEST
    evidence = json.loads(data)
    for name, expected in evidence["source_sha256"].items():
        assert digest((native / name).read_bytes()) == expected, name
    rows = [row for row in evidence["observations"] if row["policy"] == "hex"]
    assert len({row["input"] for row in rows}) == len(rows) == evidence["distinct_values"] == 181
    chunks = ["import Codec", "open SignedCodec"]
    for index, row in enumerate(rows):
        raw = json.loads(row["wire"])
        assert raw["codec"] == "hex" and re.fullmatch("[0-9a-f]{16}", raw["value"]), raw
        assert digest(row["wire"].encode()) == row["wire_sha256"]
        octets = bytes.fromhex(raw["value"])
        decimal = row["input"]
        assert str(int(decimal)) == decimal
        assert str(int.from_bytes(octets, "big", signed=True)) == decimal
        identity = digest(b"rt05-i64/1\0" + octets)
        assert row["node"] == {"status": "accepted", "decimal": decimal, "semantic": identity}
        assert row["expected_identity"] == identity
        chunks.append(f"theorem archiveCase{index} : replay ({decimal}) = "
                      f"some ({list(octets)}, ({decimal})) := by rfl")
        chunks.append(f"#print axioms archiveCase{index}")
    return "\n".join(chunks) + "\n", evidence


def run(lean, native, directory):
    revision = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in revision
    proof = HERE / "Codec.lean"
    kernel = lean_call(lean, directory, f"--root={HERE}", "-o", str(directory / "Codec.olean"), str(proof))
    axioms = audit(kernel, "SignedCodec.")
    assert len(axioms) == 14
    emitted, native_evidence = replay_code(native)
    replay = directory / "Replay.lean"
    replay.write_text(emitted, encoding="utf-8")
    equalities = audit(lean_call(lean, directory, str(replay)), "archiveCase")
    assert set(equalities) == {str(index) for index in range(native_evidence["distinct_values"])}
    negative = directory / "Incorrect.lean"
    negative.write_text("""import Codec
open SignedCodec
example : encodeChecked upperExclusive = some (encode lower) := by rfl
""", encoding="utf-8")
    refused = lean_call(lean, directory, str(negative))
    assert refused.returncode == 1 and "not definitionally equal" in (refused.stdout + refused.stderr).lower()
    return {
        "schema": "llmlang-rt32-signed-i64-byte-kernel/1",
        "python": platform.python_version(), "lean": revision,
        "lean_source_sha256": digest(proof.read_bytes()), "runner_source_sha256": digest(Path(__file__).read_bytes()),
        "generated_replay_sha256": digest(emitted.encode()), "native_archive_sha256": NATIVE_DIGEST,
        "native_python": native_evidence["python"], "native_node": native_evidence["node"],
        "native_v8": native_evidence["v8"], "model_theorem_axioms": axioms, "archive_equalities": equalities,
        "incorrect_wraparound_proof": "rejected",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--native-dir", type=Path, default=NATIVE)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rt32-i64-") as scratch:
        outcome = run(args.lean, args.native_dir.resolve(), Path(scratch))
    print(json.dumps(outcome, indent=2))
