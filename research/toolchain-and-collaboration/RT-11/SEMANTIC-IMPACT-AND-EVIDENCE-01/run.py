"""Separate observation changes, verification execution identity, and trust."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import verification_key
from src.spg_admission import validate
from src.spg_representation import Implementation, Operation, Program, compile_program, observe

BASELINE = "41ca1e1b2722abc9889d949f0b4a9f8da8310999"
INPUTS = (-2, -1, 0, 1, 2)
EDITS = {
    "original": 'emit("first", emit("second", x))',
    "formatting": '(emit("first",\n    emit("second", x))) # formatting',
    "equal-result-and-trace": 'emit("first", emit("second", x + 0))',
    "changed-trace": 'emit("second", emit("first", x))',
    "changed-value": 'emit("first", emit("second", x + 1))',
}
LEAN_REVISIONS = {
    "4.34.0": "293d5d0c0c3f3dded4688b3ccd6a33939ac5102b",
    "4.36.0": "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prototype_pins():
    pins = {}
    for name in ("semantic_graph.py", "spg_admission.py", "spg_representation.py", "recursive_identity.py"):
        path = PROTOTYPE / "src" / name
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{path.relative_to(ROOT)}"], cwd=ROOT)
        if archived != path.read_bytes():
            raise ValueError(f"fixture input differs from {BASELINE}: {name}")
        pins[name] = digest(archived)
    return pins


def source_graph(body):
    program = Program(
        contracts={"effects": (("first", "second"), ("second", "first"))},
        operations={"entry": Operation("Entry", ("Int",), "Int", "effects")},
        implementations={"entry": Implementation("entry", ("x",), body)}, bindings={},
    )
    result = compile_program(program)
    validate(result)
    return result


def run_lean(engines):
    source = HERE / "Proof.lean"
    versions, source_checks, imports = {}, {}, {}
    with tempfile.TemporaryDirectory(prefix="llmlang-proof-version-") as temporary:
        root = Path(temporary)
        for label, engine in engines.items():
            versions[label] = subprocess.check_output([engine, "--version"], text=True).strip()
            assert LEAN_REVISIONS[label] in versions[label]
            directory = root / label
            directory.mkdir()
            shutil.copyfile(source, directory / "Proof.lean")
            transcript = subprocess.check_output(
                [engine, "-DwarningAsError=true", "-o", "Proof.olean", "Proof.lean"],
                cwd=directory, text=True, timeout=30,
            )
            assert transcript.strip() == "'returnsInput' does not depend on any axioms"
            source_checks[label] = {"axioms": transcript.strip(), "object_sha256": digest(
                (directory / "Proof.olean").read_bytes())}
        importer = root / "ImportProof.lean"
        importer.write_text("import Proof\nexample : checkedResult 7 = 7 := returnsInput 7\n", encoding="utf-8")
        for consumer, producer in product(engines, repeat=2):
            result = subprocess.run(
                [engines[consumer], importer.name], cwd=root,
                env=os.environ | {"LEAN_PATH": str(root / producer)},
                capture_output=True, text=True, timeout=30,
            )
            assert (result.returncode == 0) == (consumer == producer)
            imports[f"{producer}->{consumer}"] = {
                "accepted": result.returncode == 0,
                "reason": (result.stdout or result.stderr).strip().replace(str(root), "<fixture>"),
            }
    return versions, source_checks, imports


def key(graph, version, projection, assumption):
    subject = graph.snapshot.mapping["implementation:entry"]
    return verification_key(subject, graph.snapshot.root_hash, version,
                            {"observation": projection}, (assumption,))


def compare(graphs, versions):
    baseline = graphs["original"]
    cached_version = versions["4.34.0"]
    cached_key = key(baseline, cached_version, "value-and-trace", "all-inputs")
    observations = {name: [observe(graph, "entry", (value,)) for value in INPUTS]
                    for name, graph in graphs.items()}
    rows = []
    for edit, projection, verifier, assumption, policy, exists in product(
        EDITS, ("value-and-trace", "value"), versions, ("all-inputs", "nonnegative-inputs"),
        ("allow-recorded", "exclude-recorded"), (False, True),
    ):
        graph = graphs[edit]
        comparisons = zip(INPUTS, observations["original"], observations[edit], strict=True)
        impact = any(
            (before != after if projection == "value-and-trace" else before[0] != after[0])
            for value, before, after in comparisons if assumption == "all-inputs" or value >= 0
        )
        exact_key = key(graph, versions[verifier], projection, assumption)
        if not exists:
            applicability = "ABSENT"
        elif exact_key != cached_key:
            applicability = "STALE"
        elif policy == "exclude-recorded":
            applicability = "EXACT_NOT_AUTHORIZED"
        else:
            applicability = "CURRENT"
        rows.append({
            "edit": edit, "projection": projection, "verifier": verifier, "assumption": assumption,
            "policy": policy, "cached_receipt_present": exists, "execution_key_matches": exact_key == cached_key,
            "observed_impact": impact, "evidence": applicability,
        })
    assert all(not row["observed_impact"] for row in rows if row["evidence"] == "CURRENT")
    assert graphs["original"].snapshot.root_hash == graphs["formatting"].snapshot.root_hash
    assert graphs["original"].snapshot.root_hash != graphs["equal-result-and-trace"].snapshot.root_hash
    assert observations["original"] == observations["equal-result-and-trace"]
    return observations, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-old", required=True, type=Path)
    parser.add_argument("--lean-new", required=True, type=Path)
    args = parser.parse_args()
    pins = prototype_pins()
    versions, proof_checks, imports = run_lean({
        "4.34.0": args.lean_old.resolve(strict=True), "4.36.0": args.lean_new.resolve(strict=True),
    })
    graphs = {name: source_graph(text) for name, text in EDITS.items()}
    observations, rows = compare(graphs, versions)
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "lean_versions": versions,
        "prototype_sha256": pins,
        "model_sha256": digest((HERE / "Proof.lean").read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "kernel_source_checks": proof_checks, "compiled_imports": imports, "inputs": INPUTS,
        "graphs": {name: {"root": graphs[name].snapshot.root_hash, "text_sha256": digest(text.encode()),
                          "text": text, "observations": observations[name]} for name, text in EDITS.items()},
        "cases": len(rows), "statuses": dict(Counter(row["evidence"] for row in rows)),
        "impact_cross_tab": {str(impact).lower(): dict(Counter(
            row["evidence"] for row in rows if row["observed_impact"] == impact
        )) for impact in (False, True)},
        "comparisons": rows,
    }, indent=2))


if __name__ == "__main__":
    main()
