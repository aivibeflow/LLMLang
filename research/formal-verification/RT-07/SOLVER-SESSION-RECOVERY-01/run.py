#!/usr/bin/env python3
"""Compare blind solver continuation with recovery from a known typed context."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
HEADER = ("(set-logic QF_LIA)", "(set-option :produce-models true)",
          "(declare-const x Int)", "(assert (>= x 0))", "(assert (<= x 2))")
STATUS = {"sat", "unsat", "unknown"}
DOMAIN = frozenset(range(3))
PUSH, POP = ("push", 1), ("pop", 1)


@dataclass(frozen=True)
class Case:
    name: str
    prefix: tuple
    injection: str
    repair: tuple | None
    tail: tuple
    negative: bool = True


def require(value):
    return "assert_eq", value


CASES = (
    Case("valid_sat", (), "(assert (= x 1))", (require(1),), (), False),
    Case("valid_unsat", (), "(assert (= x 1))", (require(1),), (require(0),), False),
    Case("boolean_equality_extension", (), "(assert (= x true))", (require(1),), (require(0),)),
    Case("ill_typed_assertion", (), "(assert (= x \"invalid\"))", (require(1),), (require(0),)),
    Case("unresolved_symbol", (), "(assert (= undeclared 1))", (require(2),), (require(0),)),
    Case("unsupported_command", (), "(llmlang-unknown-command)",
         (require(1),), (require(0),)),
    Case("scope_underflow", (PUSH, require(0)), "(pop 2)", (POP,), (require(1),)),
    Case("model_after_unsat", (PUSH, require(0), require(1)), "(get-value (x))",
         (), (POP, require(1))),
    Case("no_approved_repair", (), "(assert (= absent 1))", None, (require(0),)),
)


def render(steps):
    lines = []
    for tag, value in steps:
        if tag == "assert_eq":
            lines.append(f"(assert (= x {value}))")
        else:
            lines.append(f"({tag} {value})")
    return lines


def finite_status(steps):
    stack = [DOMAIN]
    for tag, value in steps:
        if tag == "push":
            stack.append(stack[-1])
        elif tag == "pop":
            if len(stack) == 1:
                raise AssertionError("Typed replay cannot pop its base frame")
            stack.pop()
        elif tag == "assert_eq":
            stack[-1] &= {value}
        else:
            raise AssertionError(tag)
    return "sat" if stack[-1] else "unsat"


def digest(data):
    return sha256(data.encode("utf-8")).hexdigest()


def framed(segments):
    commands = [*HEADER]
    for name, lines in segments:
        commands += [f'(echo "begin_{name}")', *lines, f'(echo "end_{name}")']
    return "\n".join([*commands, "(exit)", ""])


def run_solver(backend, script):
    result = subprocess.run(backend, input=script, text=True, capture_output=True, timeout=20)
    frames = {}
    active = None
    for line in result.stdout.splitlines():
        marker = line.strip().strip('"')
        if marker.startswith("begin_"):
            active = marker.removeprefix("begin_")
            if active in frames:
                raise AssertionError(result.stdout)
            frames[active] = []
        elif marker.startswith("end_"):
            if active != marker.removeprefix("end_"):
                raise AssertionError(result.stdout)
            frames[active].append("frame-complete")
            active = None
        elif active is not None:
            frames[active].append(line)
        elif line.strip():
            raise AssertionError(result.stdout)
    return {"exit": result.returncode, "frames": frames, "stdout": result.stdout.splitlines(),
            "stderr": result.stderr.splitlines(), "smt_input_sha256": digest(script)}


def answer(result, phase):
    fields = result["frames"].get(phase)
    if fields and len(fields) == 2 and fields[-1] == "frame-complete" and fields[0] in STATUS:
        return fields[0]
    return None


def check_case(backend, case):
    script = framed((
        ("prefix", [*render(case.prefix), "(check-sat)"]),
        ("mutation", [case.injection]),
        ("tail", [*render(case.tail), "(check-sat)"]),
    ))
    original = run_solver(backend, script)
    prefix = answer(original, "prefix")
    if prefix != finite_status(case.prefix):
        raise AssertionError((case.name, original))
    blind = answer(original, "tail")
    mutation_frame = original["frames"].get("mutation")
    unexpected = mutation_frame != ["frame-complete"]
    allowed_input = tuple(render(case.repair or ())) == (case.injection,)
    if allowed_input == case.negative or (allowed_input and unexpected):
        raise AssertionError((backend, case.name, original))

    recovery = None
    recovery_status = None
    if case.repair is not None:
        restored = [*case.prefix, *case.repair, *case.tail]
        recovery = run_solver(backend, framed((("fresh", [*render(restored), "(check-sat)"]),)))
        recovery_status = answer(recovery, "fresh")
        if recovery_status != finite_status(restored) or recovery["exit"] != 0:
            raise AssertionError((case.name, recovery))

    quarantine = unexpected or not allowed_input
    admitted = "unresolved-context" if quarantine else blind
    if not case.negative and (admitted != recovery_status or original["exit"] != 0):
        raise AssertionError((case.name, original, recovery))
    return {
        "case": case.name,
        "typed_request_matches": allowed_input,
        "solver_reported_command_issue": unexpected,
        "quarantined": quarantine,
        "completed_prefix": prefix,
        "blind_tail": blind,
        "after_fail_closed": admitted,
        "fresh_tail": recovery_status,
        "original": original, "fresh": recovery,
    }


def equality_extension(backend):
    rows = {}
    for flag in ("false", "true"):
        samples = []
        for value in sorted(DOMAIN):
            script = framed((("extension", [
                *render((require(value),)), f"(assert (= x {flag}))", "(check-sat)",
            ]),))
            run = run_solver(backend, script)
            samples.append({"x": value, "answer": answer(run, "extension"), **run})
        rows[flag] = samples
    return rows


def run():
    backends = (("cvc5", "--incremental", "--lang=smt2"), ("z3", "-smt2", "-in"))
    result = {}
    for backend in backends:
        rows = [check_case(backend, case) for case in CASES]
        metrics = Counter()
        for row in rows:
            refused = row["quarantined"]
            blind, fresh = row["blind_tail"], row["fresh_tail"]
            metrics["completed_cases"] += 1
            metrics["quarantined"] += refused
            metrics["faults_without_solver_diagnostic"] += refused and not row["solver_reported_command_issue"]
            metrics["blind_answers_after_fault"] += refused and blind is not None
            metrics["wrong_blind_answers_against_approved_repair"] += (
                refused and blind is not None and fresh is not None and blind != fresh
            )
            metrics["fresh_repaired_contexts"] += refused and fresh is not None
        version = subprocess.run([backend[0], "--version"], capture_output=True, text=True,
                                 check=True, timeout=20).stdout.splitlines()[0]
        result[backend[0]] = {"version": version, "counts": metrics, "cases": rows,
                              "boolean_integer_equality_controls": equality_extension(backend)}
    if not sum(row["counts"]["wrong_blind_answers_against_approved_repair"] for row in result.values()):
        raise AssertionError("The fixture did not discriminate blind continuation")
    return {"schema": "llmlang-solver-session-recovery/1", "python": platform.python_version(),
            "runner_sha256": digest(Path(__file__).read_text()), "solvers": result}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
