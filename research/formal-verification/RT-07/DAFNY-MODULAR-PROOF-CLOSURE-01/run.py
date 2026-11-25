"""Compare Dafny modular proof scopes, Lean closure and an exact CPC certificate."""

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RELEASE = "a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179"
LOGOS_REVISION = "cf18742973861b3718d04c5f25775448098ff474"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
LOGOS_LEAN_REVISION = "293d5d0c0c3f3dded4688b3ccd6a33939ac5102b"
PROVER = "282d5e0c84baf49c780704c532f87ba66d8b513d"
CALLER = "Client.Fits (correctness)"
PROVIDER = "Provider.LastOrdinal (correctness)"
UPPER_ASSUMPTION = "             (< 18446744073709551615 (+ base (* 16 (+ last 1))))\n"


def run(directory, *args, data=None, check=True, environment=None):
    return subprocess.run(list(map(str, args)), cwd=directory, input=data, text=True, capture_output=True,
                          check=check, timeout=90, env=environment or {**os.environ, "LC_ALL": "C"})


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def dafny_observation(directory, command):
    process = run(directory, *command, check=False)
    match = re.search(r"Dafny program verifier finished with (\d+) verified, (\d+) errors?"
                      r"(?:, (\d+) out of resource)?", process.stdout)
    if match is None:
        raise ValueError((process.returncode, process.stdout, process.stderr))
    verified, errors, exhausted = [int(item or 0) for item in match.groups()]
    with (directory / "verification.csv").open(encoding="utf-8", newline="") as handle:
        rows = sorted((row["TestResult.DisplayName"], row["TestResult.Outcome"]) for row in csv.DictReader(handle))
    entries = dict(rows)
    assert len(rows) == len(entries)
    files = sorted(directory.glob("program*.bpl"))
    assert files
    printed = {file.name: file.read_text(encoding="utf-8").replace(f"{directory}/", "") for file in files}
    text = "\n".join(printed.values())
    provider_impl = bool(re.search(r"^implementation [^\n]*Impl\$\$Provider\.__default\.LastOrdinal", text,
                                   flags=re.MULTILINE))
    assert "call {:id" in text and "Call$$Provider.__default.LastOrdinal" in text
    stat = {"verified": verified, "errors": errors, "out_of_resource": exhausted, "exit": process.returncode}
    proof_inputs = {name: sha(directory / name) for name in ("Client.dfy", "Provider.dfy")}
    return stat | {"obligations": entries, "provider_body_in_boogie": provider_impl,
                   "boogie_sha256": {name: sha256(body.encode()).hexdigest() for name, body in printed.items()}, "source_sha256": proof_inputs}


def observe_dafny(directory, dafny, solvers):
    exact = (HERE / "Provider.dfy").read_text(encoding="utf-8")
    implementation = "last := (MaxWord - base) / 16;"
    assert exact.count(implementation) == 1
    mutant = exact.replace(implementation, "last := 0;")
    scenarios = {
        "caller_only": (exact, (), "conditional-caller"),
        "caller_only_wrong_provider": (mutant, (), "conditional-caller"),
        "closed": (exact, ("--verify-included-files",), "verified-source-closure"),
        "wrong_provider_closure": (mutant, ("--verify-included-files",), "verification-failure"),
        "resource_exhaustion": (exact, ("--resource-limit", "1"), "unknown-resource"),
    }
    results = {}
    for version, solver in solvers.items():
        cases = {}
        for name, (provider, flags, result) in scenarios.items():
            case = directory / f"z3-{version}-{name}"
            case.mkdir()
            shutil.copyfile(HERE / "Client.dfy", case / "Client.dfy")
            (case / "Provider.dfy").write_text(provider, encoding="utf-8")
            command = (dafny, "verify", "--cores", "1", "--verification-time-limit", "20",
                       "--solver-path", solver, "--bprint", "program.bpl",
                       "--log-format", "csv;LogFileName=verification.csv", *flags, "Client.dfy")
            observed = dafny_observation(case, command)
            closure = name in ("closed", "wrong_provider_closure")
            assert observed["provider_body_in_boogie"] == closure, observed
            expected_entries = {CALLER: "Passed"}
            if closure:
                expected_entries[PROVIDER] = "Failed" if name == "wrong_provider_closure" else "Passed"
            if name == "resource_exhaustion":
                expected_entries[CALLER] = "Failed"
            assert observed["obligations"] == expected_entries, (name, observed)
            assert (observed["verified"], observed["errors"], observed["out_of_resource"], observed["exit"]) == {
                "conditional-caller": (1, 0, 0, 0),
                "verified-source-closure": (2, 0, 0, 0),
                "verification-failure": (1, 1, 0, 4),
                "unknown-resource": (0, 0, 1, 4),
            }[result], (name, observed)
            cases[name] = observed | {"disposition": result}
        assert cases["caller_only"]["boogie_sha256"] == cases["caller_only_wrong_provider"]["boogie_sha256"]
        assert cases["caller_only"]["source_sha256"] != cases["caller_only_wrong_provider"]["source_sha256"]
        results[version] = cases
    return results


