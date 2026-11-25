#!/usr/bin/env python3
"""Compare cache action inputs using native binaries for the typed CLI workload."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TYPED = HERE.parent / "TYPED-CLI-01"
POLICIES = ("entry_only", "snapshot_only", "whole_inputs", "scoped_inputs")
STAGES = {
    "hello_recipe": (0, 0, ("hello", "literal", "Hello again!\n")),
    "echo_recipe": (0, 0, ("echo", "separator", "\t")),
    "equivalent_provider": (1, 0, None),
    "incorrect_provider": (2, 0, None),
    "optimization": (0, 3, None),
    "echo_and_provider": (1, 0, ("echo", "separator", "\t")),
}
BODY = "            let quotient = left.checked_div(right).ok_or(Diagnostic::Overflow)?;"
NATIVE_DIVISION = """            let mut quotient = 0;
            match unsafe { checked_provider_division(left, right, &mut quotient) } {
                0 => (),
                1 => return Err(Diagnostic::Zero),
                _ => return Err(Diagnostic::Overflow),
            }"""
FFI = """
extern "C" {
    fn checked_provider_division(left: i64, right: i64, answer: *mut i64) -> i32;
}
"""


def digest(payload):
    return sha256(payload).hexdigest()


def load_typed(directory):
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("typed_cli_fixture", directory / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command_version(name, flag):
    return subprocess.check_output([name, flag], text=True).splitlines()


def provider(directory, mode):
    code = HERE / "division.c"
    output = directory / f"division{mode}.o"
    subprocess.run(["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", f"-DPROVIDER={mode}",
                    "-c", str(code), "-o", str(output)], check=True, timeout=30)
    return output, digest(output.read_bytes())


def native_source(typed, artifact, body, runtime, entry):
    selected = runtime
    if entry == "calculator":
        assert runtime.count(BODY) == 1
        selected = FFI + runtime.replace(BODY, NATIVE_DIVISION)
    return typed.emit(body, artifact, selected).replace("Selected semantic snapshot", "Selected entry artifact")


def build(source, label, provider_path, level, directory):
    filename = directory / f"{label}.rs"
    executable = directory / label
    filename.write_text(source, encoding="utf-8")
    arguments = ["rustc", "--edition=2021", "-Dwarnings", "-A", "dead_code",
                 f"--remap-path-prefix={directory}=/llmlang/cli-keys", "-C", f"opt-level={level}"]
    if provider_path:
        arguments.extend(["-C", f"link-arg={provider_path}"])
    subprocess.run([*arguments, str(filename), "-o", str(executable)], check=True, timeout=30)
    return executable


def make_cold(typed, directory, memo, toolchain, recipe, runtime, label, provider_object, level):
    store, snapshot = typed.model.admit(recipe)
    artifact, provider_hash = provider_object
    result = {}
    for entry in typed.acceptance.PROGRAMS:
        selected = snapshot.mapping[entry]
        body = typed.model.body_for(store, snapshot, entry)
        source = native_source(typed, selected, body, runtime, entry)
        compiler = {name: toolchain[name] for name in ("rustc", "target")}
        if entry == "calculator":
            compiler["cc"] = toolchain["cc"]
        key = {
            "semantic_entry": selected, "generated_source": digest(source.encode()), "toolchain": compiler,
            "optimization": level, "native_provider": provider_hash if entry == "calculator" else None,
        }
        # Compile every distinct scoped action once and use the native result as the cold comparison.
        memo_key = json.dumps(key, sort_keys=True)
        if memo_key not in memo:
            path = build(source, f"candidate_{len(memo)}", artifact if entry == "calculator" else None,
                         level, directory)
            rows = [typed.observe([str(path)], case) for case in typed.acceptance.CASES if case.program == entry]
            memo[memo_key] = {"manifest": key, "binary_sha256": digest(path.read_bytes()), "cases": rows}
            path.unlink()
        result[entry] = memo[memo_key]
    return {"label": label, "snapshot": snapshot.root_hash, "provider": provider_hash,
            "entries": result, "optimization": level}


def cache_key(policy, phase, entry):
    action = phase["entries"][entry]["manifest"]
    if policy == "entry_only":
        return action["semantic_entry"]
    if policy == "snapshot_only":
        return phase["snapshot"], entry
    if policy == "whole_inputs":
        inputs = {name: row["manifest"] for name, row in phase["entries"].items()}
        return phase["snapshot"], inputs, entry
    return action


def compare(policy, entry, baseline, cold):
    old, required = (phase["entries"][entry] for phase in (baseline, cold))
    reused = cache_key(policy, baseline, entry) == cache_key(policy, cold, entry)
    selected = old if reused else required
    wrong = [target["case"] for observed, target in zip(selected["cases"], required["cases"], strict=True)
             if observed != target]
    false_contract_accept = (
        all(row["matches"] for row in selected["cases"])
        and not all(row["matches"] for row in required["cases"])
    )
    return {
        "compiled": not reused, "stale_action": selected["manifest"] != required["manifest"],
        "selected_binary": selected["binary_sha256"], "cold_binary": required["binary_sha256"],
        "different_output_cases": wrong, "masks_requested_contract_failure": false_contract_accept,
    }


def run(directory, source_directory):
    typed = load_typed(source_directory)
    original = json.loads((source_directory / "programs.json").read_bytes())
    runtime = (source_directory / "runtime.rs").read_text()
    toolchain = {"cc": command_version("cc", "--version")[0], "rustc": command_version("rustc", "-Vv"),
                 "target": command_version("cc", "-dumpmachine")[0]}
    objects = {mode: provider(directory, mode) for mode in (0, 1, 2)}
    assert len({signature for _, signature in objects.values()}) == 3
    memo = {}
    base = make_cold(typed, directory, memo, toolchain, original, runtime, "base", objects[0], 0)
    assert all(row["matches"] for item in base["entries"].values() for row in item["cases"])
    cases = {}
    for phase, (mode, level, edit) in STAGES.items():
        recipe = deepcopy(original)
        if edit:
            entry, field, value = edit
            recipe[entry][field] = value
        cold = make_cold(typed, directory, memo, toolchain, recipe, runtime, phase, objects[mode], level)
        cases[phase] = {"cold": cold,
                        "policies": {policy: {entry: compare(policy, entry, base, cold)
                                               for entry in typed.acceptance.PROGRAMS} for policy in POLICIES}}
    check = cases["equivalent_provider"]["cold"]["entries"]["calculator"]
    assert check["cases"] == base["entries"]["calculator"]["cases"] and check != base["entries"]["calculator"]
    rejected = cases["incorrect_provider"]["cold"]["entries"]["calculator"]["cases"]
    assert {row["case"] for row in rejected if not row["matches"]} == {"RT-01-calc-eof", "T-0003-05"}
    metrics = {}
    for policy in POLICIES:
        counters = Counter()
        for phase, evidence in cases.items():
            for entry, result in evidence["policies"][policy].items():
                for term in ("compiled", "stale_action"):
                    counters[term] += result[term]
                counters["output_case_differences"] += len(result["different_output_cases"])
                counters["masked_contract_failures"] += (phase == "incorrect_provider"
                                                          and result["masks_requested_contract_failure"])
        metrics[policy] = dict(counters)
    assert metrics["scoped_inputs"]["stale_action"] == metrics["whole_inputs"]["stale_action"] == 0
    assert metrics["scoped_inputs"]["compiled"] < metrics["whole_inputs"]["compiled"]
    assert metrics["entry_only"]["stale_action"] and metrics["snapshot_only"]["stale_action"]
    return {
        "schema": "llmlang-rt11-cli-action-keys/1", "python": platform.python_version(), "toolchain": toolchain,
        "fixture_sha256": digest(Path(__file__).read_bytes()),
        "provider_source_sha256": digest((HERE / "division.c").read_bytes()),
        "typed_input_sha256": {name: digest((source_directory / name).read_bytes()) for name in
                               ("programs.json", "runtime.rs", "model.py", "run.py")},
        "physical_unique_compilations": len(memo), "runtime_case_evaluations": sum(
            len(item["cases"]) for item in memo.values()),
        "changes": len(cases), "entries_per_change": 3, "metrics": metrics, "base": base, "observations": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--typed-dir", type=Path, default=TYPED)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-cli-keys-") as scratch:
        result = run(Path(scratch), args.typed_dir.resolve())
    observations = result.pop("observations")
    base = result.pop("base")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "base": ' + json.dumps(base) + ',')
    print('  "observations": {')
    print(",\n".join(f"    {json.dumps(name)}: {json.dumps(rows)}" for name, rows in observations.items()))
    print("  }\n}")
