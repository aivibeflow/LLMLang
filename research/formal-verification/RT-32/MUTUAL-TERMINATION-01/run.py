"""Generate total Lean recursion for a natural-number subdomain of two exact SPG members."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import canonical_bytes
from src.spg_representation import FuelExhausted, Implementation, Operation, Program
from src.spg_representation import RepresentationError, compile_program, observe
from tests.test_spg_representation import replace_body


NAMES = ("evenMember", "oddMember")
TEST_INPUTS = tuple(range(16))
LEAN = ("lean", "+leanprover/lean4:v4.36.0", "-DwarningAsError=true")


def program():
    operations = {name: Operation(name, ("Int",), "Bool", "quiet") for name in NAMES}
    return Program({"quiet": ((),)}, operations, {
        NAMES[0]: Implementation(NAMES[0], ("n",), f'True if n == 0 else pin("{NAMES[1]}", n - 1)', "a"),
        NAMES[1]: Implementation(NAMES[1], ("n",), f'False if n == 0 else pin("{NAMES[0]}", n - 1)', "b"),
    }, {})


def target(graph, address, relation):
    found = [edge.target_hash for edge in graph.store.get(address).dependencies if edge.relation == relation]
    if len(found) != 1:
        raise RepresentationError(f"expected one exact {relation} reference")
    return found[0]


def extract(graph):
    members = {name: graph.snapshot.mapping[f"implementation:{name}"] for name in NAMES}
    groups = {target(graph, member, "member_of") for member in members.values()}
    if len(groups) != 1:
        raise RepresentationError("expected one exact recursive group")
    group, = groups
    payload = graph.store.get(group).payload
    positions = {graph.store.get(member).payload["position"]: name for name, member in members.items()}
    if len(payload) != 2 or set(positions) != {0, 1}:
        raise RepresentationError("only two uniquely positioned members are admitted")
    definitions = {}
    for position, name in sorted(positions.items()):
        row = payload[position]["body"]
        if len(row) != 4 or row[0] != {"literal": "rt05-spg-body-v1"}:
            raise RepresentationError("unsupported recursive body")
        operation = row[1]["external"]
        types = graph.store.get(target(graph, operation, "interface")).payload
        if ([graph.store.get(kind).payload for kind in types["parameters"]] != ["Int"]
                or graph.store.get(types["result"]).payload != "Bool"):
            raise RepresentationError("expected Int-to-Bool members")
        contract = target(graph, operation, "contract")
        if graph.store.get(contract).payload != [[]]:
            raise RepresentationError("expected a quiet effect contract")
        callee = positions[row[3]["local_call"]]
        body = json.loads(row[2]["literal"])
        match body:
            case ["if", ["eq", ["argument", 0], ["literal", 0]],
                  ["literal", bool(base)], ["pin", 0, ["sub", ["argument", 0], ["literal", int(stride)]]]]:
                if type(stride) is not int or stride not in (0, 1) or callee == name:
                    raise RepresentationError("unsupported recursive argument or edge")
            case _:
                raise RepresentationError("expected zero guard and one recursive branch")
        definitions[name] = {"callee": callee, "base": base, "stride": stride,
                             "contract": contract, "member": members[name], "position": position}
    return {"group": group, "snapshot": graph.snapshot.root_hash, "definitions": definitions,
            "group_payload_sha256": sha256(canonical_bytes(payload)).hexdigest()}


def generate(subject):
    pieces = ["import Lean", "",
              f'def groupIdentity : String := "{subject["group"]}"',
              f'def semanticRoot : String := "{subject["snapshot"]}"', "",
              "mutual"]
    for name in NAMES:
        spec = subject["definitions"][name]
        base = str(spec["base"]).lower()
        pieces += [
            f"  def {name} (n : Nat) : Bool :=",
            f"    if n = 0 then {base} else {spec['callee']} (n - {spec['stride']})",
            "  termination_by n",
            "  decreasing_by omega",
            "",
        ]
    pieces += ["end", ""]
    pieces += ["""
