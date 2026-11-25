#!/usr/bin/env python3
"""Compare the executable wire entry with the two operational semantics."""

from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys

import reference

HERE = Path(__file__).resolve().parent


def raw(initial, program):
    return json.dumps([reference.SCHEMA, initial, program], separators=(",", ":")).encode("ascii")


def command(data):
    result = subprocess.run(
        [sys.executable, "-B", HERE / "reference.py"], input=data, check=False,
        capture_output=True, timeout=30,
    )
    if result.stderr:
        raise RuntimeError(result.stderr.decode())
    return result.returncode, json.loads(result.stdout)


def validate():
    model = reference.model
    comparison = sha256()
    count = 0
    for program in model.corpus():
        expression = model.ast_for(program)
        for initial in model.INITIAL:
            settings = {"declared_effects": model.EFFECTS, "initial_state": {"cell": initial}}
            recursive = model.observed(model.evaluate(expression, "D", **settings))
            machine = model.observed(model.run_small_step(expression, "D", **settings))
            wire = raw(initial, program)
            report = reference.evaluate_request(wire)
            actual = (next(iter(report["result"].items())), report["final_cell"], report["trace"])
            if actual != recursive or actual != machine:
                raise AssertionError(f"Reference observation diverges for {program}")
            comparison.update(wire + b"\0" + json.dumps(report, separators=(",", ":")).encode() + b"\n")
            count += 1

    entries = (
        ("normal sequence", raw(0, ["strict", ["fail"], ["write", 1]]),
         0, {"result": {"ok": None}, "final_cell": 1, "trace": [["write", 1]]}),
        ("Result short circuit", raw(0, ["bind", ["fail"], ["write", 1]]),
         0, {"result": {"error": "planned"}, "final_cell": 0, "trace": []}),
        ("restore still emits", raw(0, ["strict", ["write", 1], ["write", 0]]),
         0, {"result": {"ok": None}, "final_cell": 0, "trace": [["write", 1], ["write", 0]]}),
    )
    malformed = (
        ("malformed", b"{", "malformed-json"),
        ("invalid UTF-8", b"\xff", "malformed-json"),
        ("wrong version", b'["unknown",0,["read"]]', "request-schema"),
        ("Boolean initial", raw(True, ["read"]), "initial-cell"),
        ("initial value out of the domain", raw(2, ["read"]), "initial-cell"),
        ("Boolean write", raw(0, ["write", True]), "unsupported-expression"),
        ("unsupported operator", raw(0, ["loop"]), "unsupported-expression"),
        ("missing right child", raw(0, ["bind", ["skip"]]), "unsupported-expression"),
        ("unsupported expression shape", raw(0, {"operation": "read"}), "expression-shape"),
        ("invalid lazy branch", raw(0, ["then", ["skip"], ["open-file"]]), "unsupported-expression"),
        ("excess bytes", b" " * (reference.MAX_BYTES + 1), "input-size"),
    )
    nested = ["skip"]
    for _ in range(reference.MAX_DEPTH + 1):
        nested = ["strict", ["skip"], nested]
    malformed += (("excess depth", raw(0, nested), "expression-depth"),)
    controls = [*entries, *((label, bytes_, 2, {"error": error})
                           for label, bytes_, error in malformed)]
    decisions = []
    for label, payload, status, expected in controls:
        actual_status, actual = command(payload)
        if (actual_status, actual) != (status, expected):
            raise AssertionError((label, actual_status, actual))
        decisions.append({"case": label, "exit_code": status, "output": actual,
                          "input_sha256": sha256(payload).hexdigest()})

    files = (HERE / "reference.py", Path(__file__), reference.MODEL,
             model.PROTOTYPE / "rt03_reference.py", model.PROTOTYPE / "rt03_smallstep.py")
    return {
        "schema": "llmlang-state-result-reference-validation/1", "python": platform.python_version(),
        "source_sha256": {path.relative_to(model.ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in files},
        "comparisons": count, "wired_observations_sha256": comparison.hexdigest(), "controls": decisions,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
