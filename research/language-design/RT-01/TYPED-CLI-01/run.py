#!/usr/bin/env python3
"""Lower the same exact typed CLI recipe used by the interpreter and compare subprocesses."""

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import platform
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

import model

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parents[1] / "PROTOTYPES" / "CLI-WORKLOADS-01"
spec = importlib.util.spec_from_file_location("rt01_acceptance", BASELINE / "run.py")
acceptance = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = acceptance
spec.loader.exec_module(acceptance)

CONTROL = {
    "floor_division": ("calculator", {"division": "floor"}, {"T-0003-05", "RT-01-calc-eof"}),
    "drop_empty_argument": ("echo", {"keep_empty": False}, {"T-0002-05", "RT-01-echo-utf8"}),
    "diagnostics_on_stdout": ("calculator", {"diagnostic_stream": "stdout"}, None),
}
OPERATIONS = {"add": "Add", "subtract": "Subtract", "multiply": "Multiply", "divide": "Divide"}


def checksum(data):
    return sha256(data).hexdigest()


def byte_const(value):
    return "&[" + ", ".join(str(octet) for octet in value) + "]"


def string_const(value):
    return byte_const(value.encode())


def bool_const(value):
    return "true" if value else "false"


def emit(entry, root, runtime):
    handler = entry["handler"]
    if handler == "write_literal":
        expression = f'process_output({string_const(entry["literal"])})'
    elif handler == "join_arguments":
        expression = (
            f'echo({string_const(entry["separator"])}, {string_const(entry["suffix"])}, '
            f'{bool_const(entry["keep_empty"])})'
        )
    else:
        operations = ", ".join(f"({ord(code)}, Operation::{OPERATIONS[operation]})"
                               for code, operation in sorted(entry["operations"].items()))
        diagnostics = ", ".join(string_const(entry["diagnostics"][key]) for key in ("invalid", "zero", "overflow"))
        expression = (
            "calculator(Calculator {\n"
            f'    separators: {byte_const(entry["separators"])}, terminator: {entry["terminator"]},\n'
            f'    operations: &[{operations}], floor: {bool_const(entry["division"] == "floor")},\n'
            f'    diagnostics_on_stdout: {bool_const(entry["diagnostic_stream"] == "stdout")},\n'
            f'    diagnostics: [{diagnostics}],\n'
            "})"
        )
    return runtime + f"\n// Selected semantic snapshot: {root}\nfn main() {{ std::process::exit({expression}); }}\n"


def compile_rust(scratch, label, src, level):
    selected = scratch / f"{label}.rs"
    executable = scratch / label
    selected.write_text(src, encoding="utf-8")
    subprocess.run(["rustc", "--edition=2021", "-Dwarnings", "-A", "dead_code", "-C", f"opt-level={level}",
                    f"--remap-path-prefix={scratch}=/llmlang/rt01", str(selected), "-o", str(executable)], check=True, timeout=30)
    return [str(executable)], {
        "source_sha256": checksum(selected.read_bytes()), "executable_sha256": checksum(executable.read_bytes()),
    }


def observe(command, case):
    result = acceptance.run_case(command, case)
    exit_ok = result.returncode == 0 if case.success else (
        result.returncode > 0 or case.broken_stdout and result.returncode == -signal.SIGPIPE
    )
    matches = exit_ok and all(expected is None or actual == expected
                              for expected, actual in ((case.stdout, result.stdout), (case.stderr, result.stderr)))
    return {"case": case.identifier, "status": result.returncode, "matches": matches,
            "stdout_hex": result.stdout.hex() if result.stdout is not None else None,
            "stderr_hex": result.stderr.hex()}


def run_all(commands):
    return [observe(commands[case.program], case) for case in acceptance.CASES]


