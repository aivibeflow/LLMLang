"""Replay native FFI observations and audit conditional proof receipt boundaries."""

import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "FFI-SIX-LANGUAGE-EXPORT-01"


def digest(blob):
    return sha256(blob).hexdigest()


def filehash(path):
    return digest(path.read_bytes())


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def process(args, cwd=None):
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=True,
        env={**os.environ, "LC_ALL": "C", "TZ": "UTC"}, timeout=150,
    ).stdout


@dataclass(frozen=True)
class Scope:
    public_contract: str
    provider: str
    abi: str
    target: str
    environment: str
    observation: str
    caller_profile: str


@dataclass(frozen=True)
class Witness:
    scope: Scope
    outcome: str
    native_observations: str
    source_proof: str

    @property
    def identity(self):
        return digest(canonical(asdict(self)))


def inspect(scope, witness, verified, has_storage, proof):
    if not has_storage:
        return "caller-premise-missing"
    if witness is None:
        return "unknown-no-observation"
    if witness.identity not in verified:
        return "unknown-unverified-observation"
    if witness.scope != scope:
        return "unknown-stale-scope"
    if witness.outcome == "contract-refused":
        return "observed-contradiction"
    if witness.outcome != "checked":
        return "unknown-incomplete-observation"
    if witness.source_proof != proof:
        return "unknown-proof-scope"
    return "conditional-on-provider-contract"


def trace_controls(evidence, environment, theorem):
    builds = evidence["builds"]
    observations = evidence["routes"]
    symbol = "checked_add/status-and-initialized-output"
    base = Scope(
        evidence["source_contract_sha256"], builds["base"]["shared_sha256"],
        builds["base"]["abi_sha256"], evidence["profile"], environment, symbol, "c-shared",
    )
    revised = replace(base, provider=builds["compatible_revision"]["shared_sha256"])
    incompatible = replace(base, provider=builds["different_contract"]["shared_sha256"])
    abi_mismatch = replace(base, provider=builds["different_abi"]["shared_sha256"],
                           abi=builds["different_abi"]["abi_sha256"])
    expected_witnesses = {}
    for version, scope in (
        ("base", base), ("compatible_revision", revised), ("different_contract", incompatible),
    ):
        outcome = observations[f"c-shared/{version}"]
        expected_witnesses[version] = Witness(scope, outcome["admission"], outcome["trace_sha256"], theorem)
    good, compatible, failed = (expected_witnesses[version] for version in
                                ("base", "compatible_revision", "different_contract"))
    wrong_proof = replace(good, source_proof="different proof statement")
    incomplete = replace(good, outcome="attempted")
    verified = {x.identity for x in (good, compatible, failed, wrong_proof, incomplete)}
    scenarios = (
        ("exact original", base, good, True, "conditional-on-provider-contract"),
        ("exact compatible replacement", revised, compatible, True, "conditional-on-provider-contract"),
        ("stale original after replacement", revised, good, True, "unknown-stale-scope"),
        ("known incompatible provider", incompatible, failed, True, "observed-contradiction"),
        ("different output pointee ABI", abi_mismatch, good, True, "unknown-stale-scope"),
        ("different public contract", replace(base, public_contract="other"), good, True, "unknown-stale-scope"),
        ("different target", replace(base, target="other"), good, True, "unknown-stale-scope"),
        ("different environment", replace(base, environment="other"), good, True, "unknown-stale-scope"),
        ("different observation", replace(base, observation="status-only"), good, True, "unknown-stale-scope"),
        ("different caller", replace(base, caller_profile="rust"), good, True, "unknown-stale-scope"),
        ("unknown provider", incompatible, None, True, "unknown-no-observation"),
        ("independent proof has other subject", base, wrong_proof, True, "unknown-proof-scope"),
        ("unverified observation", base, replace(good, native_observations="changed"), True,
         "unknown-unverified-observation"),
        ("incomplete observation", base, incomplete, True, "unknown-incomplete-observation"),
        ("storage premise missing", base, good, False, "caller-premise-missing"),
    )
    results = {}
    for name, scope, witness, storage, expected in scenarios:
        actual = inspect(scope, witness, verified, storage, theorem)
        assert actual == expected, name
        results[name] = actual
    return {
        "control_outcomes": results,
        "witness_scopes": {name: asdict(witness) for name, witness in expected_witnesses.items()},
    }


def collect(args, work):
    fixture = HERE / "Caller.lean"
    proof = process([args.lean, fixture]).splitlines()
    assert len(proof) == 4 and all("does not depend on any axioms" in row for row in proof)
    theorem = digest(canonical([filehash(fixture), proof]))
    replay = work / "native.json"
    process([
        sys.executable, "-B", NATIVE / "run.py", "--go", args.go, "--go-cache", args.go_cache,
        "--output", replay,
    ])
    original = NATIVE / "evidence.json"
    assert replay.read_bytes() == original.read_bytes()
    native = json.loads(replay.read_text(encoding="utf-8"))
    host = {
        "libc": filehash(Path("/usr/lib/x86_64-linux-gnu/libc.so.6")),
        "loader": filehash(Path("/lib64/ld-linux-x86-64.so.2")),
        "kernel": os.uname().release,
    }
    return {
        "lean_audit": proof,
        "native_replay_sha256": filehash(replay),
        "native_compared": sum(row["observations"] for row in native["routes"].values()),
        "source_sha256": {path.name: filehash(path) for path in (fixture, Path(__file__))},
        "environment": host,
        **trace_controls(native, digest(canonical(host)), theorem),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--go", default="go")
    parser.add_argument("--go-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-proof-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