def host_timeout(directory, dafny):
    delayed = "import os, sys, time; time.sleep(10); os.execv(sys.argv[1], sys.argv[1:])"
    try:
        subprocess.run([sys.executable, "-c", delayed, str(dafny), "verify", "Client.dfy"],
                       cwd=directory, capture_output=True, timeout=0.25, check=True)
    except subprocess.TimeoutExpired as expired:
        assert not expired.stdout and not expired.stderr
        return {"deadline_ms": 250, "injected_delay_ms": 10000, "disposition": "unknown-host-timeout"}
    raise AssertionError("delayed verifier unexpectedly finished before the deadline")


def lean_proofs(directory, lean):
    result = run(directory, lean, "-DwarningAsError=true", HERE / "Threshold.lean")
    axioms = {}
    for theorem, names in re.findall(r"'Threshold\.(\w+)' depends on axioms: \[([^\]]*)\]", result.stdout):
        dependencies = names.split(", ") if names else []
        assert set(dependencies) <= {"propext", "Classical.choice", "Quot.sound"}
        axioms[theorem] = dependencies
    assert set(axioms) == {"proveProvider", "callerConditional", "callerClosed", "substitutedZeroRefuted",
                           "substitutedZeroWrongAtOne"}
    return axioms


def produce_certificate(directory, cvc5, query, granularity):
    notes = ("--no-proof-allow-trust",) if granularity == "dsl-rewrite" else ()
    result = run(directory, cvc5, "--produce-proofs", "--dump-proofs", "--proof-format-mode=cpc",
                 f"--proof-granularity={granularity}", *notes, query)
    lines = result.stdout.splitlines(keepends=True)
    assert [line.strip() for line in (lines[0], lines[1], lines[-1])] == ["unsat", "(", ")"]
    proof = directory / f"{granularity}.cpc"
    proof.write_text("".join(lines[2:-1]), encoding="utf-8")
    return proof


