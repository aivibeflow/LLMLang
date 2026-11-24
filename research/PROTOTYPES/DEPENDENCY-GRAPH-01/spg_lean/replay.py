#!/usr/bin/env python3
"""Replay exact SPG body binding and compare deep and shallow Lean observations."""

import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parent
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import canonical_bytes
from src.spg_ordered_lowering import execute, lower
from src.spg_representation import (
    Implementation, Operation, Program, RepresentationError, compile_program, observe,
)


LEAN = ["lean", "+leanprover/lean4:v4.36.0", "-DwarningAsError=true", "-DmaxRecDepth=8192"]
INPUTS = (-(2**96), -2147483649, -1, 0, 1, 2147483648, 2**96)
TRACES = (("prepare", "test", "left", "right"), ("prepare", "test", "fallback"))
BODY = ('emit("prepare", (emit("left", n) + emit("right", 1)) '
        'if emit("test", n == 0) else emit("fallback", n + 2))')


def implementation(graph):
    store = graph.store
    address = graph.snapshot.mapping["implementation:entry"]
    definition = store.get(address)
    if definition.kind != "rt05-definition-v1" or len(definition.payload) != 3:
        raise RepresentationError("expected an acyclic definition without call references")
    tag, owner, body = definition.payload
    if tag != {"literal": "rt05-spg-body-v1"} or set(body) != {"literal"}:
        raise RepresentationError("expected a canonical scalar SPG body")
    operation = store.get(owner["external"])
    links = {edge.relation: edge.target_hash for edge in operation.dependencies}
    interface = store.get(links["interface"]).payload
    input_types = [store.get(key).payload for key in interface["parameters"]]
    if input_types != ["Int"] or store.get(interface["result"]).payload != "Int":
        raise RepresentationError("expected the (Int) -> Int verification profile")
    return address, links["contract"], body["literal"], store.get(links["contract"]).payload


def render(term, labels):
    """Return the typed deep witness and the separately elaborated shallow term."""
    match term:
        case ["literal", value] if type(value) is bool:
            bit = str(value).lower()
            return f"(.boolean {bit})", f"(literal (s := .bool) {bit})"
        case ["literal", value] if type(value) is int:
            return f"(.integer ({value}))", f"(literal (s := .int) ({value}))"
        case ["argument", 0]:
            return ".input", "argument"
        case ["emit", str(label), tail] if label in labels:
            deep, shallow = render(tail, labels)
            event = labels.index(label)
            return f"(.emit {event} {deep})", f"(emit {event} {shallow})"
        case ["if", test, yes, no]:
            condition, when_true, when_false = (render(child, labels) for child in (test, yes, no))
            return (f"(.choose {condition[0]} {when_true[0]} {when_false[0]})",
                    f"(branch {condition[1]} {when_true[1]} {when_false[1]})")
        case [("add" | "eq") as form, left, right]:
            lhs, rhs = render(left, labels), render(right, labels)
            operator = "add" if form == "add" else "equal"
            return f"(.{operator} {lhs[0]} {rhs[0]})", f"({operator} {lhs[1]} {rhs[1]})"
        case _:
            raise RepresentationError(f"unsupported SPG term {term!r}")


def lean_list(values):
    return "[" + ", ".join(json.dumps(value) if isinstance(value, str) else lean_list(value)
                            for value in values) + "]"


def source_module(exact_body, contract, labels, deep, shallow):
    samples = ", ".join(map(str, INPUTS))
    exact_contract = canonical_bytes(contract).decode("ascii")
    return f'''import SpgObservations
open ObservableRewrite SpgObservations

def body : String := {json.dumps(exact_body)}
def labels : List String := {lean_list(labels)}
def contract : List (List String) := {lean_list(contract)}
def contractPayload : String := {json.dumps(exact_contract)}
def witness : Expr .int := {deep}
def candidate : Shallow .int := {shallow}

theorem witness_bound : bodyBytes labels witness = some body := by decide
theorem contract_bound : contractBytes contract = contractPayload := by decide

theorem candidate_bound (input : Int) : candidate input = evaluate input witness :=
  lower_preserves witness input

theorem candidate_contract (input : Int) : traceAllowed labels contract (candidate input) = true := by
  by_cases same : input = 0
  · subst input
    decide
  · simp [traceAllowed, traceLabels, candidate, labels, contract, emit, branch,
      add, equal, pairwise, argument, literal, sequence, same]

#print axioms witness_bound
#print axioms contract_bound
#print axioms candidate_bound
#print axioms candidate_contract
#eval IO.println (Lean.Json.compress (Lean.toJson (([{samples}] : List Int).map (fun n =>
  [observation labels (evaluate n witness), observation labels (candidate n)]))))
'''


def lean(work, arguments, *, passed=True, diagnostic=None):
    result = subprocess.run([*LEAN, *arguments], cwd=work, text=True, capture_output=True,
                            env={**os.environ, "LEAN_PATH": str(work)}, timeout=60)
    if (result.returncode == 0) != passed or (diagnostic and diagnostic not in result.stdout):
        raise ValueError(f"Unexpected Lean result for {arguments}:\n{result.stdout}{result.stderr}")
    return result.stdout


