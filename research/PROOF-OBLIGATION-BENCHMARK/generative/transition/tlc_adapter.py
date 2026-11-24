"""Compare finite transition state classifications using TLA+ and TLC."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from machine import execute_validated, validate
from oracle import expected
from templates import FAMILIES, VARIANTS, model, scenarios

PROFILE = {
    "id": "transition-state-tlc-v1",
    "release": "tlaplus/tlaplus v1.8.0",
    "jar_sha256": "fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713",
    "timeout_seconds": 30,
    "obligation": "state at each action boundary for fixed initial registers and trace",
    "unsupported": ["effects", "invariants beyond state equality", "noninterference",
                    "symbolic inputs", "unbounded traces", "liveness", "regular-infinite domains"],
}
CONFIG = "INIT Init\nNEXT Next\nINVARIANT Classification\n"
OPERATORS = {"add": "+", "sub": "-", "eq": "=", "le": "<=", "and": "/\\", "or": "\\/"}


def term(value):
    if isinstance(value, (tuple, list)):
        return "<<" + ", ".join(term(item) for item in value) + ">>"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    return str(value) if value >= 0 else f"({value})"


def expression(expr, indexes, state):
    op, *args = expr
    if op == "int":
        return term(args[0])
    if op == "reg":
        return f"{state}[{indexes[args[0]]}]"
    operands = [expression(arg, indexes, state) for arg in args]
    if op == "not":
        return f"(~{operands[0]})"
    return f"({operands[0]} {OPERATORS[op]} {operands[1]})"


def block(code, indexes, state):
    bindings = []
    for op, *args in code:
        if op == "emit":
            continue
        if op == "set":
            name, value = args
            term_value = f"[{state} EXCEPT ![{indexes[name]}] = {expression(value, indexes, state)}]"
        else:
            guard, yes, no = args
            term_value = (f"IF {expression(guard, indexes, state)} "
                          f"THEN {block(yes, indexes, state)} ELSE {block(no, indexes, state)}")
        state = f"{state}s"
        bindings.append(f"{state} == {term_value}")
    return f"(LET {' '.join(bindings)} IN {state})" if bindings else state


def vector(state, indexes):
    return [state[name] for name in indexes]


def case(machine, initial, trace, gold, indexes, actions, metadata, *, final_only=False):
    replay = [step["state"] for step in execute_validated(machine, trace, initial)]
    proposed = [False]
    for step, (actual, target) in enumerate(zip(replay, gold), start=1):
        observed = step == len(trace) or not final_only
        proposed.append(proposed[-1] or (observed and actual != target))
    return {
        **metadata, "initial": initial, "expected": gold, "trace": trace, "replay": replay,
        "model_sha256": sha256(json.dumps(machine, sort_keys=True).encode()).hexdigest(),
        "initial_vector": vector(initial, indexes), "actions": [actions[name] for name in trace],
        "oracle_vectors": [vector(state, indexes) for state in gold],
        "replay_vectors": [vector(initial, indexes), *(vector(state, indexes) for state in replay)],
        "proposed": proposed, "final_only": final_only,
    }


def experiment():
    operators = []
    records = []
    for parameter, family in enumerate(FAMILIES, start=2):
        for variant in VARIANTS:
            machine = model(family, parameter, variant)
            validate(machine)
            indexes = {name: i for i, name in enumerate(sorted(machine["initial"]), start=1)}
            actions = {}
            for name, code in sorted(machine["actions"].items()):
                operators.append(block(code, indexes, "s"))
                actions[name] = len(operators)
            for override, trace in scenarios(family, parameter):
                initial = machine["initial"] | override
                gold = [step["state"] for step in expected(family, parameter, override, trace)]
                records.append(case(machine, initial, trace, gold, indexes, actions,
                                    {"family": family, "variant": variant, "parameter": parameter}))
    return operators, records


def control(final_only):
    machine = {
        "initial": {"x": 0}, "events": [],
        "actions": {"change": [["set", "x", ["int", -1]]],
                    "restore": [["set", "x", ["int", 0]]]},
    }
    validate(machine)
    indexes = {"x": 1}
    operators = [block(code, indexes, "s") for code in machine["actions"].values()]
    record = case(machine, machine["initial"], ["change", "restore"], [{"x": 0}, {"x": 0}],
                  indexes, {"change": 1, "restore": 2}, {"control": "transient-mismatch"},
                  final_only=final_only)
    return machine, operators, record


def source(module, operators, records):
    dispatch = "\n    [] ".join(f"op = {i} -> {expr}" for i, expr in enumerate(operators, start=1))
    tables = []
    for name, key in [("InitialVector", "initial_vector"), ("Actions", "actions"),
                      ("Oracle", "oracle_vectors"), ("Replay", "replay_vectors"),
                      ("Proposed", "proposed"),
                      ("FinalOnly", "final_only")]:
        rows = ",\n    ".join(term(record[key]) for record in records)
        tables.append(f"{name} == <<\n    {rows}\n>>\n")
    return f"---- MODULE {module} ----\nEXTENDS Integers, Sequences\n\n" + "\n".join(tables) + rf"""