def parityModel : Nat → Bool
  | 0 => true
  | n + 1 => !parityModel n

theorem pairAgrees (n : Nat) :
    evenMember n = parityModel n ∧ oddMember n = !parityModel n := by
  induction n with
  | zero => simp [evenMember, oddMember, parityModel]
  | succ n ih =>
    have stepEven : evenMember (n + 1) = oddMember n := by
      rw [evenMember]
      simp
    have stepOdd : oddMember (n + 1) = evenMember n := by
      rw [oddMember]
      simp
    rw [stepEven, stepOdd]
    simp [parityModel, ih.1, ih.2]

#print axioms evenMember
#print axioms oddMember
#print axioms pairAgrees

def main : IO Unit :=
  for n in List.range 16 do
    IO.println s!"{evenMember n},{oddMember n}"
""".lstrip()]
    return "\n".join(pieces)


def run_lean(path, *flags, expected=None):
    result = subprocess.run([*LEAN, *flags, path.name], cwd=path.parent, text=True, capture_output=True, timeout=40)
    if expected is None and result.returncode != 0:
        raise AssertionError((result.stdout, result.stderr))
    if expected is not None and (result.returncode == 0 or expected not in result.stdout):
        raise AssertionError((expected, result.returncode, result.stdout, result.stderr))
    return result.stdout.strip().splitlines()


def exhausted(graph, name, value, fuel):
    try:
        observe(graph, name, (value,), fuel=fuel)
    except FuelExhausted:
        return
    raise AssertionError(("fuel cutoff did not distinguish an unfinished path", name, value, fuel))


def verify(directory):
    source = program()
    coverage = {}
    for policy in ("keyed", "structural"):
        graph = compile_program(source, policy)
        subject = extract(graph)
        target_path = directory / "Generated.lean"
        code = generate(subject)
        target_path.write_text(code, encoding="utf-8")
        audits = run_lean(target_path)
        runtime = run_lean(target_path, "--run")[-len(TEST_INPUTS):]
        actual = []
        for n in TEST_INPUTS:
            pair = (n % 2 == 0, n % 2 == 1)
            results = tuple(observe(graph, member, (n,), fuel=n+1) for member in NAMES)
            if results != tuple((value, ()) for value in pair):
                raise AssertionError((n, results, pair))
            actual.append(",".join(str(value).lower() for value in pair))
            for member in NAMES:
                exhausted(graph, member, n, n)
        if runtime != actual:
            raise AssertionError((policy, runtime, actual))
        for value in (-1, -17):
            for member in NAMES:
                exhausted(graph, member, value, 32)
        coverage[policy] = {"subject": subject, "lean_source_sha256": sha256(code.encode()).hexdigest(),
                            "lean_audit": audits, "native_values": actual,
                            "domain": "natural inputs represented by nonnegative Int",
                            "negative_source_inputs_exhaust_fuel": [-1, -17]}

    mutations = {}
    for label, body, expected in (
        ("no_measure_decrease", f'True if n == 0 else pin("{NAMES[1]}", n - 0)', "omega"),
        ("changed_base_result", f'False if n == 0 else pin("{NAMES[1]}", n - 1)', "unsolved goals"),
    ):
        graph = compile_program(replace_body(source, NAMES[0], body), "keyed")
        subject = extract(graph)
        code = generate(subject)
        path = directory / "Rejected.lean"
        path.write_text(code, encoding="utf-8")
        run_lean(path, expected=expected)
        mutations[label] = {"group": subject["group"], "lean_rejected": True, "diagnostic_marker": expected}
    return coverage, mutations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-mutual-proof-") as scratch:
        variants, controls = verify(Path(scratch))
    version = subprocess.check_output([*LEAN, "--version"], text=True).strip()
    options.output.write_text(json.dumps({"format": "rt32-mutual-termination/1", "lean": version,
        "python": sys.version.split()[0], "case_inputs": TEST_INPUTS, "variants": variants,
        "controls": controls}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
