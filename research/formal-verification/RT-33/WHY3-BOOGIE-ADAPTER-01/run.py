#!/usr/bin/env python3
"""Replay the selected Why3 and Boogie routes and independently check the fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import subprocess
import tempfile
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def invoke(command, directory, env, *, marker=None):
    with subprocess.Popen(command, cwd=directory, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, start_new_session=True) as process:
        try:
            if marker is not None:
                until = time.monotonic() + 15
                while not marker.exists() and process.poll() is None and time.monotonic() < until:
                    time.sleep(0.01)
                assert marker.exists() and process.poll() is None, command
                os.killpg(process.pid, signal.SIGTERM)
            output, _ = process.communicate(timeout=20)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
    return process.returncode, output.decode()


def normalize(output, scratch):
    return output.replace(str(scratch), "<scratch>").replace("\r\n", "\n")


def evaluate(backend, code, output, target):
    if backend == "why3":
        if "not found in theory" in output:
            return "missing-target"
        if "expected to have type" in output:
            return "type-error"
        report = json.loads(output)
        assert report["term"]["goal_name"] == target, report
        answer = report["prover-result"]["answer"]
        if answer == "Valid" and code == 0:
            return "valid"
        if answer == "Unknown\n(sat)":
            return "sat-without-witness"
        if answer == "Step limit\nexceeded":
            return "resource-exhausted"
        raise AssertionError((code, output))
    if "invalid argument types" in output:
        return "type-error"
    summary = re.search(r"finished with (\d+) verified, (\d+) errors?", output)
    assert summary, output
    counts = tuple(map(int, summary.groups()))
    if counts == (1, 0) and code == 0:
        return "valid"
    if counts == (0, 0):
        return "missing-target"
    assert counts == (0, 1) and "a postcondition could not be proved" in output, output
    return "failed-postcondition"


def record(backend, code, output, scratch):
    output = normalize(output, scratch)
    if backend == "why3" and output.lstrip().startswith("{"):
        result = json.loads(output)
        result["prover-result"].pop("time")
        return {"exit": code, "report": result}
    return {"exit": code, "diagnostic": output.strip()}


def prepare_sources(directory):
    for name, required, premise in [("valid", 4, 3), ("invalid", 5, 3),
                                    ("illtyped", 4, "true")]:
        (directory / f"{name}.why").write_text(
            "theory Fixture\n  use int.Int\n"
            f"  goal Verify: forall i: int. i = {premise} -> i + 1 = {required}\n"
            "  goal Decoy: forall i: int. i = 3 -> i + 1 = 99\nend\n")
        (directory / f"{name}.bpl").write_text(
            "procedure Verify(i: int) returns (r: int)\n"
            f"  requires i == {premise};\n  ensures r == {required};\n{{\n  r := i + 1;\n}}\n\n"
            "procedure Decoy(i: int) returns (r: int)\n"
            "  requires i == 3;\n  ensures r == 99;\n{\n  r := i + 1;\n}\n")


def independent(args, root, env, expected, identifier):
    required = {"valid": 4, "invalid": 5, "decoy": 99}[identifier]
    formula = ("(set-logic QF_LIA)\n(declare-const i Int)\n"
               f"(assert (= i 3))\n(assert (not (= (+ i 1) {required})))\n(check-sat)\n")
    condition = root / f"independent-{identifier}.smt2"
    condition.write_text(formula)
    code, result = invoke([args.cvc5, "--produce-proofs", "--proof-format-mode=alethe",
                           "--proof-alethe-res-pivots", "--dump-proofs", condition], root, env)
    assert code == 0 and result.splitlines()[0] == expected, result
    proof = None
    native = None
    native_check = None
    witness = None
    if expected == "unsat":
        prefix = "unsat\n(\n"
        assert result.startswith(prefix) and result.endswith(")\n"), result
        native = root / "cvc5-valid.alethe"
        native.write_text(result[len(prefix):-2])
        code, checked = invoke([args.carcara, "check", native, condition], root, env)
        native_check = checked.strip()
        assert code == 0 and native_check == "holey", checked
        proof = Path(__file__).with_name("independent-valid.alethe")
        code, checked = invoke([args.carcara, "check", proof, condition], root, env)
        assert code == 0 and checked.strip() == "valid", checked
    else:
        query = "(set-option :produce-models true)\n" + formula + "(get-value (i))\n"
        condition.write_text(query)
        code, result = invoke([args.z3, "-smt2", condition], root, env)
        match = re.fullmatch(r"sat\s+\(\(i (-?\d+)\)\)\s*", result)
        assert code == 0 and match, result
        value = int(match.group(1))
        assert value == 3 and value + 1 != required
        witness = {"i": value, "r": value + 1, "required": required}
        condition.write_text(formula)
    return {"formula": formula, "result": expected, "validated_witness": witness,
            "carcara": None if proof is None else "valid",
            "certificate": None if proof is None else proof.read_text(),
            "native_certificate": None if native is None else native.read_text(),
            "native_certificate_carcara": native_check}


def main():
    parser = argparse.ArgumentParser()
    for program in ("why3", "dotnet", "boogie-dll", "z3", "cvc5", "carcara"):
        parser.add_argument(f"--{program}", type=lambda value: str(Path(value).resolve()), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt33-vc-adapters-") as scratch:
        root = Path(scratch)
        env = {**os.environ, "PATH": str(Path(args.z3).parent) + os.pathsep + os.environ["PATH"],
               "DOTNET_CLI_HOME": scratch, "DOTNET_NOLOGO": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
               "LC_ALL": "C"}
        versions = {}
        for name, command, version in [
            ("why3", [args.why3, "--version"], "version 1.8.0"),
            ("boogie", [args.dotnet, args.boogie_dll, "/version"], "3.5.8.0"),
            ("z3", [args.z3, "--version"], "4.13.3"),
            ("cvc5", [args.cvc5, "--version"], "1.4.2"),
            ("carcara", [args.carcara, "--version"], "1.1.0"),
        ]:
            code, output = invoke(command, root, env)
            assert code == 0 and version in output, output
            versions[name] = output.splitlines()[0]
        prepare_sources(root)
        config = root / "why3.conf"
        code, output = invoke([args.why3, "config", "-C", config, "detect"], root, env)
        assert code == 0 and f'path = "{args.z3}"' in config.read_text(), output
        why3 = [args.why3, "prove", "-C", config, "-P", "Z3,4.13.3,"]
        boogie = [args.dotnet, args.boogie_dll]
        rows = {}
        for name, source, target, expected in [
            ("valid", "valid", "Verify", ["valid", "valid"]),
            ("invalid", "invalid", "Verify", ["sat-without-witness", "failed-postcondition"]),
            ("decoy", "valid", "Decoy", ["sat-without-witness", "failed-postcondition"]),
            ("missing", "valid", "Missing", ["missing-target", "missing-target"]),
            ("illtyped", "illtyped", "Verify", ["type-error", "type-error"]),
            ("limited", "invalid", "Verify", ["resource-exhausted", "failed-postcondition"]),
        ]:
            rows[name] = {}
            for backend, extension, disposition in zip(("why3", "boogie"), ("why", "bpl"), expected):
                source_path = root / f"{source}.{extension}"
                if backend == "why3":
                    selection = [source_path, "-T", "Fixture", "-G", target]
                    command = why3 + ["--json"] + (["-s", "1"] if name == "limited" else []) + selection
                else:
                    log = root / f"{name}-@PROC@.smt2"
                    command = boogie + [f"/proc:{target}", f"/proverOpt:PROVER_PATH={args.z3}",
                                         f"/proverLog:{log}"]
                    command += (["/rlimit:1"] if name == "limited" else []) + [source_path]
                code, output = invoke(command, root, env)
                actual = evaluate(backend, code, output, target)
                assert actual == disposition, (name, backend, actual, output)
                row = {"target": target, "disposition": actual,
                       "source": source_path.read_text(), "source_sha256": digest(source_path.read_bytes()),
                       **record(backend, code, output, root)}
                rows[name][backend] = row
                if name not in ("valid", "invalid", "decoy", "limited"):
                    continue
                if backend == "why3":
                    if name == "limited":
                        continue
                    emitted = root / f"export-{name}"
                    emitted.mkdir()
                    status, export = invoke(why3 + ["-o", emitted] + selection, root, env)
                    assert status == 0, export
                    [native] = emitted.glob("*.smt2")
                    assert native.name.endswith(f"-Fixture-{target}.smt2")
                else:
                    native = root / f"{name}-{target}.smt2"
                    assert f":boogie-vc-id {target})" in native.read_text()
                    if name == "limited":
                        assert "(set-option :rlimit 1)" in native.read_text()
                raw = native.read_bytes().decode()
                portable = normalize(raw, root)
                row.update({"normalized_native_query": portable,
                            "normalized_native_sha256": digest(portable.encode())})
                if name == "limited":
                    continue
                prefix, delimiter, _ = raw.partition("(check-sat)")
                assert delimiter and "(assert" in prefix, raw
                replay = root / f"replay-{name}-{backend}.smt2"
                replay.write_text(prefix + delimiter + "\n")
                status, verdict = invoke([args.z3, "-smt2", replay], root, env)
                assert status == 0 and verdict.strip() == ("unsat" if name == "valid" else "sat"), verdict
                row["native_first_verdict_replay"] = verdict.strip()

        blocker = root / "wait-for-cancel"
        blocker.write_text(
            f"#!{sys.executable}\nimport os, pathlib, sys, time\n"
            "if '--version' in sys.argv or '-version' in sys.argv:\n"
            "    os.execv(os.environ['FIXTURE_Z3'], [os.environ['FIXTURE_Z3'], *sys.argv[1:]])\n"
            "pathlib.Path(os.environ['FIXTURE_READY']).write_text('solver started')\n"
            "time.sleep(90)\n")
        blocker.chmod(0o700)
        slow_config = root / "slow.conf"
        slow_config.write_text(config.read_text().replace(args.z3, str(blocker)))
        rows["host-cancel"] = {}
        for backend, command in [
            ("why3", [args.why3, "prove", "-C", slow_config, "--json", "-P", "Z3,4.13.3,",
                      root / "valid.why", "-T", "Fixture", "-G", "Verify"]),
            ("boogie", boogie + ["/proc:Verify", f"/proverOpt:PROVER_PATH={blocker}",
                                 root / "valid.bpl"]),
        ]:
            ready = root / f"{backend}-started"
            code, output = invoke(command, root, {
                **env, "FIXTURE_Z3": args.z3, "FIXTURE_READY": str(ready),
            }, marker=ready)
            assert code != 0 and "Valid" not in output and "1 verified" not in output, output
            rows["host-cancel"][backend] = {"target": "Verify", "disposition": "host-cancelled",
                                            "solver_started": ready.read_text() == "solver started",
                                            **record(backend, code, output, root)}

        audits = {name: independent(args, root, env, verdict, name) for name, verdict in
                  [("valid", "unsat"), ("invalid", "sat"), ("decoy", "sat")]}
        result = {"versions": versions, "frontend_rows": rows, "independent_fragment": audits}
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
