"""Generate and kernel-check ordered effects for one exact mutually recursive SPG fragment."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sibling = spec_from_file_location("quiet_mutual", HERE.parent / "MUTUAL-TERMINATION-01" / "run.py")
quiet = module_from_spec(sibling)
sibling.loader.exec_module(quiet)

from src.semantic_graph import canonical_bytes
from src.spg_admission import validate
from src.spg_representation import Implementation, Operation, Program, RepresentationError, compile_program, observe


MEMBERS = quiet.NAMES
PHASES = dict(zip(MEMBERS, ("even", "odd"), strict=True))
CONTRACT_MAX = 15
OBSERVATION_MAX = 19


def oracle(name, count):
    start = MEMBERS.index(name)
    surrounding = [PHASES[MEMBERS[(start + offset) % 2]] for offset in range(count)]
    value = (start + count) % 2
    terminal = PHASES[MEMBERS[value]]
    trace = tuple(f"enter_{phase}" for phase in surrounding) + (f"base_{terminal}",) + tuple(
        f"exit_{phase}" for phase in reversed(surrounding)
    )
    return value, trace


def program(*, reorder=False, stride=1, narrow=False):
    contracts = {}
    operations = {}
    implementations = {}
    for value, name in enumerate(MEMBERS):
        phase = PHASES[name]
        callee = MEMBERS[1-value]
        count = CONTRACT_MAX - int(narrow and value == 0)
        contracts[name] = tuple(oracle(name, n)[1] for n in range(count+1))
        operations[name] = Operation(name, ("Int",), "Int", name)
        enter = f'emit("enter_{phase}", pin("{callee}", n - {stride}))'
        leave = f'emit("exit_{phase}", 0)'
        left, right = (leave, enter) if reorder and value == 0 else (enter, leave)
        body = f'emit("base_{phase}", {value}) if n == 0 else ({left} + {right})'
        implementations[name] = Implementation(name, ("n",), body, phase)
    return Program(contracts, operations, implementations, {})


def extract(graph):
    members = {name: graph.snapshot.mapping[f"implementation:{name}"] for name in MEMBERS}
    if any(graph.store.get(member).kind != "rt05-recursive-member-v1" for member in members.values()):
        raise RepresentationError("expected recursive member values")
    groups = {quiet.target(graph, member, "member_of") for member in members.values()}
    if len(groups) != 1:
        raise RepresentationError("expected one exact mutual group")
    group, = groups
    payload = graph.store.get(group).payload
    positions = {graph.store.get(member).payload["position"]: name for name, member in members.items()}
    if len(payload) != 2 or set(positions) != {0, 1}:
        raise RepresentationError("two exact members required")
    contracts = {}
    data = {}
    for index, name in sorted(positions.items()):
        row = payload[index]["body"]
        if (len(row) != 4 or row[0] != {"literal": "rt05-spg-body-v1"}
                or set(row[1]) != {"external"} or set(row[2]) != {"literal"}
                or set(row[3]) != {"local_call"}):
            raise RepresentationError("unexpected recursive body schema")
        operation = row[1]["external"]
        types = graph.store.get(quiet.target(graph, operation, "interface")).payload
        if ([graph.store.get(kind).payload for kind in types["parameters"]] != ["Int"]
                or graph.store.get(types["result"]).payload != "Int"):
            raise RepresentationError("expected Int-to-Int signature")
        address = quiet.target(graph, operation, "contract")
        observed = {tuple(trace) for trace in graph.store.get(address).payload}
        expected = {oracle(name, n)[1] for n in range(CONTRACT_MAX+1)}
        if observed != expected:
            raise RepresentationError("finite trace contract differs from the declared domain")
        contracts[name] = address
        callee = positions[row[3]["local_call"]]
        if callee == name:
            raise RepresentationError("expected a cross-member call")

        body = json.loads(row[2]["literal"])
        match body:
            case ["if", ["eq", ["argument", 0], ["literal", 0]],
                  ["emit", str(base), ["literal", int(value)]], ["add", left, right]]:
                pass
            case _:
                raise RepresentationError("unexpected zero guard or integer base")
        order = "enter-then-exit"
        if left == ["emit", f"exit_{PHASES[name]}", ["literal", 0]]:
            left, right = right, left
            order = "exit-then-enter"
        match left, right:
            case (["emit", str(enter), ["pin", 0, ["sub", ["argument", 0], ["literal", int(stride)]]]],
                  ["emit", str(exit_event), ["literal", 0]]):
                if type(value) is not int or type(stride) is not int or stride not in (0, 1):
                    raise RepresentationError("unexpected literal")
            case _:
                raise RepresentationError("unexpected call or ordered event expression")
        data[name] = {"member": members[name], "position": index, "callee": callee, "base_value": value,
                      "base_event": base, "enter": enter, "exit": exit_event, "stride": stride, "order": order}
    return {"group": group, "group_sha256": sha256(canonical_bytes(payload)).hexdigest(),
            "snapshot": graph.snapshot.root_hash, "contracts": contracts, "members": data}


def generate(subject):
    lines = [f'def fixtureGroup : String := "{subject["group"]}"',
             f'def fixtureRoot : String := "{subject["snapshot"]}"', "", "mutual"]
    for name in MEMBERS:
        spec = subject["members"][name]
        entered = json.dumps(spec["enter"])
        exit_event = json.dumps(spec["exit"])
        base = json.dumps(spec["base_event"])
        if spec["order"] == "enter-then-exit":
            traces = f"[{entered}] ++ result.2 ++ [{exit_event}]"
        else:
            traces = f"[{exit_event}] ++ [{entered}] ++ result.2"
        lines += [
            f"  def {name} (n : Nat) : Int × List String :=",
            f"    if n = 0 then ({spec['base_value']}, [{base}]) else",
            f"      let result := {spec['callee']} (n - {spec['stride']})",
            f"      (result.1, {traces})",
            "  termination_by n",
            "  decreasing_by omega",
            "",
        ]
    lines.append("end")
    return (HERE / "TraceModel.lean.in").read_text(encoding="utf-8").replace("-- @DEFINITIONS@", "\n".join(lines))


def verify(directory):
    ledger = {}
    for policy in ("keyed", "structural"):
        graph = compile_program(program(), policy)
        try:
            validate(graph)
        except RepresentationError as error:
            assert str(error) == "unsupported implementation value"
            admission = str(error)
        else:
            raise AssertionError("the acyclic admission boundary changed")
        subject = extract(graph)
        source = generate(subject)
        artifact = directory / "MutualEffects.lean"
        artifact.write_text(source, encoding="utf-8")
        axiom_audit = quiet.run_lean(artifact)
        assert axiom_audit and all("sorryAx" not in line for line in axiom_audit)
        observations = []
        cutoff = 2 * (OBSERVATION_MAX+1)
        lean = quiet.run_lean(artifact, "--run")[-cutoff:]
        outside = 0
        for n in range(OBSERVATION_MAX+1):
            for member in MEMBERS:
                value, trace = observe(graph, member, (n,), fuel=n+1)
                assert (value, trace) == oracle(member, n)
                assert len(trace) == 2*n+1
                admitted = list(trace) in graph.store.get(subject["contracts"][member]).payload
                assert admitted == (n <= CONTRACT_MAX)
                outside += not admitted
                observations.append(f"{value}|{','.join(trace)}")
                quiet.exhausted(graph, member, n, n)
        assert lean == observations
        ledger[policy] = {"subject": subject, "axioms": axiom_audit, "out_of_finite_contract": outside,
                          "acyclic_admission": admission,
                          "observations": len(observations),
                          "generated_sha256": sha256(source.encode()).hexdigest(),
                          "trace_sha256": sha256("\n".join(observations).encode()).hexdigest()}

    controls = {}
    for label, options, diagnostic in (
        ("swap_effect_order", {"reorder": True}, "unsolved goals"),
        ("zero_stride", {"stride": 0}, "omega"),
    ):
        graph = compile_program(program(**options), "keyed")
        subject = extract(graph)
        path = directory / "Rejected.lean"
        path.write_text(generate(subject), encoding="utf-8")
        quiet.run_lean(path, expected=diagnostic)
        controls[label] = {"subject": subject["group"], "kernel_diagnostic": diagnostic}
        if label == "swap_effect_order":
            member = MEMBERS[0]
            actual = observe(graph, member, (3,), fuel=4)
            expected = oracle(member, 3)
            assert actual[0] == expected[0] and actual[1] != expected[1] and sorted(actual[1]) == sorted(expected[1])
            controls[label]["same_value_and_event_multiset"] = True
    try:
        extract(compile_program(program(narrow=True), "keyed"))
    except RepresentationError as exc:
        assert "finite trace contract differs" in str(exc)
        controls["changed_contract"] = {"rejected_by": str(exc)}
    else:
        raise AssertionError("changed contract admitted")
    return {"format": "rt32-mutual-effects/1", "python": sys.version.split()[0],
            "lean": subprocess.check_output([*quiet.LEAN, "--version"], text=True).strip(),
            "highest_contract_input": CONTRACT_MAX, "highest_observed_input": OBSERVATION_MAX,
            "encodings": ledger, "controls": controls}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    opts = parser.parse_args()
    with TemporaryDirectory(prefix="rt32-mutual-effects-") as directory:
        result = verify(Path(directory))
    opts.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
