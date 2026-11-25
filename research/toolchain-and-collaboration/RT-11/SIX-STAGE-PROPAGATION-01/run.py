#!/usr/bin/env python3
"""Trace native artifacts and evidence across scoped changes."""

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
MODES = ("direct", "contract")
STAGES = ("type", "contract", "optimize", "codegen", "test", "proof")
DRIVER = r"""#include <stdio.h>
int invoke(int);
int main(void) {
    for (int n = -8; n <= 8; ++n)
        printf("%d\n", invoke(n));
    return 0;
}
"""
LATE = "int provider(int);\nint invoke(int n) { return provider(n); }\n"
DIRECT = '#include "provider.h"\nint invoke(int n) { return provider(n); }\n'


@dataclass(frozen=True)
class Variant:
    body: str = "n+(1+1)"
    structure: tuple = ("add", "n", ("add", 1, 1))
    offset: int = 2
    limit: int = 10
    proof_checker: str = "lean/4.36.0/approved-standard"
    test_inputs: tuple = (-8, 0, 8)
    unused_candidate: str = "other-provider-v1"


BASELINE = Variant()
VARIANTS = {
    "baseline": BASELINE,
    "equivalent_provider": replace(BASELINE, body="n+2", structure=("add", "n", 2)),
    "different_provider": replace(BASELINE, body="n+3", structure=("add", "n", 3), offset=3),
    "contract_changed": replace(BASELINE, limit=11),
    "unused_candidate_changed": replace(BASELINE, unused_candidate="other-provider-v2"),
    "checker_policy_changed": replace(BASELINE, proof_checker="lean/4.36.0/changed-policy"),
    "test_fixture_changed": replace(BASELINE, test_inputs=(-3, 0, 3)),
    "wrong_provider_type": replace(BASELINE, body='"wrong"', structure=("literal-string", "wrong")),
}


