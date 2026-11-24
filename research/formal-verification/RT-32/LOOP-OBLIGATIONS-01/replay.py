"""Generate and check obligations for the restricted countdown loop profile."""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
TEST_POINTS = ((0, 0), (1, 1), (2, 2), (5, 5), (9, 9), (32, 32), (2, 0), (3, 2))
OPS = {"emit_remaining": ".emitRemaining", "emit_accumulator": ".emitAccumulator",
       "add": ".add", "subtract": ".subtract"}
FIXED = {"schema": "llmlang-typed-countdown-v1", "input_type": "Nat", "result_type": "Nat"}
CONTRACT = {"invariant": "remaining-and-accumulator-and-trace", "measure": "remaining",
            "trace": "remaining-then-accumulator"}


def nat(value):
    if type(value) is not int or not 0 <= value <= 32:
        raise ValueError("Fixture numeral outside admitted small-Nat profile")
    return value


def generate(template, fixture):
    if not isinstance(fixture, dict) or set(fixture) != {*FIXED, "initial_accumulator", "stop_at", "body", "contract"}:
        raise ValueError("Unknown or missing program fields")
    if any(fixture[field] != expected for field, expected in FIXED.items()):
        raise ValueError("Unknown program profile")
    contract = fixture["contract"]
    if (not isinstance(contract, dict) or set(contract) != {*CONTRACT, "stride"}
            or any(contract[field] != expected for field, expected in CONTRACT.items())):
        raise ValueError("Unsupported contract or missing obligation")
    body = fixture["body"]
    if (not isinstance(body, list)
            or any(not isinstance(action, dict) or not isinstance(action.get("op"), str) for action in body)
            or sorted(action["op"] for action in body) != sorted(OPS)):
        raise ValueError("The fixture needs each admitted operation once")
    actions = []
    decrease = None
    for action in body:
        kind = action["op"]
        with_amount = kind in {"add", "subtract"}
        fields = {"op", "amount"} if with_amount else {"op"}
        if set(action) != fields:
            raise ValueError("Unexpected body fields")
        amount = nat(action["amount"]) if with_amount else None
        actions.append(f"{OPS[kind]} {amount}" if with_amount else OPS[kind])
        if kind == "subtract":
            decrease = amount

    evaluations = [f'#eval IO.println ("OBS|{n}|{fuel}|" ++ observation {n} {fuel})'
                   for n, fuel in TEST_POINTS]
    slots = {
        "INITIAL": nat(fixture["initial_accumulator"]),
        "STOP": nat(fixture["stop_at"]),
        "ACTIONS": ", ".join(actions),
        "STRIDE": nat(contract["stride"]),
        "DECREASE_IN_BODY": decrease,
        "EVALUATIONS": "\n".join(evaluations),
    }
    for name, value in slots.items():
        template = template.replace(f"@{name}@", str(value))
    return template


def execute_source(fixture, remaining, fuel):
    accumulator = fixture["initial_accumulator"]
    events = []
    used = 0
    while remaining > fixture["stop_at"]:
        if used == fuel:
            return "exhausted"
        used += 1
        for action in fixture["body"]:
            match action["op"]:
                case "subtract":
                    remaining = max(0, remaining - action["amount"])
                case "add":
                    accumulator += action["amount"]
                case "emit_remaining":
                    events.append(f"r{remaining}")
                case "emit_accumulator":
                    events.append(f"a{accumulator}")
    return ",".join([str(accumulator), *events])


def check_version():
    result = subprocess.check_output(["lean", "--version"], text=True).strip()
    if "version 4.36.0" not in result:
        raise ValueError(result)
    return result


def run_lean(path, env):
    return subprocess.run(["lean", "--json", path.name], cwd=path.parent, env=env,
                          text=True, capture_output=True, timeout=60)


def diagnostics(run):
    return [json.loads(line) for line in run.stdout.splitlines()]


