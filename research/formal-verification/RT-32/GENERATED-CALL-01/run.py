"""Generate and check conditional and closed proofs for two exact SPG call modes."""

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import digest
from src.spg_representation import RepresentationError, compile_program, observe
from tests.test_spg_representation import dispatch_program, replace_body


LEAN = ["lean", "+leanprover/lean4:v4.36.0", "-DwarningAsError=true"]
INPUTS = (-(2**96), -1, 0, 1, 2**96)
ORDER = (("first", "last"),)
REVERSED = (("last", "first"),)
EXPORTS = ("late", "direct")


def links(graph, value):
    return {edge.relation: edge.target_hash for edge in graph.store.get(value).dependencies}


def read_function(graph, address):
    item = graph.store.get(address)
    if item.kind != "rt05-definition-v1" or not isinstance(item.payload, list):
        raise RepresentationError("expected an acyclic compiled body")
    marker, owner, body, *references = item.payload
    if marker != {"literal": "rt05-spg-body-v1"}:
        raise RepresentationError("unexpected SPG body form")
    operation = owner["external"]
    declarations = links(graph, operation)
    interface = graph.store.get(declarations["interface"]).payload
    if ([graph.store.get(key).payload for key in interface["parameters"]] != ["Int"]
            or graph.store.get(interface["result"]).payload != "Int"):
        raise RepresentationError("only unary integer functions are admitted")
    contract = declarations["contract"]
    return operation, contract, graph.store.get(contract).payload, json.loads(body["literal"]), references


def binding(graph, operation):
    matches = [(address, edges["implementation"]) for slot, address in graph.snapshot.selections
               if slot.startswith("binding:") and (edges := links(graph, address))["operation"] == operation]
    if len(matches) != 1:
        raise RepresentationError("expected one exact binding for the selected operation")
    return matches[0]


def render(term, mode=None):
    match term:
        case ["argument", 0]:
            return "(arg n)"
        case ["literal", int(value)] if type(value) is int:
            return f"(arg ({value}))"
        case ["emit", str(event), child]:
            return f"(emit {json.dumps(event)} {render(child, mode)})"
        case ["add", left, right]:
            return f"(add {render(left, mode)} {render(right, mode)})"
        case [("op" | "pin") as call, 0, operand] if call == mode:
            return f"(invoke provider {render(operand)})"
        case _:
            raise RepresentationError(f"unsupported compiled term {term!r}")


def lean_list(value):
    if isinstance(value, str):
        return json.dumps(value)
    return "[" + ", ".join(map(lean_list, value)) + "]"


def subject(graph, slot):
    caller = graph.snapshot.mapping[f"implementation:{slot}"]
    own_op, caller_contract, allowed, body, references = read_function(graph, caller)
    mode = "op" if slot == "late" else "pin"
    if len(references) != 1 or body != [mode, 0, ["emit", "argument", ["argument", 0]]]:
        raise RepresentationError("expected one ordered call argument and one exact call reference")
    ref = references[0]["external" if mode == "op" else "exact_call"]
    selected_binding, provider = binding(graph, ref) if mode == "op" else (None, ref)
    operation, provider_contract, provider_allowed, provider_body, provider_refs = read_function(graph, provider)
    if (mode == "op" and operation != ref) or provider_refs:
        raise RepresentationError("unexpected provider ownership or unresolved provider calls")
    return {"mode": mode, "root": graph.snapshot.root_hash, "caller": caller, "caller_operation": own_op,
            "caller_contract": caller_contract, "caller_allowed": allowed, "caller_body": body, "reference": ref,
            "binding": selected_binding, "provider": provider, "provider_operation": operation,
            "provider_contract": provider_contract, "provider_allowed": provider_allowed,
            "provider_body": provider_body}


def caller_source(entry):
    return f"""import CallCore
open LLMLang.GeneratedCall
def callerIdentity : String := "{entry['caller']}"
def callReference : String := "{entry['reference']}"
def assumptionsIdentity : String := "{entry['provider_contract']}"
def claimIdentity : String := "{entry['caller_contract']}"
def required : List (List String) := {lean_list(entry['provider_allowed'])}
def declared : List (List String) := {lean_list(entry['caller_allowed'])}
def caller (provider : Function) (n : Int) : Observation := {render(entry['caller_body'], entry['mode'])}

theorem conditional (provider : Function) (evidence : conforms required provider) :
    conforms declared (caller provider) := by
  intro n
  have justified := evidence n
  simp [required] at justified
  simp_all [caller, invoke, emit, arg, declared]
#print axioms conditional
"""


def provider_source(entry):
    return f"""import Caller
open LLMLang.GeneratedCall
def providerIdentity : String := "{entry['provider']}"
def actualProvider (n : Int) : Observation := {render(entry['provider_body'])}

theorem providerChecked : conforms required actualProvider := by
  intro n
  simp [required, actualProvider, emit, add, arg]
#print axioms providerChecked
"""


def closed_source(entry):
    inputs = ", ".join(map(str, INPUTS))
    version = entry["binding"] or entry["reference"]
    return f"""import Provider
open LLMLang.GeneratedCall
def selectedReference : String := "{version}"
def scopeRoot : String := "{entry['root']}"
theorem exactProvider : providerIdentity = "{entry['provider']}" := by rfl
theorem exactCaller : callerIdentity = "{entry['caller']}" := by rfl
theorem exactAssumptions : assumptionsIdentity = "{entry['provider_contract']}" := by rfl
theorem closedClaim : conforms declared (caller actualProvider) :=
  conditional actualProvider providerChecked
#print axioms closedClaim

def main : IO Unit :=
  for input in ([{inputs}] : List Int) do
    let (value, trace) := caller actualProvider input
    IO.println s!"{{value}}:{{String.intercalate "," trace}}"
"""


