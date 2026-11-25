#!/usr/bin/env python3
"""Generate and kernel-check bounded observations for source-derived cleanup CFGs."""

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parents[2] / "language-design" / "RT-03" / "SOURCE-CLEANUP-CFG-01"
LEAN_COMMIT = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
sys.path.insert(0, str(FIXTURE))
import flow


def hash_bytes(payload):
    return sha256(payload).hexdigest()


def lean_string(text):
    return json.dumps(text, ensure_ascii=False)


def bool_lit(value):
    return "true" if value else "false"


def span(values):
    return "⟨" + ", ".join(map(str, values)) + "⟩"


def tests(value):
    return f"(.constant {bool_lit(value)})" if isinstance(value, bool) else f".{value}"


def program(graph):
    entry, nodes = graph
    instructions = []
    for node in nodes:
        op, data = node.kind, node.data
        targets = " ".join(map(str, node.next))
        position = span(node.span) if node.span is not None else ""
        if op in {"fallthrough", "returned", "error"}:
            body = f".{op}"
        elif op in {"open_slot", "close"}:
            name = "openSlot" if op == "open_slot" else "closeSlot"
            body = f".{name} {position} .{data[0]} {targets}"
        elif op == "test":
            body = f".test {tests(data[0])} {targets}"
        elif op == "probe":
            body = f".probe {position} {lean_string(data[0])} {tests(data[1])} {targets}"
        elif op in {"emit", "stage", "fail"}:
            body = f".{op} {position} {lean_string(data[0])} {targets}"
        else:
            raise ValueError(op)
        instructions.append(body)
    return f"⟨{entry}, [\n  " + ",\n  ".join(instructions) + "]⟩"


def event(item):
    position, event_kind, label, *payload = item
    where = span(position)
    if event_kind == "open":
        return f".openSlot {where} .{label}"
    if event_kind == "close":
        return f".closeSlot {where} .{label} {bool_lit(payload[0])}"
    if event_kind == "probe":
        return f".probe {where} {lean_string(label)} {bool_lit(payload[0])}"
    return f".{event_kind} {where} {lean_string(label)}"


def observation(row):
    events = "[" + ", ".join(map(event, row["trace"])) + "]"
    causes = "[" + ", ".join(map(lean_string, row["errors"])) + "]"
    result = "none" if row["result"] is None else f"some {lean_string(row['result'])}"
    owner = "absent" if row["handle"] == "none" else row["handle"]
    return f"⟨{events}, {result}, {causes}, .{row['slots']['inner']}, .{row['slots']['outer']}, .{owner}⟩"


def boolean_inputs(row):
    return tuple(map(bool_lit, (
        row["inputs"]["x"], row["inputs"]["y"], row["release_failures"]["inner"],
        row["release_failures"]["outer"],
    )))


def emit(ledger):
    declarations = ["import CleanupModel", "open Cleanup", "set_option maxHeartbeats 5000000"]
    proof_headers = []
    graphs = {}
    exact_inputs = {}
    for index, (fixture, item) in enumerate(ledger["fixtures"].items()):
        text = item["source"]
        assert hash_bytes(text.encode()) == item["sha256"]
        graph = flow.lower(text)
        payload = json.dumps([graph[0], [asdict(node) for node in graph[1]]], sort_keys=True)
        assert hash_bytes(payload.encode()) == item["graph_sha256"]
        graphs[fixture] = graph

        declarations.append(f"def case{index} : Program := {program(graph)}")
        cases = {}
        for row in ledger["executions"]:
            if row["fixture"] != fixture:
                continue
            inputs = boolean_inputs(row)
            assert inputs not in cases
            cases[inputs] = observation(row["source_observation"])
        assert len(cases) == 16
        exact_inputs[fixture] = cases
        oracle_branches = "\n".join(f"  | {', '.join(inputs)} => {outcome}"
                                    for inputs, outcome in cases.items())
        declarations.append(f"def oracle{index} : Bool → Bool → Bool → Bool → Observation\n{oracle_branches}")
        proof_headers.extend((
            (f"sourceAgreement{index}", "(x y inner outer : Bool)",
             f"run case{index} ⟨x, y, inner, outer⟩ = some (oracle{index} x y inner outer)",
             "cases x <;> cases y <;> cases inner <;> cases outer <;> decide"),
            (f"resourceCompletion{index}", "(x y inner outer : Bool)",
             f"(run case{index} ⟨x, y, inner, outer⟩).map (resultSettled ⟨x, y, inner, outer⟩) = some true",
             "cases x <;> cases y <;> cases inner <;> cases outer <;> decide"),
        ))

    fixture = "and/return_on_true"
    text = ledger["fixtures"][fixture]["source"]
    entry, nodes = graphs[fixture]
    bad_spans = list(nodes)
    original = bad_spans[entry]
    a, b, c, d = original.span
    bad_spans[entry] = replace(original, span=(a, b, c + 1, d))
    no_fault = ("true", "true", "false", "false")
    controls = (
        ("eagerEvaluation", flow.lower(text, eager=True), ("false", "true", "false", "false")),
        ("returnBypassesCleanup", flow.lower(text, skip_return_cleanup=True),
         ("true", "true", "true", "false")),
        ("sourceSpanChanged", (entry, bad_spans), no_fault),
        ("missingEntry", (len(nodes), nodes), no_fault),
    )
    for name, graph, inputs in controls:
        argument = span(inputs)
        expected = exact_inputs[fixture][inputs]
        declarations.append(f"def {name} : Program := {program(graph)}")
        proof_headers.append((f"reject_{name}", "", f"run {name} {argument} ≠ some {expected}", "decide"))

    for name, parameters, claim, tactic in proof_headers:
        declarations.append(f"theorem {name} {parameters} :\n    {claim} := by\n  {tactic}")
    declarations.extend(f"#print axioms {name}" for name, *_ in proof_headers)
    return "\n\n".join(declarations) + "\n", [name for name, *_ in proof_headers]


