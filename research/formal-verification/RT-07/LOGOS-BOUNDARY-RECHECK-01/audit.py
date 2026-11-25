"""Replay runtime verdict conditions and compare exact archived proof dependencies."""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from collections import Counter
from pathlib import Path

BASELINE = "d816c26380dae97c9ade3252eb7438adacb1b4ae"
LOGOS_REVISION = "cf18742973861b3718d04c5f25775448098ff474"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
BINDING = Path("research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding")
VERDICT = Path("research/formal-verification/RT-07/LOGOS-VERDICT-PROOF-01")
CORE = {"propext", "Classical.choice", "Quot.sound"}
REPORT = re.compile(r"'([^']+)' depends on axioms: \[([^\]]+)\]")
MODULE = re.compile(r"^_private\.(.+?)\.\d+\.")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def set_digest(names):
    return digest(("\n".join(sorted(names)) + "\n").encode())


def pinned(path):
    payload = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"])
    if payload != path.read_bytes():
        raise ValueError(f"{path} differs from {BASELINE}")
    return payload


def parse_reports(raw):
    rows = REPORT.findall(raw.decode())
    result = {name: [item.strip() for item in axioms.split(",")] for name, axioms in rows}
    if not rows or len(result) != len(rows):
        raise ValueError("empty or duplicate Lean axiom report")
    return result


def compare_archived_sets():
    archive = json.loads(pinned(VERDICT / "evidence.json"))
    build = json.loads(pinned(VERDICT / "build-provenance.json"))
    standard = set(archive["standard_axioms"])
    native = set(archive["verdict_native_axioms"])
    witness = set(archive["witness_native_axioms"])
    assert standard == CORE and len(native) == 2118 and len(witness) == 1 and witness < native
    assert all("._native.native_decide." in name and MODULE.match(name) for name in native)
    for theorem, row in archive["theorems"].items():
        declared = witness if theorem == "Smtm.model_wf_nonvacuous" else native
        assert len(declared) == row["native_decide_axioms"]
        assert len(declared | standard) == row["total_axioms"]
        assert set_digest(declared | standard) == row["set_sha256"]

    common = next(iter(witness))
    renamed = native - {common} | {common.replace(".Common.", ".ChangedCommon.", 1)}
    assert len(renamed) == len(native) and renamed != native
    assert {name.rsplit(".", 1)[-1] for name in renamed} == {name.rsplit(".", 1)[-1] for name in native}
    assert set_digest(renamed | standard) != set_digest(native | standard)
    modules = Counter(MODULE.match(name).group(1) for name in native)
    return {
        "upstream_build_provenance_sha256": digest(pinned(VERDICT / "build-provenance.json")),
        "archive_sha256": digest(pinned(VERDICT / "evidence.json")),
        "build_record_fields": sorted(build),
        "full_proof_native_axioms": len(native),
        "native_axioms_within_rule_modules": sum(
            count for module, count in modules.items() if module.startswith("Cpc.Proofs.Rules.")
        ),
        "distinct_final_components": len({name.rsplit(".", 1)[-1] for name in native}),
        "defining_modules": dict(sorted(modules.items(), key=lambda item: (-item[1], item[0]))),
        "theorem_sets": archive["theorems"],
        "base_witness_native_axiom": common,
        "changed_name_control": {
            "same_full_count": True, "same_final_components": True, "same_full_set_digest": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--logos-checkout", required=True, type=Path)
    args = parser.parse_args()
    lean = args.lean.resolve(strict=True)
    logos = args.logos_checkout.resolve(strict=True)
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=logos, text=True).strip() == LOGOS_REVISION
    assert not subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=logos,
    )
    library = logos / ".lake/build/lib/lean"
    lean_version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in lean_version
    runtime = BINDING / "LogosVerdictConditions.lean"
    runtime_source = pinned(runtime)
    env = os.environ | {"LC_ALL": "C", "LEAN_PATH": str(library)}
    archived_runtime = pinned(BINDING / "evidence/logos-verdict/runtime-axioms.txt")
    observed = subprocess.check_output(
        [lean, "-DwarningAsError=true", runtime], env=env, timeout=30,
    )
    assert observed == archived_runtime
    assert all(set(axioms) == CORE for axioms in parse_reports(observed).values())
    other_profiles = {}
    for profile in ("logos-concrete-pair", "logos-model-extension", "logos-kernel-model-witness",
                    "logos-source-refutation"):
        report = pinned(BINDING / "evidence" / profile / "axioms.txt")
        rows = parse_reports(report)
        assert all(CORE <= set(values) for values in rows.values())
        other_profiles[profile] = {"transcript_sha256": digest(report), "theorems": rows}
    print(json.dumps({
        "baseline": BASELINE, "logos_revision": LOGOS_REVISION,
        "python": platform.python_version(), "runtime_lean": lean_version,
        "runtime_api_olean_sha256": digest((library / "Cpc/Api.olean").read_bytes()),
        "runtime_source_sha256": digest(runtime_source),
        "runtime_axioms_sha256": digest(observed), "runtime_theorems": parse_reports(observed),
        "archived_source_profiles": other_profiles,
        "archived_verdict": compare_archived_sets(),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
