#!/usr/bin/env python3
"""Rebuild the exact source-wire gate and replay CPC scope rebinding controls."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tarfile import open as tar_open
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "d0be069bc08e456dd3f173537245e42612ec7c6e"
PROTOTYPE = Path("research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding")
LOGOS_REV = "cf18742973861b3718d04c5f25775448098ff474"
UNCHANGED = {"base", "sequence_of_two_skips", "renamed_factor", "unused_hidden_declaration"}
CHANGED = {"unused_visible_state", "observed_state", "different_constant_return", "dependent_return",
           "new_factor_identity"}
UNAVAILABLE = {"factor_role_changed", "factor_uninitialized", "ambiguous_duplicate_name"}
REBOUND = {"unused_visible_state", "different_constant_return", "new_factor_identity"}


def execute(args, cwd, *, env=None):
    return subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True,
                          timeout=90).stdout


def digest(data):
    return sha256(data).hexdigest()


def rebuild(root, env):
    compiled = {}

    def build(module):
        path = root / f"{module}.lean"
        if module in compiled or not path.is_file():
            return
        source = path.read_bytes()
        imports = re.findall(r"^import ([\w.]+)$", source.decode("utf-8"), flags=re.MULTILINE)
        for dependency in imports:
            build(dependency)
        execute(["lean", "-DwarningAsError=true", "-o", f"{module}.olean", path.name], root, env=env)
        compiled[module] = digest(source)

    build("SourceWireRefutation")
    return compiled


def results(transcript):
    lines = transcript.decode("utf-8").splitlines()
    axioms = [line for line in lines if line.startswith("'")]
    if len(axioms) != 2 or any("[propext, Classical.choice, Quot.sound]" not in line for line in axioms):
        raise AssertionError(axioms)
    rows = [json.loads(line) for line in lines if line.startswith("{")]
    indexed = {row["name"]: row for row in rows}
    if len(rows) != len(indexed) or set(indexed) != UNCHANGED | CHANGED | UNAVAILABLE:
        raise AssertionError(indexed.keys())
    base = indexed["base"]["fresh_wire"]
    base_fields = json.loads(base)
    output = []
    for row in rows:
        label, wire = row["name"], row["fresh_wire"]
        if label in UNCHANGED:
            assert wire == base and row["old_wire_check"] == row["fresh_wire_check"] == "admitted", row
        if label in CHANGED:
            assert wire and wire != base and row["old_wire_check"] == "source-or-wire", row
            assert row["fresh_wire_check"] == "assumptions", row
        if label in UNAVAILABLE:
            assert wire is None and row["old_wire_check"] == "source-or-wire", row
            assert row["fresh_wire_check"].startswith("source-unavailable:"), row
        assert row["rebound_proof_check"] == ("admitted" if label in REBOUND else None), row
        wire_fields = json.loads(wire) if wire is not None else {}
        changed_fields = [key for key, value in wire_fields.items() if value != base_fields.get(key)]
        if label == "unused_visible_state" and changed_fields != ["declarations"]:
            raise AssertionError((label, changed_fields))
        output.append({
            "name": label, "changed_wire_fields": changed_fields if wire is not None else None, "fresh_wire_sha256": None if wire is None else digest(wire.encode("utf-8")),
            "same_wire_as_base": wire == base,
            "old_wire_check": row["old_wire_check"], "fresh_wire_check": row["fresh_wire_check"],
            "rebound_proof_check": row["rebound_proof_check"],
        })
    return axioms, output


def run(logos):
    if execute(["git", "rev-parse", "HEAD"], logos).decode().strip() != LOGOS_REV:
        raise AssertionError("Unexpected Logos revision")
    if execute(["git", "status", "--porcelain", "--untracked-files=no"], logos):
        raise AssertionError("Logos checkout has changed tracked sources")
    library = logos / ".lake/build/lib/lean"
    runtime = library / "Cpc/Api.olean"
    if not runtime.is_file():
        raise RuntimeError("Build the pinned Logos Cpc library first")
    archive_bytes = execute(["git", "archive", BASELINE, PROTOTYPE], ROOT)
    with TemporaryDirectory(prefix="llmlang-source-proof-") as temp:
        with tar_open(fileobj=BytesIO(archive_bytes)) as archive:
            archive.extractall(temp, filter="data")
        root = Path(temp) / PROTOTYPE
        env = {**os.environ, "LEAN_PATH": f".:{library}", "LC_ALL": "C"}
        modules = rebuild(root, env)
        for name in ("Rebind.lean", "proof.cpc"):
            shutil.copyfile(HERE / name, root / name)
        transcript = execute(["lean", "-DwarningAsError=true", "--run", "Rebind.lean"], root, env=env)
    axioms, rows = results(transcript)
    return {
        "schema": "llmlang-source-proof-rebinding/1", "baseline": BASELINE,
        "python": platform.python_version(), "lean": execute(["lean", "--version"], ROOT).decode().strip(),
        "logos_revision": LOGOS_REV, "logos_api_olean_sha256": digest(runtime.read_bytes()),
        "sources_sha256": {name: digest((HERE / name).read_bytes())
                           for name in ("run.py", "Rebind.lean", "proof.cpc")},
        "rebuilt_modules_sha256": modules,
        "full_transcript_sha256": digest(transcript), "axioms": axioms,
        "same_wire_including_base": len(UNCHANGED), "changed_wire": len(CHANGED),
        "source_unavailable": len(UNAVAILABLE), "rebuilt_certificate_admissions": len(REBOUND),
        "controls": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logos", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().logos.resolve()), indent=2))
