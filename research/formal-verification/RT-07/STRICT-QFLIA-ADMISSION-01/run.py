"""Compare strict source and typed JSON admission before the solver."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASELINE = "0ef40055665a73b82c6ac30c2ea88f71b8947331"
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.formal_core import Binary, Const, Emit, Program, Return, UnsupportedConstruct, Var
from src.qf_lia_ir import canonical_query_json
from src.qf_lia_profile import build_qf_lia_queries


def command(*args, cwd=None, data=None):
    return subprocess.run(args, cwd=cwd, input=data, capture_output=True,
                          check=True, text=True, timeout=90).stdout.strip()


def source_controls(cvc5):
    x, y = Var("x"), Var("y")
    square = Binary("mul", x, x)
    okay = {
        "identity": (x, {"x": "Int"}, "sat"),
        "constant-return": (Const(0), {"x": "Int"}, "unsat"),
        "negative-literal-multiplier": (Binary("mul", Const(-2), x), {"x": "Int"}, "sat"),
        "bool-identity": (x, {"x": "Bool"}, "sat"),
    }
    bad = {
        "unsupported-string-declaration": (Const(0), {"x": "String"}),
        "unsupported-string-literal": (Const("value"), {"x": "Int"}),
        "variable-times-variable": (Binary("mul", x, y), {"x": "Int", "y": "Int"}),
        "arithmetic-constant-expression-multiplier": (Binary("mul", x, Binary("add", Const(1), Const(1))), {"x": "Int"}),
        "syntactically-nonlinear-cancellation": (Binary("sub", square, square), {"x": "Int"}),
        "division": (Binary("div", x, Const(2)), {"x": "Int"}),
        "boolean-in-arithmetic": (Binary("add", x, Const(True)), {"x": "Int"}),
    }
    observations, wire_controls = [], []
    for label, (expr, sorts, expected) in okay.items():
        result = build_qf_lia_queries(Program((Return(expr),)), sorts)
        factor, = result.factors
        assert factor.smt2.startswith("(set-logic QF_LIA)")
        status = command(cvc5, "--lang=smt2", data=factor.smt2)
        assert status == expected
        observations.append({"label": label, "emitted_query": True, "solver": status,
                             "query_sha256": sha256(factor.smt2.encode()).hexdigest()})
        wire_controls.append((label, json.loads(canonical_query_json(factor.query_ir)), True))

    negative_programs = [(label, Program((Return(expr),)), sorts) for label, (expr, sorts) in bad.items()]
    negative_programs.append(("emitted-effect", Program((Emit("event", x), Return(x))), {"x": "Int"}))
    for label, program, sorts in negative_programs:
        try:
            build_qf_lia_queries(program, sorts)
        except UnsupportedConstruct as error:
            observations.append({"label": label, "emitted_query": False, "reason": str(error)})
        else:
            raise AssertionError(label)
    return observations, wire_controls


def negative_wires(valid):
    def term(operator, sort, *children, atom=None):
        return {"op": operator, "sort": sort, "args": list(children), "atom": atom}

    x = term("symbol", "Int", atom=valid["factor_left"])
    y = term("symbol", "Int", atom=valid["factor_right"])
    num = term("int", "Int", atom=2)
    nonlinear = term("mul", "Int", x, y)
    edits = {
        "wire-string-sort": {"declarations": [*valid["declarations"], {"name": "s", "sort": "String"}]},
        "wire-nonlinear": {"observations_differ": term("eq", "Bool", nonlinear, x)},
        "wire-canceling-nonlinearity": {"observations_differ": term("eq", "Bool", nonlinear, nonlinear)},
        "wire-nonliteral-multiplier": {"observations_differ": term("eq", "Bool", term("mul", "Int", x, term("add", "Int", num, num)), y)},
        "wire-division": {"observations_differ": term("eq", "Bool", term("div", "Int", x, num), y)},
        "wire-mixed-equality": {"observations_differ": term("eq", "Bool", x, term("bool", "Bool", atom=True))},
        "wire-int-with-string-atom": {"observations_differ": term("eq", "Bool", x, term("int", "Int", atom="2"))},
        "wire-hidden-operator-atom": {"observations_differ": term("eq", "Bool", term("add", "Int", x, num, atom=0), y)},
        "wire-unknown-version": {"schema": "llmlang.qf_lia.relational-query/3"},
        "wire-unknown-field": {"extra": "synthetic"},
    }
    return [(name, deepcopy(valid) | edit, False) for name, edit in edits.items()]


def run(binding, cvc5):
    assert command("git", "-C", binding / ".lake/packages/Cpc", "rev-parse", "HEAD") == "cf18742973861b3718d04c5f25775448098ff474"
    source_results, controls = source_controls(cvc5)
    controls.extend(negative_wires(controls[0][1]))
    with TemporaryDirectory(prefix="llmlang-qflia-wire-") as scratch:
        path = Path(scratch) / "controls.jsonl"
        path.write_text("".join(json.dumps({"label": name, "wire": json.dumps(wire, sort_keys=True)}) + "\n"
                                for name, wire, _ in controls), encoding="utf-8")
        results = [json.loads(line) for line in command(
            "lake", "env", "lean", "--run", HERE / "Decode.lean", path, cwd=binding).splitlines()]
        assert [(r["label"], r["accepted"]) for r in results] == [(name, expected) for name, _, expected in controls]
        wire_digest = sha256(path.read_bytes()).hexdigest()
    return {
        "schema": "rt07-strict-qflia-admission-comparison-v1", "baseline": BASELINE,
        "python": platform.python_version(), "wire_fixture_sha256": wire_digest,
        "source_controls": source_results, "wire_controls": results,
        "source_admission_counts": dict(Counter("emitted" if r["emitted_query"] else "rejected" for r in source_results)),
        "wire_admission_counts": dict(Counter("admitted" if r["accepted"] else "rejected" for r in results)),
        "lean": command("lake", "env", "lean", "--version", cwd=binding),
        "cvc5": command(cvc5, "--version").splitlines()[0],
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in (
            HERE / "Decode.lean", HERE / "run.py", PROTOTYPE / "src/qf_lia_profile.py", PROTOTYPE / "src/qf_lia_ir.py",
            binding / "LLMLangLogosBinding.lean")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--cvc5", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.binding.resolve(), args.cvc5), indent=2, sort_keys=True))