def positive(work, name, fixture, template, env):
    file = work / f"{name}.lean"
    file.write_text(generate(template, fixture), encoding="utf-8")
    result = run_lean(file, env)
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    logs = [message["data"].strip() for message in diagnostics(result)]
    observations = [match.split("|", maxsplit=3)[-1] for match in logs if match.startswith("OBS|")]
    expected = [execute_source(fixture, n, fuel) for n, fuel in TEST_POINTS]
    if observations != expected:
        raise ValueError(f"Concrete Lean/Python mismatch: {observations!r} != {expected!r}")
    axiom_line, = [line for line in logs if "depends on axioms" in line or "does not depend" in line]
    axiom_match = re.search(r"\[([^\]]*)\]", axiom_line)
    axioms = axiom_match[1].split(", ") if axiom_match else []
    if set(axioms) - {"propext", "Quot.sound", "Classical.choice"}:
        raise ValueError(axiom_line)
    return {"generated_sha256": sha256(file.read_bytes()).hexdigest(),
            "evaluations": observations, "axioms": axioms}


def reject(work, name, fixture, template, expected_theorem, env):
    file = work / f"{name}.lean"
    generated = generate(template, fixture)
    file.write_text(generated, encoding="utf-8")
    result = run_lean(file, env)
    if not result.returncode:
        raise ValueError(f"{name} passed")
    theorem_lines = [(i, match.group(1)) for i, line in enumerate(generated.splitlines(), 1)
                     if (match := re.match(r"^theorem (\w+)", line))]
    failed = set()
    for message in diagnostics(result):
        if message["severity"] == "error":
            line = message["pos"]["line"]
            failed.add(next((theorem for position, theorem in reversed(theorem_lines)
                             if position <= line), "before-theorems"))
    if expected_theorem not in failed:
        raise ValueError(result.stdout + result.stderr)
    return {"failed_obligations": sorted(failed), "expected_failure": expected_theorem}


def main():
    version = check_version()
    fixture_path = HERE / "fixtures.json"
    template = (HERE / "Program.lean.in").read_text(encoding="utf-8")
    fixture = json.loads(fixture_path.read_text())
    with tempfile.TemporaryDirectory(prefix="llmlang-loop-") as directory:
        work = Path(directory)
        core = work / "LoopCore.lean"
        core.write_bytes((HERE / core.name).read_bytes())
        subprocess.run(["lean", "-o", "LoopCore.olean", core.name], cwd=work, check=True, timeout=60)
        env = {**os.environ, "LEAN_PATH": str(work)}
        rewritten = deepcopy(fixture)
        rewritten["body"][1]["amount"] = 5
        rewritten["contract"]["stride"] = 5
        base = positive(work, "Base", fixture, template, env)
        variant = positive(work, "StrideFive", rewritten, template, env)
        controls = {}
        for name, change, theorem in (
            ("WrongInit", lambda x: x.update(initial_accumulator=1), "vcInit"),
            ("WrongStep", lambda x: x["body"][1].update(amount=3), "vcPreserve"),
            ("ZeroDecrease", lambda x: x["body"][3].update(amount=0), "vcDecrease"),
            ("EarlyExit", lambda x: x.update(stop_at=1), "vcExit"),
            ("TraceOrder", lambda x: x.update(body=[x["body"][i] for i in (1, 2, 0, 3)]), "vcPreserve"),
        ):
            mutant = deepcopy(fixture)
            change(mutant)
            failure = reject(work, name, mutant, template, theorem, env)
            observed = execute_source(mutant, 1, 2)
            expected = execute_source(fixture, 1, 2)
            if observed == expected:
                raise ValueError(f"Missing concrete witness for {name}")
            if name == "TraceOrder":
                left, *left_events = observed.split(",")
                right, *right_events = expected.split(",")
                if left != right or sorted(left_events) != sorted(right_events):
                    raise ValueError("Trace-order control must preserve the value and event multiset")
            controls[name] = {**failure, "witness": {"input": 1, "fuel": 2,
                                                    "baseline": expected, "mutant": observed}}
        missing = deepcopy(fixture)
        del missing["contract"]["invariant"]
        try:
            generate(template, missing)
        except ValueError:
            controls["MissingInvariant"] = "rejected-before-generation"
        else:
            raise ValueError("Missing invariant admitted")
    paths = (fixture_path, HERE / "Program.lean.in", HERE / "LoopCore.lean", Path(__file__))
    digests = {path.name: sha256(path.read_bytes()).hexdigest() for path in paths}
    evidence = {"lean": version, "inputs_sha256": digests, "test_points": TEST_POINTS,
                "programs": [base, variant], "controls": controls}
    print(json.dumps(evidence, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