def content(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(data).hexdigest()


def file_id(path):
    return sha256(path.read_bytes()).hexdigest()


def command(compiler, directory, *args, accept=True):
    proc = subprocess.run([compiler, *args], cwd=directory, text=True, capture_output=True)
    if (proc.returncode == 0) != accept:
        raise AssertionError((args, proc.stdout, proc.stderr))
    return proc


def build(path, compiler, toolchain, mode, variant):
    path.mkdir()
    interface = "Int32->Int32/admitted-int-range"
    contract = content(["return-upper-bound", 8, variant.limit])
    # The provider body identity is independent of the request to check a new upper bound.
    provider = content(["provider-impl-fixture/1", interface, variant.structure])
    abstract = content(["provider-operation-fixture/1", interface])
    caller = content(["caller-fixture/1", mode, provider if mode == "direct" else abstract])
    flags = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-O2")
    (path / "main.c").write_text(DRIVER)
    (path / "caller.c").write_text(DIRECT if mode == "direct" else LATE)
    definition = f"int provider(int n) {{ return {variant.body}; }}\n"
    (path / "provider.c").write_text(definition)
    (path / "provider.h").write_text("static inline " + definition)

    keys = {"type": content(["type", caller, provider, interface, toolchain["gcc"], flags])}
    modules = ["caller"] if mode == "direct" else ["caller", "provider"]
    admitted = variant.structure[0] != "literal-string"
    proc = command(compiler, path, *flags, "-fsyntax-only", *(f"{stem}.c" for stem in modules),
                   accept=admitted)
    if not admitted:
        if "int-conversion" not in proc.stderr:
            raise AssertionError(proc.stderr)
        return {"keys": keys, "caller": caller, "provider": provider,
                "type": "refused"}

    keys["optimize"] = content(["optimizer", caller, provider, toolchain["gcc"], flags])
    artifacts = {}
    for stem in modules:
        command(compiler, path, *flags, "-S", f"{stem}.c", "-o", f"{stem}.s")
    assemblies = {stem: file_id(path / f"{stem}.s") for stem in modules}
    keys["codegen"] = content(["assemble-and-link", assemblies, file_id(path / "main.c"),
                               toolchain, flags])
    for stem in modules:
        command(compiler, path, "-c", f"{stem}.s", "-o", f"{stem}.o")
        artifacts[stem] = file_id(path / f"{stem}.o")
    command(compiler, path, *flags, "main.c", *(f"{stem}.o" for stem in modules), "-o", "execute")
    executable = file_id(path / "execute")
    run = subprocess.run([str(path / "execute")], cwd=path, text=True, capture_output=True, check=True)
    actual = [int(row) for row in run.stdout.splitlines()]
    expected = [n + variant.offset for n in range(-8, 9)]
    if actual != expected or run.stderr:
        raise AssertionError((mode, variant, actual, expected))
    keys["test"] = content(["test/1", executable, variant.test_inputs, BASELINE.offset])
    keys["contract"] = content(["conformance", caller, provider, contract])
    keys["proof"] = content(["proof", keys["contract"], variant.proof_checker])
    return {
        "keys": keys, "caller": caller, "provider": provider,
        "type": "checked", "assemblies": assemblies,
        "objects": artifacts, "executable": executable, "native_cases": len(actual),
        "contract_passes": all(value <= variant.limit for value in actual),
        "exact_tests_pass": all(actual[n + 8] == BASELINE.offset + n for n in variant.test_inputs),
    }


def verify_contract(lean, directory, variant):
    args = f"{variant.offset} 8 {variant.limit}"
    positive = 8 + variant.offset <= variant.limit
    prefix = "" if positive else "¬ "
    tactic = "exact (affine_bound_iff " + args + ").2 (by decide)" if positive else (
        "exact endpoint_refutes " + args + " (by decide)")
    source = ("import Bound\n"
              f"theorem fixtureProperty : {prefix}bounded {args} := by\n"
              f"  {tactic}\n#print axioms fixtureProperty\n")
    path = directory / "Property.lean"
    path.write_text(source)
    run = subprocess.run([lean, "-DwarningAsError=true", path.name], cwd=directory,
                         env={**os.environ, "LEAN_PATH": str(directory)}, text=True,
                         capture_output=True, check=True)
    if run.stderr or "sorryAx" in run.stdout:
        raise AssertionError((run.stdout, run.stderr))
    return {"disposition": "checked" if positive else "refuted",
            "generated_sha256": file_id(path), "axioms": run.stdout.splitlines()}


def compare():
    compiler = os.environ.get("CC", "gcc")
    lean = os.environ.get("LEAN", "lean")
    toolchain = {"gcc": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]}
    for program in ("as", "ld"):
        tool = subprocess.check_output([compiler, f"-print-prog-name={program}"], text=True).strip()
        toolchain[program] = subprocess.check_output([tool, "--version"], text=True).splitlines()[0]
    reports = {}
    with tempfile.TemporaryDirectory() as build_dir:
        directory = Path(build_dir)
        (directory / "Bound.lean").write_bytes((HERE / "Bound.lean").read_bytes())
        check = command(lean, directory, "-DwarningAsError=true", "-o", "Bound.olean", "Bound.lean")
        if check.stdout != (HERE / "axioms.txt").read_text():
            raise AssertionError("Bound theorem dependency mismatch")
        proofs = {name: verify_contract(lean, directory, variant)
                  for name, variant in VARIANTS.items() if name != "wrong_provider_type"}
        for mode in MODES:
            here = Path(build_dir) / mode
            here.mkdir()
            rows = {key: build(here / key, compiler, toolchain, mode, variant)
                    for key, variant in VARIANTS.items()}
            base = rows["baseline"]
            for name, row in rows.items():
                row["keys_changed"] = [stage for stage in STAGES
                                       if row["keys"].get(stage) != base["keys"][stage]]
                row["same_caller"] = row["caller"] == base["caller"]
                row["same_provider"] = row["provider"] == base["provider"]
                row["same_unselected_candidate"] = (
                    VARIANTS[name].unused_candidate == BASELINE.unused_candidate)
                if name in proofs:
                    row["model_proof"] = proofs[name]
                    assert (proofs[name]["disposition"] == "checked") == row["contract_passes"]
            assert rows["equivalent_provider"]["executable"] == base["executable"]
            assert rows["equivalent_provider"]["keys_changed"] == ["type", "contract", "optimize", "proof"]
            assert rows["different_provider"]["keys_changed"] == list(STAGES)
            assert not rows["different_provider"]["contract_passes"]
            assert not rows["different_provider"]["exact_tests_pass"]
            assert rows["contract_changed"]["keys_changed"] == ["contract", "proof"]
            assert rows["unused_candidate_changed"]["keys_changed"] == []
            assert rows["checker_policy_changed"]["keys_changed"] == ["proof"]
            assert rows["test_fixture_changed"]["keys_changed"] == ["test"]
            assert rows["wrong_provider_type"]["type"] == "refused"
            assert set(rows["wrong_provider_type"]["keys"]) == {"type"}
            assert rows["different_provider"]["same_caller"] == (mode == "contract")
            if mode == "contract":
                assert rows["different_provider"]["objects"]["caller"] == base["objects"]["caller"]
            reports[mode] = rows
    return {"native_toolchain": toolchain,
            "lean": subprocess.check_output([lean, "--version"], text=True).strip(),
            "by_call_mode": reports}


if __name__ == "__main__":
    print(json.dumps({
        "schema": "llmlang-six-stage-propagation/1", "python": platform.python_version(),
        "sources_sha256": {name: file_id(HERE / name)
                           for name in ("run.py", "Bound.lean", "axioms.txt")},
        "results": compare(),
    }, indent=2))
