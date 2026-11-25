#!/usr/bin/env python3
"""Build and check a per-claim trust crosswalk from exact archived evidence."""

import copy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as tar_open
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "7efdcd1dc4dc3b25ef0c257d4f346530e168a509"
RT = Path("research/formal-verification/RT-07")
CONDITIONAL_SOURCE = Path("research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/upstream-model/LogosSourceRefutation.lean")
CONDITIONAL = "LLMLang.LogosScalarDenotation.checkedRefutation_noDependence"
PINNED = "LLMLang.LogosScalarDenotation.pinnedVerdict_noDependence"
ENV = {**os.environ, "LC_ALL": "C"}


def execute(args, cwd=ROOT):
    return subprocess.run(args, cwd=cwd, env=ENV, check=True, capture_output=True,
                          timeout=60).stdout


def digest(raw):
    return sha256(raw).hexdigest()


def set_digest(names):
    return digest(("\n".join(sorted(set(names))) + "\n").encode("utf-8"))


def archived(path):
    return execute(["git", "show", f"{BASELINE}:{path.as_posix()}"])


def audit():
    files = {}
    replays = {}

    def source(path):
        raw = archived(path)
        files[path.as_posix()] = digest(raw)
        return raw

    def ledger(folder):
        return json.loads(source(RT / folder / "evidence.json"))

    replayable = ("PER-CLAIM-TRUST-01", "CHECKED-BYTE-PROOF-ROUTES-01")
    with TemporaryDirectory(prefix="llmlang-trust-crosswalk-") as temp:
        root = Path(temp)
        archive = execute(["git", "archive", BASELINE, *(RT / folder for folder in replayable)])
        with tar_open(fileobj=BytesIO(archive)) as selection:
            selection.extractall(root, filter="data")
        for folder in replayable:
            fixture = root / RT / folder
            if folder == "CHECKED-BYTE-PROOF-ROUTES-01":
                axiom_output = execute(["lean", "-DwarningAsError=true", "Regions.lean"], fixture)
                if axiom_output != source(RT / folder / "axioms.txt"):
                    raise AssertionError("Checked-byte axiom transcript mismatch")
            value = execute([sys.executable, "-B", "run.py"], fixture)
            if value != source(RT / folder / "evidence.json"):
                raise AssertionError(f"Ledger replay mismatch for {folder}")
            replays[folder] = digest(value)

    local = ledger("PER-CLAIM-TRUST-01")
    routes = ledger("CHECKED-BYTE-PROOF-ROUTES-01")
    formats = ledger("PROOF-FORMAT-RECEIPTS-01")
    boundary = ledger("LOGOS-BOUNDARY-RECHECK-01")
    verdict = ledger("LOGOS-VERDICT-PROOF-01")
    source(RT / "LOGOS-VERDICT-PROOF-01" / "build-provenance.json")
    source(RT / "LOGOS-VERDICT-PROOF-01" / "CheckedVerdict.lean")
    conditional_source = source(CONDITIONAL_SOURCE).decode("utf-8")
    theorem_body = conditional_source.split("theorem checkedRefutation_noDependence", maxsplit=1)[1]
    theorem_signature = theorem_body.split(" := by", maxsplit=1)[0]
    premise_fields = ["compiled", "certified", "tableValidated", "wellFormed", "soundVerdict"]
    if not all(f"({name} :" in theorem_signature for name in premise_fields):
        raise AssertionError("The observed source theorem signature changed")

    standard = set(verdict["standard_axioms"])
    native = verdict["verdict_native_axioms"]
    exact = set_digest(standard | set(native))
    if exact != verdict["theorems"][PINNED]["set_sha256"] or len(set(native)) != 2118:
        raise AssertionError("Pinned native axiom set disagrees with preexisting audit")
    conditional_axioms = boundary["archived_source_profiles"]["logos-source-refutation"]["theorems"][CONDITIONAL]
    if set(conditional_axioms) != standard:
        raise AssertionError("Conditional theorem axiom class changed")

    scoped_receipt = next(row for row in formats["receipts"]
                          if row["format"] == "cpc-text/1" and row["checker_result"] == "runtime-cpc-accepted")
    witness = routes["solvers"]["z3"]["checks"]["inclusive_overflow"]["validated_witness"]
    if not all(-128 <= argument <= 127 for argument in witness) or sum(witness) != 128:
        raise AssertionError("The archived SAT witness does not distinguish the cutoff")
    native_rows = routes["native"]["rows_per_optimization"]
    if len(set(routes["native"]["profile_sha256"].values())) != 1 or native_rows != 393216:
        raise AssertionError("Unexpected native observation set")

    def claim(kind, subject, components, axioms=(), *, premises=(), native_count=0, native_digest=None):
        return {"kind": kind, "subject": subject, "components": components,
                "standard_axioms": sorted(axioms), "open_premises": list(premises),
                "native_count": native_count, "full_axiom_set_sha256": native_digest}

    records = {
        "kernel_reduction": claim("kernel-proof", "TrustBoundary.wrappedKernel",
                                  ["pinned Lean kernel and imported module contents"],
                                  local["declarations"]["wrappedKernel"]["axioms"]),
        "kernel_open_premise": claim("kernel-proof", "TrustBoundary.openPremise",
                                     ["pinned Lean kernel and imported module contents"],
                                     local["declarations"]["openPremise"]["axioms"],
                                     premises=["observedInput = 9"]),
        "conditional_source_refutation": claim(
            "kernel-proof", CONDITIONAL, ["pinned proof kernel", "typed source and wire correspondence"],
            conditional_axioms, premises=premise_fields,
        ),
        "pinned_source_refutation": claim(
            "kernel-proof", PINNED,
            ["pinned proof kernel", "typed source and wire correspondence", "pinned upstream proof dependencies"],
            standard, premises=premise_fields[:3], native_count=len(native), native_digest=exact,
        ),
        "cpc_runtime": claim(
            "runtime-verdict", scoped_receipt["receipt_key"],
            ["pinned Lean runtime", "Logos parser and runtime", "exact source and wire gate"],
        ),
        "smt_witness": claim(
            "validated-witness", f"checked-byte cutoff and witness {witness}",
            ["exact QF_LIA mismatch subject", "fixture integer witness evaluator"],
        ),
        "native_correspondence": claim(
            "native-test", next(iter(routes["native"]["profile_sha256"].values())),
            ["two pinned GCC profiles", "host execution", "instrumented C events", "finite reference comparison"],
        ),
    }

    basis = {
        "kernel_reduction": [RT / "PER-CLAIM-TRUST-01/evidence.json"],
        "kernel_open_premise": [RT / "PER-CLAIM-TRUST-01/evidence.json"],
        "conditional_source_refutation": [RT / "LOGOS-BOUNDARY-RECHECK-01/evidence.json", CONDITIONAL_SOURCE],
        "pinned_source_refutation": [RT / "LOGOS-VERDICT-PROOF-01/evidence.json",
                                     RT / "LOGOS-VERDICT-PROOF-01/build-provenance.json",
                                     RT / "LOGOS-VERDICT-PROOF-01/CheckedVerdict.lean"],
        "cpc_runtime": [RT / "PROOF-FORMAT-RECEIPTS-01/evidence.json"],
        "smt_witness": [RT / "CHECKED-BYTE-PROOF-ROUTES-01/evidence.json"],
        "native_correspondence": [RT / "CHECKED-BYTE-PROOF-ROUTES-01/evidence.json"],
    }
    for label, paths in basis.items():
        records[label]["basis_sha256"] = {path.as_posix(): files[path.as_posix()] for path in paths}

    def check(expected, submitted):
        if expected != submitted:
            return "scope-or-basis-mismatch"
        if expected["kind"] != "kernel-proof":
            return expected["kind"]
        if expected["native_count"]:
            return "native-trust-pending"
        if expected["open_premises"]:
            return "conditional-proof"
        return "closed-model-proof"

    cases = {label: check(row, row) for label, row in records.items()}
    faults = {}
    for label, name, field, replacement in (
        ("drop_explicit_premise", "kernel_open_premise", "open_premises", []),
        ("erase_source_soundness_premise", "conditional_source_refutation", "open_premises", premise_fields[:-1]),
        ("erase_full_upstream_context", "pinned_source_refutation", "components", ["pinned proof kernel"]),
        ("erase_native_count", "pinned_source_refutation", "native_count", 0),
        ("replace_native_name_with_same_count", "pinned_source_refutation", "full_axiom_set_sha256",
         set_digest(standard | set(native[:-1]) | {"Different." + native[-1]})),
        ("promote_runtime_cpc_verdict", "cpc_runtime", "kind", "kernel-proof"),
        ("relabel_solver_witness_as_kernel_proof", "smt_witness", "kind", "kernel-proof"),
        ("promote_native_case_to_universal", "native_correspondence", "kind", "kernel-proof"),
    ):
        expected = records[name]
        mutated = copy.deepcopy(expected)
        mutated[field] = replacement
        faults[label] = check(expected, mutated)
    if set(faults.values()) != {"scope-or-basis-mismatch"}:
        raise AssertionError(faults)
    return {
        "schema": "llmlang-claim-trust-crosswalk/1", "baseline": BASELINE, "python": platform.python_version(),
        "input_sha256": files, "fresh_replay_sha256": replays, "claims": records,
        "strict_policy_projection": cases, "fault_controls": faults,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