def run(scratch):
    source = HERE / "programs.json"
    programs = json.loads(source.read_bytes())
    store, snapshot = model.admit(programs)
    unsupported = deepcopy(programs)
    unsupported["hello"]["handler"] = "write_external_file"
    try:
        model.admit(unsupported)
    except ValueError as error:
        assert str(error) == "Unsupported entry effect"
    else:
        raise AssertionError("Unsupported effect passed exact recipe admission")
    runtime = (HERE / "runtime.rs").read_text()
    executable = scratch / "reference-c"
    subprocess.run(["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", str(BASELINE / "reference.c"),
                    "-o", str(executable)], check=True, timeout=30)
    observations = {
        "host_python": run_all({entry: [sys.executable, "-B", str(BASELINE / "reference.py"), entry]
                                for entry in acceptance.PROGRAMS}),
        "host_c": run_all({entry: [str(executable), entry] for entry in acceptance.PROGRAMS}),
    }
    interpreted = [sys.executable, "-B", str(HERE / "model.py"), str(source), snapshot.root_hash]
    observations["interpreted"] = run_all({entry: [*interpreted, entry] for entry in acceptance.PROGRAMS})
    code = {}
    for level in (0, 3):
        commands = {}
        for entry in acceptance.PROGRAMS:
            native = emit(model.body_for(store, snapshot, entry), snapshot.root_hash, runtime)
            command, code[f"{entry}_O{level}"] = compile_rust(scratch, f"{entry}_o{level}", native, level)
            commands[entry] = command
        observations[f"rust_O{level}"] = run_all(commands)
    assert all(row["matches"] for route in observations.values() for row in route)

    controls = {}
    for control, (entry, patch, expected) in CONTROL.items():
        wrong = deepcopy(programs)
        wrong[entry].update(patch)
        changed_store, changed = model.admit(wrong)
        assert changed.root_hash != snapshot.root_hash
        assert set(changed.mapping.items()) & set(snapshot.mapping.items()) == {
            (other, ident) for other, ident in snapshot.mapping.items() if other != entry
        }
        tampered = scratch / f"{control}.json"
        tampered.write_text(json.dumps(wrong), encoding="utf-8")
        wrong_pin = subprocess.run([sys.executable, "-B", str(HERE / "model.py"), str(tampered),
                                    snapshot.root_hash, entry], capture_output=True, timeout=5, check=False)
        assert wrong_pin.returncode == 2 and not wrong_pin.stdout
        mutant_code = emit(model.body_for(changed_store, changed, entry), changed.root_hash, runtime)
        native, generated = compile_rust(scratch, control, mutant_code, 3)
        routes = {"interpreter": [sys.executable, "-B", str(HERE / "model.py"),
                                   str(tampered), changed.root_hash, entry], "rust": native}
        results = {name: [observe(command, case) for case in acceptance.CASES if case.program == entry]
                   for name, command in routes.items()}
        failures = {name: {row["case"] for row in rows if not row["matches"]} for name, rows in results.items()}
        if expected is None:
            expected = {case.identifier for case in acceptance.CASES if case.program == entry and case.stderr}
        assert all(actual == expected for actual in failures.values())
        controls[control] = {"snapshot": changed.root_hash, "changed_entry": changed.mapping[entry],
                             "generated": generated, "rejected_case_ids": sorted(expected),
                             "old_snapshot_status": wrong_pin.returncode, "observations": results}
    return {
        "schema": "llmlang-rt01-typed-cli/1", "python": platform.python_version(),
        "cc": subprocess.check_output(["cc", "--version"], text=True).splitlines()[0],
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
        "input_shas": {name: checksum(path.read_bytes()) for name, path in (
            ("recipe", source), ("model", HERE / "model.py"), ("runtime", HERE / "runtime.rs"),
            ("runner", Path(__file__)), ("acceptance", BASELINE / "run.py"),
            ("c_reference", BASELINE / "reference.c"), ("python_reference", BASELINE / "reference.py"))},
        "snapshot": snapshot.root_hash, "entry_artifacts": snapshot.mapping, "generated": code, "unsupported_entry_effect": "refused",
        "route_counts": {route: sum(row["matches"] for row in rows) for route, rows in observations.items()},
        "case_count": len(acceptance.CASES), "observations": observations, "controls": controls,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt01-typed-cli-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": {')
    print(",\n".join(f"    {json.dumps(name)}: {json.dumps(rows)}" for name, rows in observations.items()))
    print("  }\n}")