def check_smt(directory, cvc5, logos_checkout, logos_lean):
    query = HERE / "Caller.smt2"
    content = query.read_text(encoding="utf-8")
    assert content.count(UPPER_ASSUMPTION) == 1
    weak_text = content.replace(UPPER_ASSUMPTION, "")
    weak = directory / "without-upper.smt2"
    weak.write_text(weak_text, encoding="utf-8")
    model = run(directory, cvc5, "--lang=smt2", "--produce-models",
                data=weak_text + "(get-value (base last ordinal))\n").stdout
    assert model.startswith("sat\n"), model
    assignments = {key: int(value) for key, value in re.findall(r"\((base|last|ordinal) (\d+)\)", model)}
    base, last, ordinal = (assignments[key] for key in ("base", "last", "ordinal"))
    maximum = (1 << 64) - 1
    assert 0 <= base <= maximum and 0 <= last and 0 <= ordinal
    assert base + 16 * last <= maximum
    assert (ordinal <= last) != (base + 16 * ordinal <= maximum)

    unknown = run(directory, cvc5, "--lang=smt2", "--rlimit=1",
                  data=content + "(get-info :reason-unknown)\n").stdout.splitlines()
    assert unknown == ["unknown", "(:reason-unknown resourceout)"], unknown
    logo = logos_checkout / ".lake" / "build" / "bin" / "logos"
    results = {}
    for granularity in ("theory-rewrite", "dsl-rewrite"):
        proof = produce_certificate(directory, cvc5, query, granularity)
        assert proof.read_bytes() == (HERE / proof.name).read_bytes()
        trust = proof.read_text(encoding="utf-8").count(":rule trust")
        result = run(directory, logo, proof, check=False)
        if granularity == "theory-rewrite":
            assert trust > 0 and result.returncode == 1 and "unknown rule trust" in result.stdout + result.stderr
            status = "rejected-trust"
        else:
            assert trust == 0 and result.returncode == 0 and result.stdout.strip() == "correct"
            status = "correct"
        results[granularity] = {"solver": "unsat", "trust_commands": trust, "logos": status, "proof_sha256": sha(proof)}

    env = {**os.environ, "LC_ALL": "C", "PATH": str(logos_lean.parent) + os.pathsep + os.environ["PATH"]}
    command = (logos_lean.parent / "lake", "env", logos_lean, "-DwarningAsError=true", "--run", HERE / "BoundCpc.lean")
    proof = directory / "dsl-rewrite.cpc"
    accepted = run(logos_checkout, *command, query, proof, environment=env)
    rejected = run(logos_checkout, *command, weak, proof, environment=env, check=False)
    assert accepted.stdout.strip() == "correct"
    assert rejected.stdout.strip() == "assumptions-mismatch" and rejected.returncode == 3
    return {"certificates": results, "exact_binding": "correct", "weaker_binding": "assumptions-mismatch",
            "weaker_query_sha256": sha(weak), "weaker_model": assignments, "resource_limit_1": unknown,
            "logos_executable_sha256": sha(logo)}


def compare(directory, args):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    assert sha(args.archive) == RELEASE
    dafny = args.dafny.resolve()
    logos = args.logos.resolve()
    solvers = {version: dafny.parent / "z3" / "bin" / f"z3-{version}" for version in ("4.12.1", "4.14.1")}
    versions = {
        "dafny": run(directory, dafny, "--version").stdout.strip(),
        "cvc5": run(directory, args.cvc5, "--version").stdout.splitlines()[0],
        "lean": run(directory, args.lean, "--version").stdout.strip(),
        "logos_lean": run(directory, args.logos_lean, "--version").stdout.strip(),
        "logos": run(logos, "git", "rev-parse", "HEAD").stdout.strip(),
        "python": platform.python_version(),
    }
    assert versions["logos"] == LOGOS_REVISION
    assert LEAN_REVISION in versions["lean"] and LOGOS_LEAN_REVISION in versions["logos_lean"]
    assert PROVER[:7] in versions["cvc5"]
    assert not run(logos, "git", "status", "--porcelain", "--untracked-files=no").stdout.strip()
    return {"schema": "llmlang-dafny-modular-proof-closure/1", "tool_versions": versions,
            "dafny_archive_sha256": RELEASE, "z3_sha256": {version: sha(solver) for version, solver in solvers.items()},
            "source_sha256": {name: sha(HERE / name) for name in
                              ("Client.dfy", "Provider.dfy", "Caller.smt2", "Threshold.lean", "BoundCpc.lean", "run.py")},
            "dafny": observe_dafny(directory, dafny, solvers), "host_control": host_timeout(directory / "z3-4.12.1-caller_only", dafny),
            "lean_axioms": lean_proofs(directory, args.lean),
            "cpc": check_smt(directory, args.cvc5, logos, args.logos_lean)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("dafny", "archive", "lean", "logos", "logos-lean", "cvc5"):
        parser.add_argument(f"--{tool}", type=Path, required=True)
    with TemporaryDirectory(prefix="llmlang-dafny-modular-closure-") as directory:
        print(json.dumps(compare(Path(directory), parser.parse_args()), indent=2))
