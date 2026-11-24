"""Kernel-check bounded state claims for the finite transition fixtures."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from shutil import which

from machine import execute_validated, validate
from oracle import expected
from templates import FAMILIES, VARIANTS, model, scenarios

PROFILE = {
    "id": "transition-state-lean-v1",
    "lean_version": "4.36.0",
    "lean_commit": "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9",
    "obligation": "state at each action boundary for fixed initial registers and trace",
    "timeout_seconds": 30,
    "unsupported": ["effects", "invariants", "noninterference",
                    "symbolic inputs", "unbounded traces"],
}
ROOT = Path(__file__).resolve().parent
CONTROL = """def controlActions : List Program := [.assign 0 (.literal (-1)) .done,
    .assign 0 (.literal 0) .done]
theorem controlAll : observe [0] controlActions ≠ [[0], [0]] := by decide
#print axioms controlAll
theorem controlFinal : (observe [0] controlActions).getLast? = some [0] := rfl
#print axioms controlFinal
"""
FALSE_CLAIM = "example : observe [0] controlActions = [[0], [0]] := by decide\n"


def expression(expr, registers):
    op, *args = expr
    if op == "int":
        return f"(.literal ({args[0]}))"
    if op == "reg":
        return f"(.register {registers[args[0]]})"
    terms = " ".join(expression(arg, registers) for arg in args)
    return f"(.{op} {terms})"


def block(code, registers):
    continuation = ".done"
    for op, *args in reversed(code):
        if op == "set":
            name, value = args
            continuation = f"(.assign {registers[name]} {expression(value, registers)} {continuation})"
        elif op == "if":
            guard, yes, no = args
            continuation = (f"(.branch {expression(guard, registers)} "
                            f"{block(yes, registers)} {block(no, registers)} {continuation})")
    return continuation


def vector(state, registers):
    return "[" + ", ".join(str(state[name]) for name in registers) + "]"


def experiment():
    source = [ROOT.joinpath("TransitionState.lean").read_text(), "open TransitionState", ""]
    records = []

    for parameter, family in enumerate(FAMILIES, start=2):
        for variant in VARIANTS:
            machine = model(family, parameter, variant)
            validate(machine)
            registers = {name: index for index, name in enumerate(sorted(machine["initial"]))}
            prefix = f"fixture{parameter}_{variant}"
            actions = {}
            for index, (name, code) in enumerate(sorted(machine["actions"].items())):
                action = f"{prefix}_{index}"
                actions[name] = action
                source.append(f"def {action} : Program := {block(code, registers)}")

            for override, trace in scenarios(family, parameter):
                initial = machine["initial"] | override
                gold = [step["state"] for step in expected(family, parameter, override, trace)]
                replay = [step["state"] for step in execute_validated(machine, trace, initial)]
                name = f"check{len(records):04d}"
                relation = "=" if replay == gold else "≠"
                proof = "rfl" if relation == "=" else "by decide"
                trace_term = "[" + ", ".join(actions[action] for action in trace) + "]"
                gold_term = "[" + ", ".join(vector(state, registers) for state in gold) + "]"
                source.append(f"theorem {name} : observe {vector(initial, registers)} "
                              f"{trace_term} {relation} {gold_term} := {proof}")
                source.append(f"#print axioms {name}")
                records.append({
                    "claim": name, "family": family, "variant": variant, "parameter": parameter,
                    "initial": initial, "trace": trace, "expected": gold, "replay": replay,
                    "model_sha256": sha256(json.dumps(machine, sort_keys=True).encode()).hexdigest(),
                    "relation": "equal" if relation == "=" else "different",
                })
            source.append("")
    source.append(CONTROL)
    return "\n".join(source), records


def audits_claims(output, claims):
    accepted = ("does not depend on any axioms",
                "depends on axioms: [propext, Classical.choice, Quot.sound]")
    lines = output.splitlines()
    return len(lines) == len(claims) and all(
        line in {f"'{claim}' {suffix}" for suffix in accepted}
        for claim, line in zip(claims, lines)
    )


def compare_smt(raw, records):
    def scope(record):
        return {field: record[field] for field in (
            "family", "variant", "parameter", "initial", "trace", "expected",
            "replay", "model_sha256",
        )}

    smt_cases = [json.loads(line) for line in raw.splitlines()]
    if len(smt_cases) != len(records) + 2:
        return False
    observations, controls = smt_cases[:-2], smt_cases[-2:]
    for record, observation in zip(records, observations):
        expected_result = ("unsat", "bounded-agreement") if record["relation"] == "equal" else (
            "sat", "replayed-counterexample"
        )
        if (scope(record) != scope(observation)
                or (observation["solver"], observation["outcome"]) != expected_result):
            return False
    return [(c["control"], c["solver"], c["outcome"]) for c in controls] == [
        ("all-boundaries", "sat", "replayed-counterexample"),
        ("final-only", "unsat", "translation-or-solver-conflict"),
    ]


def run_lean(binary, path):
    return subprocess.run([binary, path.name], cwd=path.parent, text=True,
                          capture_output=True, check=False, timeout=PROFILE["timeout_seconds"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smt-observations", type=Path)
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    source, records = experiment()
    source_path = options.output / "TransitionClaims.lean"
    source_path.write_text(source, encoding="utf-8")
    control_path = options.output / "FalseClaim.lean"
    control_source = ROOT.joinpath("TransitionState.lean").read_text() + "\nopen TransitionState\n"
    control_path.write_text(control_source + CONTROL + FALSE_CLAIM, encoding="utf-8")
    output = ""
    errors = ""
    version = ""
    status = "abstain"
    negative_output = ""
    negative_rejected = False
    comparison = "not-requested" if options.smt_observations is None else "abstain"
    smt_sha256 = None
    try:
        binary = which(options.lean)
        if binary is None:
            raise FileNotFoundError(options.lean)
        lean = str(Path(binary).absolute())
        process = subprocess.run([lean, "--version"], text=True, capture_output=True,
                                 timeout=PROFILE["timeout_seconds"], check=True)
        version = process.stdout.strip()
        if (version.startswith(f"Lean (version {PROFILE['lean_version']}, ")
                and f"commit {PROFILE['lean_commit']}" in version):
            process = run_lean(lean, source_path)
            output, errors = process.stdout, process.stderr
            claims = [record["claim"] for record in records] + ["controlAll", "controlFinal"]
            negative = run_lean(lean, control_path)
            negative_output = negative.stdout + negative.stderr
            negative_rejected = (negative.returncode == 1
                                 and "the proposition" in negative_output
                                 and "is false" in negative_output)
            if (process.returncode == 0 and not errors and audits_claims(output, claims)
                    and negative_rejected):
                status = "kernel-checked"
                if options.smt_observations is not None:
                    raw = options.smt_observations.read_bytes()
                    smt_sha256 = sha256(raw).hexdigest()
                    comparison = "match" if compare_smt(raw, records) else "conflict"
        else:
            errors = "unsupported Lean version"
    except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as error:
        errors = str(error)
    (options.output / "stdout.txt").write_text(output)
    (options.output / "stderr.txt").write_text(errors)
    (options.output / "false-claim-output.txt").write_text(negative_output)
    for record in records:
        record["status"] = status
    (options.output / "observations.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )
    with (options.output / "outcomes.csv").open("w", newline="") as stream:
        columns = ["claim", "family", "variant", "parameter", "relation", "status"]
        writer = csv.DictWriter(stream, columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    summary = {
        "profile": PROFILE, "version": version, "status": status,
        "false_claim_rejected": negative_rejected, "smt_comparison": comparison,
        "smt_observations_sha256": smt_sha256,
        "source_sha256": sha256(source.encode()).hexdigest(),
        "stdout_sha256": sha256(output.encode()).hexdigest(),
        "checked": dict(Counter(record["relation"] for record in records))
        if status == "kernel-checked" else {},
    }
    (options.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return int(status != "kernel-checked" or (options.smt_observations and comparison != "match"))


if __name__ == "__main__":
    raise SystemExit(main())