Apply(op, s) == CASE {dispatch}

VARIABLES caseId, position, registers, mismatch
Vars == <<caseId, position, registers, mismatch>>

Init ==
    /\ caseId \in 1..{len(records)}
    /\ position = 0
    /\ registers = InitialVector[caseId]
    /\ mismatch = FALSE

Next ==
    IF position = Len(Actions[caseId])
    THEN UNCHANGED Vars
    ELSE LET target == position + 1
             updated == Apply(Actions[caseId][target], registers)
             observe == ~FinalOnly[caseId] \/ target = Len(Actions[caseId])
         IN /\ UNCHANGED caseId
            /\ position' = target
            /\ registers' = updated
            /\ mismatch' = (mismatch \/ (observe /\ updated # Oracle[caseId][target]))

Classification ==
    /\ registers = Replay[caseId][position + 1]
    /\ mismatch = Proposed[caseId][position + 1]
====
"""


def run_tlc(java, jar, directory, module, text):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / f"{module}.tla").write_text(text)
    (directory / f"{module}.cfg").write_text(CONFIG)
    args = [java, "-Xmx512m", "-cp", str(jar), "tlc2.TLC", "-workers", "1",
            "-seed", "1", "-fp", "0", "-noGenerateSpecTE", "-dumpTrace", "json", "trace.json", module]
    try:
        result = subprocess.run(args, text=True, cwd=directory, capture_output=True,
                                timeout=PROFILE["timeout_seconds"], check=False)
    except subprocess.TimeoutExpired as error:
        (directory / "stdout.txt").write_bytes(error.stdout or b"")
        (directory / "stderr.txt").write_bytes(error.stderr or b"")
        raise
    (directory / "stdout.txt").write_text(result.stdout)
    (directory / "stderr.txt").write_text(result.stderr)
    return result


def completed(result, distinct_count):
    match = re.search(r"^\d+ states generated, (\d+) distinct states found, (\d+) states left on queue\.",
                      result.stdout, re.M)
    return (result.returncode == 0 and not result.stderr and match is not None
            and "Model checking completed. No error has been found." in result.stdout
            and tuple(map(int, match.groups())) == (distinct_count, 0))


def replay_control(machine, record, result, trace_path):
    if (result.returncode != 12 or result.stderr
            or "Error: Invariant Classification is violated." not in result.stdout):
        return False
    observations = json.loads(trace_path.read_text())["counterexample"]["state"]
    if len(observations) != 2 or [row[0] for row in observations] != [1, 2]:
        return False
    states = [row[1] for row in observations]
    first = execute_validated(machine, record["trace"][:1], record["initial"])[0]["state"]
    return states == [
        {"caseId": 1, "position": 0, "registers": record["initial_vector"], "mismatch": False},
        {"caseId": 1, "position": 1, "registers": [first["x"]], "mismatch": True},
    ] and first != record["expected"][0]


def backend_match(raw, records, backend):
    observations = [json.loads(line) for line in raw.splitlines()]
    if backend == "smt":
        controls = [(row.get("control"), row.get("solver"), row.get("outcome"))
                    for row in observations[-2:]]
        if controls != [
            ("all-boundaries", "sat", "replayed-counterexample"),
            ("final-only", "unsat", "translation-or-solver-conflict"),
        ]:
            return False
        observations = observations[:-2]
    if len(records) != len(observations):
        return False
    fields = ("family", "variant", "parameter", "initial", "trace", "expected", "replay", "model_sha256")
    for case_data, observation in zip(records, observations):
        if any(case_data[field] != observation[field] for field in fields):
            return False
        different = case_data["proposed"][-1]
        if backend == "smt":
            answer = ("sat", "replayed-counterexample") if different else ("unsat", "bounded-agreement")
            if (observation["solver"], observation["outcome"]) != answer:
                return False
        elif (observation["status"] != "kernel-checked"
              or observation["relation"] != ("different" if different else "equal")):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--smt-observations", type=Path)
    parser.add_argument("--lean-observations", type=Path)
    args = parser.parse_args()
    jar = args.jar.resolve()
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(f"cannot create a fresh output directory: {exc}")
    checks = {}
    sources = {}
    comparisons = {}
    error = None
    operators, records = experiment()
    states = sum(len(record["trace"]) + 1 for record in records)
    try:
        if sha256(jar.read_bytes()).hexdigest() != PROFILE["jar_sha256"]:
            raise ValueError("unsupported TLC JAR digest")
        text = source("Cases", operators, records)
        sources["Cases"] = sha256(text.encode()).hexdigest()
        cases = run_tlc("java", jar, args.output / "cases", "Cases", text)
        checks["complete_prefix_graph"] = bool(completed(cases, states))

        machine, ops, weakened = control(final_only=True)
        text = source("FinalOnly", ops, [weakened])
        sources["FinalOnly"] = sha256(text.encode()).hexdigest()
        final = run_tlc("java", jar, args.output / "final-only", "FinalOnly", text)
        checks["weakened_observation_agrees"] = bool(completed(final, 3))

        wrong = {**weakened, "final_only": False}
        text = source("FalseClaim", ops, [wrong])
        sources["FalseClaim"] = sha256(text.encode()).hexdigest()
        location = args.output / "false-claim"
        fail = run_tlc("java", jar, location, "FalseClaim", text)
        checks["incorrect_full_claim_replayed"] = replay_control(
            machine, wrong, fail, location / "trace.json",
        )
        for backend, path in [("smt", args.smt_observations), ("lean", args.lean_observations)]:
            if path is not None:
                raw = path.read_bytes()
                comparisons[backend] = {
                    "matches": backend_match(raw, records, backend),
                    "observations_sha256": sha256(raw).hexdigest(),
                }
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        error = str(exc)

    accepted = error is None and len(checks) == 3 and all(checks.values())
    with (args.output / "outcomes.csv").open("w", newline="") as stream:
        columns = ["case_id", "family", "variant", "parameter", "classification"]
        writer = csv.DictWriter(stream, columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for index, record in enumerate(records, start=1):
            classification = ("different" if record["proposed"][-1] else "equal") if accepted else "abstain"
            writer.writerow({**record, "case_id": index, "classification": classification})

    summary = {
        "profile": PROFILE, "status": "bounded-comparison" if accepted else "abstain",
        "error": error, "cases": len(records), "expected_distinct_prefix_states": states,
        "observations": dict(Counter("different" if row["proposed"][-1] else "equal"
                                     for row in records)) if accepted else {},
        "source_sha256": sources, "checks": checks, "comparisons": comparisons,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return int(not accepted or any(not row["matches"] for row in comparisons.values()))


if __name__ == "__main__":
    raise SystemExit(main())