def replay(work, source_body):
    graph_source = Program({"effects": TRACES}, {"entry": Operation("Entry", ("Int",), "Int", "effects")},
                           {"entry": Implementation("entry", ("n",), source_body)}, {})
    graph = compile_program(graph_source)
    address, contract_digest, exact_body, contract = implementation(graph)
    labels = sorted({label for trace in contract for label in trace})
    body = json.loads(exact_body)
    deep, shallow = render(body, labels)
    module = source_module(exact_body, contract, labels, deep, shallow)
    (work / "Bound.lean").write_text(module, encoding="utf-8")
    output = lean(work, ["-o", "Bound.olean", "Bound.lean"])
    proof_audit, observations = output.strip().rsplit("\n", 1)
    ordered = lower(graph, "entry")
    expected = []
    for number in INPUTS:
        value, trace = observe(graph, "entry", (number,))
        if execute(ordered, (number,)) != (value, trace):
            raise ValueError(f"The stored and ordered SPG observations differ on {number}")
        expected.append([value, list(trace)])
    if json.loads(observations) != [[row, row] for row in expected]:
        raise ValueError(f"Lean observations differ from the stored SPG: {observations}")

    # Swap only the addends on the true branch. Both implementations typecheck.
    affirmative = body[2][2]
    affirmative[1], affirmative[2] = affirmative[2], affirmative[1]
    mutant_deep, mutant_shallow = render(body, labels)
    (work / "Mutant.lean").write_text(f'''import Bound
open ObservableRewrite SpgObservations
def mutant : Shallow .int := {mutant_shallow}
def differentWitness : Expr .int := {mutant_deep}
theorem same_result (input : Int) : (mutant input).1 = (candidate input).1 := by
  by_cases same : input = 0
  · subst input
    rfl
  · simp [mutant, candidate, emit, branch, add, equal, pairwise, argument, literal, sequence, same]
theorem different_trace : (mutant 0).2 ≠ (candidate 0).2 := by decide
theorem different_body : bodyBytes labels differentWitness ≠ some body := by decide
theorem admitted_by_relaxed_contract : traceAllowed labels [["prepare", "test", "left", "right"],
  ["prepare", "test", "right", "left"], ["prepare", "test", "fallback"]] (mutant 0) = true := by decide
theorem wrong_contract : traceAllowed labels [["prepare", "test", "right", "left"],
  ["prepare", "test", "fallback"]] (candidate 0) = false := by decide
''', encoding="utf-8")
    lean(work, ["-o", "Mutant.olean", "Mutant.lean"])
    controls = {
        "reordered_candidate": "(mutant 0).2 = (evaluate 0 witness).2",
        "reordered_typed_witness": "bodyBytes labels differentWitness = some body",
        "wrong_order_contract": ('traceAllowed labels [["prepare", "test", "right", "left"], '
                                 '["prepare", "test", "fallback"]] (candidate 0) = true'),
    }
    for name, statement in controls.items():
        rejected = work / "Rejected.lean"
        rejected.write_text(f"import Mutant\nopen ObservableRewrite SpgObservations\n"
                            f"theorem {name} : {statement} := by decide\n", encoding="utf-8")
        lean(work, [rejected.name], passed=False, diagnostic="Tactic `decide` proved that the proposition")

    # The existing SPG compiler handles subtraction. This fixture profile declines it.
    outside = compile_program(replace(graph_source, implementations={
        "entry": Implementation("entry", ("n",), "n - 1"),
    }))
    try:
        render(json.loads(implementation(outside)[2]), labels)
    except RepresentationError as error:
        if "unsupported SPG term" not in str(error):
            raise
    else:
        raise ValueError("Subtraction was unexpectedly admitted")

    return {
        "source": source_body,
        "spg_snapshot": graph.snapshot.root_hash,
        "spg_definition": address,
        "spg_trace_contract": contract_digest,
        "ordered_artifact": ordered.identity,
        "canonical_body": exact_body,
        "canonical_contract": canonical_bytes(contract).decode("ascii"),
        "generated_module_sha256": sha256(module.encode()).hexdigest(),
        "axiom_audit": proof_audit,
        "observations": [[number, *row] for number, row in zip(INPUTS, expected, strict=True)],
        "controls": {**dict.fromkeys(controls, "rejected by Lean"), "subtraction": "unsupported"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-spg-lean-") as tmp:
        scratch = Path(tmp)
        rewrite = PROTOTYPE / "logos_binding" / "ObservableRewrite.lean"
        support = HERE / "SpgObservations.lean"
        for source in (rewrite, support):
            (scratch / source.name).write_bytes(source.read_bytes())
        lean(scratch, ["-o", "ObservableRewrite.olean", rewrite.name])
        axioms = lean(scratch, ["-o", "SpgObservations.olean", support.name]).strip()
        result = {
            "schema": "llmlang-rt32-spg-lean-observations-v1",
            "lean": lean(scratch, ["--version"]).strip(),
            "generic_lowering_axioms": axioms,
            "positive_literal": replay(scratch, BODY),
            "minimum_literal": replay(scratch, BODY.replace("n + 2", "n + -2147483648")),
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