def run_lean(directory, module, *args, expected=None):
    command = [*LEAN, *args, module + ".lean"]
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=45,
                            env={**os.environ, "LEAN_PATH": os.pathsep.join(map(str, (directory, directory.parent)))})
    if expected is None and result.returncode != 0:
        raise AssertionError((command, result.stdout, result.stderr))
    if expected is not None and (result.returncode == 0 or expected not in result.stdout):
        raise AssertionError((command, expected, result.stdout, result.stderr))
    return result.stdout.strip().splitlines()


def verify_case(directory, graph, slot, expectation, stale_provider=None):
    directory.mkdir()
    entry = subject(graph, slot)
    source = {"Caller": caller_source(entry), "Provider": provider_source(entry), "Closed": closed_source(entry)}
    for module, text in source.items():
        (directory / (module + ".lean")).write_text(text, encoding="utf-8")
    audits = {}
    negative = None
    if expectation == "contract_mismatch":
        run_lean(directory, "Caller", expected="unsolved goals")
    else:
        audits["conditional"] = run_lean(directory, "Caller", "-o", "Caller.olean")
        if expectation == "bad_provider":
            run_lean(directory, "Provider", expected="unsolved goals")
        else:
            audits["provider"] = run_lean(directory, "Provider", "-o", "Provider.olean")
            audits["closed"] = run_lean(directory, "Closed", "-o", "Closed.olean")
            if stale_provider is not None:
                exact = f'theorem exactProvider : providerIdentity = "{entry["provider"]}"'
                stale = f'theorem exactProvider : providerIdentity = "{stale_provider}"'
                altered = source["Closed"].replace(exact, stale)
                if altered == source["Closed"]:
                    raise AssertionError("Stale provider control did not change expected identity")
                (directory / "Stale.lean").write_text(altered, encoding="utf-8")
                run_lean(directory, "Stale", expected="rfl")
                negative = "stale_provider_rejected"
            lines = run_lean(directory, "Closed", "--run")
            expected = [f"{value}:{','.join(trace)}" for n in INPUTS
                        for value, trace in (observe(graph, slot, (n,)),)]
            if lines[-len(INPUTS):] != expected:
                raise AssertionError((slot, expected, lines))
    values = [observe(graph, slot, (n,)) for n in INPUTS]
    return {"subject": entry, "source_ids": {name: digest(text) for name, text in source.items()},
            "expected": expectation, "observations": values, "axioms": audits,
            "negative_replay": negative}


def verify(root):
    shutil.copyfile(HERE / "CallCore.lean", root / "CallCore.lean")
    run_lean(root, "CallCore", "-o", "CallCore.olean")
    trace = {"provider": ORDER, "forward": (("argument", "first", "last"),), "quiet": ((),)}
    program = replace(dispatch_program(), contracts=trace)
    for slot, call in (("late", 'op("provider", emit("argument", n))'),
                       ("direct", 'pin("primary", emit("argument", n))')):
        program = replace_body(program, slot, call)

    rebound = replace(program, bindings={"provider": "alternate"})
    changed = replace_body(program, "primary", 'emit("first", emit("last", n + 4))')
    bad = replace_body(rebound, "alternate", 'emit("last", emit("first", n + 2))')
    broader = replace(bad, contracts={**trace, "provider": (*ORDER, *REVERSED)})
    inputs = {"base": program, "rebound": rebound, "primary_edit": changed,
              "bad_rebound": bad, "broader_provider": broader}
    cases = {}
    for name, candidate in inputs.items():
        graph = compile_program(candidate)
        for slot in EXPORTS:
            expectation = "closed"
            if name == "bad_rebound" and slot == "late":
                expectation = "bad_provider"
            if name == "broader_provider":
                expectation = "contract_mismatch"
            stale_provider = cases["base/late"]["subject"]["provider"] if name == "rebound" and slot == "late" else None
            cases[f"{name}/{slot}"] = verify_case(root / f"{name}-{slot}", graph, slot, expectation, stale_provider)

    for slot in EXPORTS:
        base, selected, edited = (cases[f"{variant}/{slot}"] for variant in ("base", "rebound", "primary_edit"))
        expected = slot == "late"
        if (base["observations"] != selected["observations"]) != expected:
            raise AssertionError((slot, "rebinding"))
        if base["source_ids"]["Caller"] != selected["source_ids"]["Caller"]:
            raise AssertionError((slot, "rebinding must preserve conditional proof"))
        if (base["source_ids"]["Caller"] == edited["source_ids"]["Caller"]) != expected:
            raise AssertionError((slot, "editing a directly pinned target changes the conditional artifact"))
        if base["observations"] == edited["observations"]:
            raise AssertionError((slot, "both use the edited primary provider"))
        if (base["source_ids"]["Provider"] != selected["source_ids"]["Provider"]) != expected:
            raise AssertionError((slot, "rebound provider evidence"))
    if cases["bad_rebound/late"]["observations"][2] != (2, ("argument", "last", "first")):
        raise AssertionError("Wrong-order provider lost its distinguishing observation")
    return cases


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-generated-call-") as temporary:
        ledger = verify(Path(temporary))
    identity = subprocess.check_output([*LEAN, "--version"], text=True).strip()
    args.output.write_text(json.dumps({"format": "llmlang-generated-call/1", "lean": identity,
                                      "python": sys.version.split()[0], "inputs": INPUTS, "cases": ledger,
                                      "call_core_source_id": digest((HERE / "CallCore.lean").read_text())},
                                     indent=2, sort_keys=True) + "\n", encoding="utf-8")
