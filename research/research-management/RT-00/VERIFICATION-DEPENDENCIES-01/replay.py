#!/usr/bin/env python3
"""Replay the pinned experimental basis for five verification dependency edges."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


REVISION = "b23901a91bc4eade228cab50be0276a00010961b"
RT = "research/formal-verification/RT-33"
REGISTER = "research/research-management/RESEARCH-DEPENDENCY-MAP.md"
EDGES = ("DEP-191", "DEP-193", "DEP-194", "DEP-196", "DEP-199")


def command(argv, root, env):
    result = subprocess.run(argv, cwd=root, env=env, capture_output=True, timeout=140)
    assert result.returncode == 0, (argv, result.stdout.decode(errors="replace"),
                                     result.stderr.decode(errors="replace"))
    return result.stdout


def prepare(repo, archive, env):
    paths = [RT, REGISTER, "research/formal-verification/RT-32/LEAN-ARTIFACT-REPLAY-01/Defs.lean",
             "research/packages-and-ecosystem/PROTOTYPES/PACKAGE-IDENTITY-01",
             "research/toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01"]
    payload = command(["git", "archive", REVISION, *paths], repo, env)
    with tarfile.open(fileobj=BytesIO(payload), mode="r:") as source:
        source.extractall(archive, filter="data")


def run_case(repo, archive, env, folder, expected, options):
    trial = archive / RT / folder
    output = archive / "replay.json"
    command([sys.executable, "-B", trial / "run.py", *options, output], archive, env)
    data = output.read_bytes()
    output.unlink()
    pinned = (trial / expected).read_bytes()
    assert data == pinned, (folder, sha256(data).hexdigest(), sha256(pinned).hexdigest())
    blobs = {name: command(["git", "rev-parse", f"{REVISION}:{RT}/{folder}/{name}"], repo, env)
             .decode().strip() for name in ("run.py", expected)}
    return json.loads(data), {"pinned_blobs": blobs, "verified_sha256": sha256(data).hexdigest()}


def facts(data):
    temporal, smt, lean, why, keys = [data[key] for key in ("temporal", "smt", "lean", "why3-boogie", "keys")]
    state = temporal["observations"]
    assert state["apalache-cli"]["shallow"]["disposition"] == "checked"
    assert state["apalache-grpc"]["violation"]["states"] == [0, 1, 2, 3]
    assert state["tlc-cli"]["fair"]["disposition"] == "checked"
    assert state["tlc-java"]["unfair"]["disposition"] == "temporal-violation"
    assert temporal["grpc_controls"]["deadline_1ms"] == "DEADLINE_EXCEEDED"
    assert why["frontend_rows"]["missing"]["boogie"]["exit"] == 0
    assert why["frontend_rows"]["missing"]["boogie"]["disposition"] == "missing-target"
    assert why["independent_fragment"]["valid"]["native_certificate_carcara"] == "holey"
    assert why["independent_fragment"]["valid"]["carcara"] == "valid"
    assert smt["resource_and_type"]["raw-z3-coerces-boolean-to-int"] == 1
    assert smt["resource_and_type"]["raw-cvc5-rejects-mixed-sorts"] == "protocol-failure"
    assert smt["cancellation"]["z3-api"] == "native-context-unknown-after-interrupt"
    assert all(smt["certificate_checks"][route]["status"] == "checked" for route in ("cvc5-api", "cvc5-cli"))
    assert lean["controls"]["expression-echo-type-hint"] == "returned-other-type-explicit-comparison-refused"
    assert lean["controls"]["changed-import-restoration"] == "refused-before-load"
    assert lean["controls"]["old-term-under-new-import"] == "refused-all-routes"
    assert keys["signed_controls"]["signed-rehashed-artifact"] == "independent-check-unavailable"
    assert sum(row["matrix"] for row in keys["keys_by_property"].values()) == 65536
    assert all(row["generic_cache_shape_accepts_missing_declared_role"]
               for row in keys["keys_by_property"].values())
    result = {
        "temporal_observations": sum(len(value) for value in state.values()),
        "why3_boogie_observations": sum(len(value) for value in why["frontend_rows"].values()),
        "lean_claims": len(lean["valid_claims"]),
        "lean_controls": len(lean["controls"]),
        "solver_query_count": sum(len(row["verdicts"]) for row in smt["queries"].values()),
        "admission_identity_combinations": sum(row["matrix"] for row in keys["keys_by_property"].values()),
        "signed_admission_controls": len(keys["signed_controls"]),
    }
    assert list(result.values()) == [18, 14, 6, 17, 56, 65536, 12], result
    return result


def main():
    parser = argparse.ArgumentParser()
    flags = ("tlc", "apalache", "why3-bundle", "dotnet", "boogie-dll", "z3", "cvc5", "carcara",
             "lean", "pantograph-repl", "pantograph-library", "out")
    for flag in flags:
        parser.add_argument(f"--{flag}", type=lambda name: Path(name).resolve(), required=True)
    args = parser.parse_args()
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"LC_ALL": "C", "TZ": "UTC", "WHY3_BUNDLE": str(args.why3_bundle), "PYTHONHASHSEED": "1"})
    repo = Path(command(["git", "rev-parse", "--show-toplevel"], Path.cwd(), env).decode().strip())
    git_dir = command(["git", "rev-parse", "--absolute-git-dir"], repo, env).decode().strip()
    tools = ["--z3", args.z3, "--cvc5", args.cvc5, "--carcara", args.carcara]
    with tempfile.TemporaryDirectory(prefix="rt00-verification-edges-") as scratch:
        archive = Path(scratch)
        prepare(repo, archive, env)
        tasks = {
            "temporal": ("TEMPORAL-ADAPTER-01", "observations.json",
                         ("--tlc", args.tlc, "--apalache", args.apalache, "--out")),
            "smt": ("SMT-ADAPTER-COMPARISON-01", "evidence.json", (*tools, "--output")),
            "lean": ("PANTOGRAPH-ADAPTER-01", "evidence.json",
                     ("--lean", args.lean, "--repl", args.pantograph_repl,
                      "--library", args.pantograph_library, "--output")),
            "why3-boogie": ("WHY3-BOOGIE-ADAPTER-01", "observations.json",
                            (*tools, "--why3", archive / RT / "WHY3-BOOGIE-ADAPTER-01/why3-debian",
                             "--dotnet", args.dotnet, "--boogie-dll", args.boogie_dll, "--out")),
            "keys": ("TYPED-PROOF-KEYS-01", "evidence.json", ()),
        }
        proofs, inventory = {}, {}
        for label, (folder, expected, flags) in tasks.items():
            current = {**env, "GIT_DIR": git_dir, "GIT_WORK_TREE": str(archive)} if label in {"lean", "keys"} else env
            proofs[label], inventory[label] = run_case(repo, archive, current, folder, expected, flags)
        register = (archive / REGISTER).read_text().splitlines()
        original = {edge: [line for line in register if line.startswith(f"| {edge} |")] for edge in EDGES}
        assert all(len(rows) == 1 for rows in original.values())
        report = {"baseline": REVISION, "baseline_rows": {edge: rows[0] for edge, rows in original.items()},
                  "replayed_ledgers": inventory, "claims": facts(proofs)}
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
