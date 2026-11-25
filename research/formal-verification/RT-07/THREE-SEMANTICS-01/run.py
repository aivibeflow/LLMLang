"""Compare two operational interpreters, a state/trace denotation and a WP."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from itertools import product
from pathlib import Path

BASELINE = "8cf3ec125a67e0eb0293fd632b18f09a771aea0c"
ROOT = Path(__file__).resolve().parents[4]
PROTOTYPE = ROOT / "research/PROTOTYPES/RT-04-01"
sys.path.insert(0, str(PROTOTYPE))

from rt03_reference import evaluate
from rt03_smallstep import run_small_step

INITIAL = (0, 1)
EFFECTS = ("state.read", "state.write")
LEAVES = (("skip",), ("read",), ("write", 0), ("write", 1), ("fail",))
FORMERS = ("strict", "bind", "then", "else")
UNIT = ("ok", None)
FAILURE = ("error", "planned")


def ast_for(program):
    tag, *args = program
    if tag == "skip":
        return {"result_ok": {"literal": None}}
    if tag == "fail":
        return {"result_error": {"literal": "planned"}}
    if tag == "read":
        return {"perform": {"effect": "state.read", "operation": "read", "payload": {"key": "cell"}}}
    if tag == "write":
        return {"perform": {"effect": "state.write", "operation": "write",
                            "payload": {"key": "cell", "value": args[0]}}}
    left, right = map(ast_for, args)
    if tag in {"then", "else"}:
        return {"if": {"condition": {"literal": tag == "then"}, "then": left, "else": right}}
    return {"result_sequence" if tag == "bind" else "sequence": [left, right]}


def observed(trace):
    assert not trace.final_files and not trace.final_resources
    assert set(trace.final_state) == {"cell"}
    assert len(trace.result) == 1
    events = []
    for event in trace.events:
        operation = event["operation"]
        assert operation in {"read", "write"}
        assert event["effect"] == f"state.{operation}" and event["payload"]["key"] == "cell"
        if operation == "read":
            events.append(("read", event["outcome"]["ok"]))
        else:
            assert event["outcome"] == {"ok": None}
            events.append(("write", event["payload"]["value"]))
    return next(iter(trace.result.items())), trace.final_state["cell"], tuple(events)


def denote(program, initial):
    """Map an initial cell to the result, final cell, and newly emitted trace."""
    match program:
        case ("skip",):
            return UNIT, initial, ()
        case ("fail",):
            return FAILURE, initial, ()
        case ("read",):
            return ("ok", initial), initial, (("read", initial),)
        case ("write", value):
            return UNIT, value, (("write", value),)
        case ("then", left, _):
            return denote(left, initial)
        case ("else", _, right):
            return denote(right, initial)
        case (("strict" | "bind") as tag, left, right):
            result, state, prefix = denote(left, initial)
            if tag == "bind" and result[0] == "error":
                return result, state, prefix
            last, final, suffix = denote(right, state)
            return last, final, prefix + suffix
        case _:
            raise ValueError("outside the denotation fragment")


def wp(program, post):
    """Compose a postcondition backward without evaluating a denotation."""
    match program:
        case ("skip",):
            return lambda state, history: post(UNIT, state, history)
        case ("fail",):
            return lambda state, history: post(FAILURE, state, history)
        case ("read",):
            return lambda state, history: post(("ok", state), state, history + (("read", state),))
        case ("write", value):
            return lambda _, history: post(UNIT, value, history + (("write", value),))
        case ("then", left, _):
            return wp(left, post)
        case ("else", _, right):
            return wp(right, post)
        case ("strict", left, right):
            continuation = wp(right, post)
            return wp(left, lambda _, state, history: continuation(state, history))
        case ("bind", left, right):
            continuation = wp(right, post)
            return wp(left, lambda result, state, history: (
                post(result, state, history) if result[0] == "error" else continuation(state, history)
            ))
        case _:
            raise ValueError("outside the predicate transformer fragment")


def corpus():
    shallow = tuple(product(FORMERS, LEAVES, LEAVES))
    yield from LEAVES
    yield from shallow
    yield from product(FORMERS, LEAVES, shallow)
    yield from product(FORMERS, shallow, LEAVES)


def postconditions(initial, expected):
    return {
        "success": lambda result, _1, _2: result[0] == "ok",
        "unit": lambda result, _1, _2: result == UNIT,
        "initial_cell_preserved": lambda _, state, _history: initial == state,
        "read_first": lambda _1, _2, trace: bool(trace) and trace[0][0] == "read",
        "no_writes": lambda _1, _2, trace: all(operation != "write" for operation, _ in trace),
        "exact_observation": lambda result, state, trace: (result, state, trace) == expected,
        "wrong_final_cell": lambda result, state, trace: (result, 1 - state, trace) == expected,
    }


def compare(rows=None):
    digest = hashlib.sha256()
    programs = observations = predicates = 0
    for program in corpus():
        programs += 1
        expression = ast_for(program)
        for initial in INITIAL:
            observations += 1
            settings = {"declared_effects": EFFECTS, "initial_state": {"cell": initial}}
            recursive = observed(evaluate(expression, "D", **settings))
            machine = observed(run_small_step(expression, "D", **settings))
            derived = denote(program, initial)
            assert recursive == machine == derived, (program, initial, recursive, machine, derived)
            judgments = {}
            for name, predicate in postconditions(initial, recursive).items():
                predicates += 1
                judgment = wp(program, predicate)(initial, ())
                assert judgment == predicate(*derived), (program, initial, name)
                judgments[name] = judgment
            row = json.dumps([program, initial, recursive, judgments], separators=(",", ":")).encode() + b"\n"
            digest.update(row)
            if rows is not None:
                rows.write(row)
    return programs, observations, predicates, digest.hexdigest()


def controls():
    strict = ("strict", ("fail",), ("write", 1))
    stop = ("bind", ("fail",), ("write", 1))
    pure = ("skip",)
    restored = ("strict", ("write", 1), ("write", 0))
    normal, early = denote(strict, 0), denote(stop, 0)
    no_effect, restore = denote(pure, 0), denote(restored, 0)
    no_writes = postconditions(0, no_effect)["no_writes"]
    assert normal != early and normal[1] == 1 and early[1] == 0
    assert no_effect[:2] == restore[:2] and no_effect[2] != restore[2]
    assert wp(pure, no_writes)(0, ()) and not wp(restored, no_writes)(0, ())
    return {"strict_vs_short_circuit": [normal, early],
            "same_value_and_final_cell_different_trace": [no_effect, restore]}


def inputs():
    pins = {}
    for name in ("rt03_reference.py", "rt03_smallstep.py"):
        source = PROTOTYPE / name
        raw = subprocess.check_output(["git", "show", f"{BASELINE}:{source.relative_to(ROOT)}"], cwd=ROOT)
        assert source.read_bytes() == raw
        pins[name] = hashlib.sha256(raw).hexdigest()
    return pins


def main():
    pins = inputs()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, help="optional JSON Lines export")
    args = parser.parse_args()
    if args.rows is None:
        totals = compare()
    else:
        with args.rows.open("wb") as rows:
            totals = compare(rows)
    programs, observations, predicates, digest = totals
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prototype_sha256": pins, "initial_cells": INITIAL, "programs": programs,
        "observations_compared": observations, "predicate_checks": predicates,
        "comparison_rows_sha256": digest, "controls": controls(),
    }, indent=2))


if __name__ == "__main__":
    main()