def command(arguments, *, cwd=None):
    result = subprocess.run(arguments, cwd=cwd, text=True, capture_output=True, timeout=120, check=True)
    if result.stderr:
        raise RuntimeError(result.stderr)
    return result.stdout


def replay(lean):
    version = command([lean, "--version"]).strip()
    if LEAN_COMMIT not in version:
        raise ValueError("Expected the exact Lean 4.36.0 revision")

    native = (FIXTURE / "evidence.json").read_bytes()
    reproduction = command([sys.executable, "-B", str(FIXTURE / "run.py")]).encode()
    assert native == reproduction
    ledger = json.loads(native)
    source, names = emit(ledger)
    model = HERE / "CleanupModel.lean"
    with TemporaryDirectory(prefix="llmlang-cleanup-proof-") as temporary:
        root = Path(temporary)
        shutil.copy(model, root / model.name)
        (root / "Generated.lean").write_text(source, encoding="utf-8")
        command([lean, "-DwarningAsError=true", "-o", "CleanupModel.olean", model.name], cwd=root)
        result = subprocess.run(
            [lean, "-DwarningAsError=true", "Generated.lean"], cwd=root,
            env={**os.environ, "LEAN_PATH": str(root)},
            text=True, capture_output=True, timeout=120, check=False,
        )
        if result.returncode or result.stderr:
            raise RuntimeError(result.stdout + result.stderr)
        written = result.stdout.splitlines()
        allowed = re.compile(r"^'([^']+)' (does not depend on any axioms|depends on axioms: \[(.*)\])$")
        axioms = {}
        for line in written:
            match = allowed.fullmatch(line)
            if match is None:
                raise ValueError(f"Unexpected Lean output {line!r}")
            name, _, dependencies = match.groups()
            axioms[name] = [] if dependencies is None else dependencies.split(", ")
        assert list(axioms) == names
        trusted = {"propext", "Quot.sound"}
        if any(set(dependencies) - trusted for dependencies in axioms.values()):
            raise ValueError(f"Unexpected axioms in {axioms}")

    return {
        "schema": "llmlang-source-cleanup-kernel/1",
        "lean": version,
        "python": sys.version.split()[0],
        "native_evidence_sha256": hash_bytes(native),
        "runner_sha256": hash_bytes(Path(__file__).read_bytes()),
        "model_sha256": hash_bytes(model.read_bytes()),
        "generated_lean_sha256": hash_bytes(source.encode()),
        "native_observations": len(ledger["executions"]),
        "source_agreement": len(ledger["fixtures"]),
        "resource_completion": len(ledger["fixtures"]),
        "mutation_inequalities": 4,
        "theorems": axioms,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    arguments = parser.parse_args()
    lean = shutil.which(arguments.lean)
    if lean is None:
        raise ValueError("Pinned Lean is required")
    print(json.dumps(replay(lean), indent=2))


if __name__ == "__main__":
    main()
