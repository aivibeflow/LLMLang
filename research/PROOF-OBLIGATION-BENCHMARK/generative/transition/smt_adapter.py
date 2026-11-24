"""Experimental cvc5 adapter for bounded transition state observations."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from machine import Unsupported, execute_validated, validate
from oracle import expected
from templates import FAMILIES, VARIANTS, model, scenarios

PROFILE = {
    "id": "transition-state-smt-v1",
    "solver_version": "cvc5 1.4.2 [git 282d5e0 on branch HEAD]",
    "logic": "QF_LIA",
    "timeout_seconds": 30,
    "trace_max_actions": 8,
    "obligation": "state at each action boundary for fixed initial registers and trace",
    "unsupported": ["effects", "invariants", "noninterference", "symbolic initial states",
                    "unbounded traces", "proof certificates"],
}
OPERATOR = {"add": "+", "sub": "-", "eq": "=", "le": "<=",
            "and": "and", "or": "or", "not": "not"}


def integer(value):
    return str(value) if value >= 0 else f"(- {-value})"


def expression(expr, registers):
    op, *operands = expr
    if op == "int":
        return integer(operands[0])
    if op == "reg":
        return registers[operands[0]]
    args = " ".join(expression(operand, registers) for operand in operands)
    return f"({OPERATOR[op]} {args})"


class StateCompiler:
    def __init__(self):
        self.definitions = []

    def bind(self, term):
        name = f"r{len(self.definitions)}"
        self.definitions.append(f"(define-fun {name} () Int {term})")
        return name

    def block(self, statements, registers):
        registers = registers.copy()
        for op, *args in statements:
            if op == "set":
                name, expr = args
                registers[name] = self.bind(expression(expr, registers))
            elif op == "if":
                guard, yes, no = args
                condition = expression(guard, registers)
                true_regs = self.block(yes, registers)
                false_regs = self.block(no, registers)
                for name in registers:
                    if true_regs[name] != false_regs[name]:
                        term = f"(ite {condition} {true_regs[name]} {false_regs[name]})"
                        registers[name] = self.bind(term)
            # The validated emit statement has no register side effects.
        return registers


def state_query(machine, initial, trace, gold, *, final_only_control=False):
    validate(machine)
    if (not isinstance(initial, dict) or set(initial) != set(machine["initial"])
            or any(type(v) is not int or abs(v) > 10**9 for v in initial.values())):
        raise Unsupported("initial override")
    if (not isinstance(trace, (list, tuple)) or len(trace) > PROFILE["trace_max_actions"]
            or any(not isinstance(action, str) or action not in machine["actions"]
                   for action in trace)):
        raise Unsupported("trace outside declared action alphabet/bound")
    if (len(trace) != len(gold)
            or any(not isinstance(state, dict) or set(state) != set(initial)
                   or any(type(v) is not int for v in state.values()) for state in gold)):
        raise Unsupported("invalid state observation")

    compiler = StateCompiler()
    registers = {name: compiler.bind(integer(value)) for name, value in sorted(initial.items())}
    different = []
    for step, (action, state) in enumerate(zip(trace, gold), start=1):
        registers = compiler.block(machine["actions"][action], registers)
        if not final_only_control or step == len(trace):
            different.extend(f"(distinct {registers[name]} {integer(state[name])})"
                             for name in sorted(state))
    mismatch = f"(or false {' '.join(different)})" if different else "false"
    return "\n".join(["(push 1)", *compiler.definitions, f"(assert {mismatch})",
                      "(check-sat)", "(pop 1)"])


def solver_responses(binary, source, count):
    try:
        process = subprocess.run(
            [binary, "--lang=smt2", "--incremental"], input=source,
            capture_output=True, text=True, timeout=PROFILE["timeout_seconds"], check=False,
        )
    except subprocess.TimeoutExpired as error:
        return ("timeout", (error.stdout or b"").decode(errors="replace"),
                (error.stderr or b"").decode(errors="replace"))
    except OSError as error:
        return "unavailable", "", str(error)
    statuses = process.stdout.split()
    if (process.returncode or process.stderr or len(statuses) != count
            or any(status not in {"sat", "unsat", "unknown"} for status in statuses)):
        return "invalid-response", process.stdout, process.stderr
    return "ok", process.stdout, ""


def outcome(answer, differs):
    if answer == "unknown":
        return "abstain"
    if answer == "sat" and differs:
        return "replayed-counterexample"
    if answer == "unsat" and not differs:
        return "bounded-agreement"
    return "translation-or-solver-conflict"


def control():
    machine = {
        "initial": {"x": 0}, "events": [],
        "actions": {"change": [["set", "x", ["int", -1]]],
                    "restore": [["set", "x", ["int", 0]]]},
    }
    return machine, machine["initial"], ["change", "restore"], [{"x": 0}, {"x": 0}]


def experiment():
    queries = []
    records = []

    def add(machine, initial, trace, gold, metadata, *, weakened=False):
        query = state_query(machine, initial, trace, gold, final_only_control=weakened)
        replay = [step["state"] for step in execute_validated(machine, trace, initial)]
        queries.append(query)
        records.append({
            **metadata, "initial": initial, "trace": trace, "expected": gold,
            "replay": replay, "query_sha256": sha256(query.encode()).hexdigest(),
            "model_sha256": sha256(json.dumps(machine, sort_keys=True).encode()).hexdigest(),
        })

    for parameter, family in enumerate(FAMILIES, start=2):
        for variant in VARIANTS:
            machine = model(family, parameter, variant)
            for override, trace in scenarios(family, parameter):
                gold = [step["state"] for step in expected(family, parameter, override, trace)]
                add(machine, machine["initial"] | override, trace, gold,
                    {"family": family, "parameter": parameter, "variant": variant})
    add(*control(), {"control": "all-boundaries"})
    add(*control(), {"control": "final-only"}, weakened=True)
    return f"(set-logic {PROFILE['logic']})\n" + "\n".join(queries) + "\n(exit)\n", records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    source, records = experiment()
    options.output.joinpath("queries.smt2").write_text(source)
    version = ""
    try:
        process = subprocess.run([options.cvc5, "--version"], text=True,
                                 capture_output=True, timeout=PROFILE["timeout_seconds"], check=True)
        version = process.stdout.splitlines()[0]
    except (OSError, IndexError, subprocess.SubprocessError) as error:
        status, stdout, stderr = "version-unavailable", "", str(error)
    else:
        if version == PROFILE["solver_version"]:
            status, stdout, stderr = solver_responses(options.cvc5, source, len(records))
        else:
            status, stdout, stderr = "unsupported-version", "", ""
    options.output.joinpath("stdout.txt").write_text(stdout)
    options.output.joinpath("stderr.txt").write_text(stderr)

    answers = stdout.split() if status == "ok" else [None] * len(records)
    counts = Counter()
    for record, answer in zip(records, answers):
        differs = record["expected"] != record["replay"]
        record["solver"] = answer
        record["outcome"] = "abstain" if answer is None else outcome(answer, differs)
        if "control" not in record:
            counts[record["outcome"]] += 1
    options.output.joinpath("observations.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )
    summary = {
        "profile": PROFILE, "solver_version": version, "batch_status": status,
        "query_sha256": sha256(source.encode()).hexdigest(),
        "stdout_sha256": sha256(stdout.encode()).hexdigest(), "counts": dict(counts),
        "controls": [{field: record[field] for field in ("control", "solver", "outcome")}
                     for record in records if "control" in record],
    }
    options.output.joinpath("summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return int(status != "ok" or counts["translation-or-solver-conflict"] > 0
               or counts["abstain"] > 0 or answers[-2:] != ["sat", "unsat"])


if __name__ == "__main__":
    raise SystemExit(main())
