#!/usr/bin/env python3
"""Compare named-record SPG projections on shared native Rust and Python fixtures."""

import ast
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore

FIELDS = ("alpha", "beta", "gamma")
VALUES = {"alpha": 11, "beta": 22, "gamma": 33}
OPERANDS = ("literal", "trace", "maybe")
POLICIES = ("surface_order", "ordered_effects", "field_map")
RUST_PREFIX = """
#[derive(Debug)]
struct Record { gamma: i64, alpha: i64, beta: i64 }
fn trace(field: u8, value: i64, events: &mut Vec<u8>) -> i64 {
    events.push(field + 1);
    value
}
fn maybe(field: u8, value: i64, mask: u8, events: &mut Vec<u8>) -> Result<i64, u8> {
    events.push(field + 4);
    if mask & (1 << field) != 0 { Err(field + 1) } else { Ok(value) }
}
"""
PYTHON_PREFIX = """
from dataclasses import dataclass
import json

@dataclass
class Record:
    beta: int
    gamma: int
    alpha: int

class Stop(Exception):
    pass

def trace(field, value, events):
    events.append(field + 1)
    return value

def maybe(field, value, mask, events):
    events.append(field + 4)
    if mask & (1 << field):
        raise Stop(field + 1)
    return value
"""
RUST_BODY = re.compile(r"\n    Ok\(Record\s*\{(?P<fields>[^{}]+)\}\)\n")
RUST_FIELD = re.compile(
    r"\s*(?P<name>[a-z]+)\s*:\s*(?P<term>\d+|trace\(\d+, \d+, events\)|maybe\(\d+, \d+, mask, events\)\?)\s*"
)


def sha_bytes(data):
    return sha256(data).hexdigest()


def validate(fields):
    names = [name for name, _, _, _ in fields]
    if len(names) != len(FIELDS) or set(names) != set(FIELDS):
        raise ValueError("Named record requires each schema field exactly once")
    if any(index != FIELDS.index(name) for name, _, index, _ in fields):
        raise ValueError("Observable operation refers to another field")
    return fields


def rust_lower(source):
    match = RUST_BODY.fullmatch(source)
    if not match:
        raise ValueError("Unsupported Rust record expression")
    terms = re.split(r",(?![^()]*\))", match["fields"].strip().removesuffix(","))
    result = []
    for term in terms:
        field = RUST_FIELD.fullmatch(term)
        if not field:
            raise ValueError("Unsupported Rust field initializer")
        name, operand = field["name"], field["term"]
        if operand.isdecimal():
            result.append((name, "literal", FIELDS.index(name) if name in FIELDS else -1, int(operand)))
        else:
            index, value = map(int, re.findall(r"\d+", operand))
            result.append((name, operand.split("(", 1)[0], index, value))
    return validate(result)


def python_lower(source):
    root = ast.parse(source).body
    if (len(root) != 1 or not isinstance(root[0], ast.FunctionDef) or len(root[0].body) != 1
            or not isinstance(root[0].body[0], ast.Return)):
        raise ValueError("Unsupported Python record fixture")
    record = root[0].body[0].value
    if not isinstance(record, ast.Call) or ast.unparse(record.func) != "Record" or record.args:
        raise ValueError("Use explicit named record fields")
    result = []
    for field in record.keywords:
        operand, name = field.value, field.arg
        if isinstance(operand, ast.Constant) and type(operand.value) is int:
            result.append((name, "literal", FIELDS.index(name) if name in FIELDS else -1, operand.value))
            continue
        if not isinstance(operand, ast.Call) or operand.keywords:
            raise ValueError("Unsupported Python field initializer")
        function = ast.unparse(operand.func)
        args = operand.args
        suffix = [ast.unparse(arg) for arg in args[2:]]
        if (function, suffix) not in (("trace", ["events"]), ("maybe", ["mask", "events"])):
            raise ValueError("Unsupported Python initializer operand")
        if not all(isinstance(arg, ast.Constant) and type(arg.value) is int for arg in args[:2]):
            raise ValueError("Expected literal initializer operands")
        result.append((name, function, args[0].value, args[1].value))
    return validate(result)


def rust_terms(fields):
    terms = []
    for name, operand, index, value in fields:
        value_code = {
            "literal": str(value),
            "trace": f"trace({index}, {value}, events)",
            "maybe": f"maybe({index}, {value}, mask, events)?",
        }[operand]
        terms.append(f"{name}: {value_code}")
    return "\n    Ok(Record { " + ", ".join(terms) + ", })\n"


def python_terms(index, fields):
    terms = []
    for name, operand, position, value in fields:
        expression = {
            "literal": str(value),
            "trace": f"trace({position}, {value}, events)",
            "maybe": f"maybe({position}, {value}, mask, events)",
        }[operand]
        terms.append(f"        {name}={expression},")
    return f"def case_{index}(mask, events):\n    return Record(\n" + "\n".join(terms) + "\n    )\n"


def canonical(store, fields, policy):
    values = {name: {"type": "I64", "term": operand, "field_bit": index, "value": value}
              for name, operand, index, value in fields}
    if policy == "surface_order":
        order = [name for name, _, _, _ in fields]
    elif policy == "ordered_effects":
        order = [name for name, operand, _, _ in fields if operand != "literal"]
    else:
        order = sorted(values)
    artifact = {"kind": "named-record", "slots": values, "evaluation": order,
                "completion": "publish-on-success", "abrupt": "propagate-first-failure"}
    return store.put("rt05-record-projection-v1", artifact)


def evaluate(graph, mask):
    log = []
    for name in graph["evaluation"]:
        field = graph["slots"][name]
        if field["term"] == "literal":
            continue
        index = field["field_bit"]
        if field["term"] == "trace":
            log.append(index + 1)
        else:
            log.append(index + 4)
            if mask & (1 << index):
                return [None, index + 1, log]
    return [[graph["slots"][slot]["value"] for slot in FIELDS], None, log]


def oracle(order, choices, mask):
    effects = [(FIELDS.index(label), choices[label]) for label in order if choices[label] != "literal"]
    failure = next((index for index, (field, term) in enumerate(effects)
                    if term == "maybe" and mask & (2**field)), None)
    prefix = effects if failure is None else effects[:failure + 1]
    trace = [field + (1 if term == "trace" else 4) for field, term in prefix]
    if failure is not None:
        return [None, effects[failure][0] + 1, trace]
    return [[11, 22, 33], None, trace]


def emit(universe, directory):
    rust = [RUST_PREFIX]
    python = [PYTHON_PREFIX]
    for index, order, choices, fields in universe:
        rust_body = rust_terms(fields)
        py_function = python_terms(index, fields)
        assert rust_lower(rust_body) == python_lower(py_function) == fields
        rust.append(f"fn case_{index}(mask: u8, events: &mut Vec<u8>) -> Result<Record, u8> {{"
                    + rust_body + "}\n")
        python.append(py_function)

    rust.extend(["fn main() {",
                 "    let cases: &[fn(u8, &mut Vec<u8>) -> Result<Record, u8>] = &["])
    rust.extend(f"        case_{index}," for index, *_ in universe)
    rust.append("""
    ];
    for (index, case) in cases.iter().enumerate() {
        for mask in 0..8 {
            let mut events = Vec::new();
            match case(mask, &mut events) {
                Ok(record) => println!("[{}, {}, [[{}, {}, {}], null, {:?}]]", index, mask,
                                      record.alpha, record.beta, record.gamma, events),
                Err(field) => println!("[{}, {}, [null, {}, {:?}]]", index, mask, field, events),
            }
        }
    }
}
""")
    python.append("CASES = (" + ", ".join(f"case_{index}" for index, *_ in universe) + ")")
    python.append("""
for index, case in enumerate(CASES):
    for mask in range(8):
        events = []
        try:
            value = case(mask, events)
            observation = [[value.alpha, value.beta, value.gamma], None, events]
        except Stop as error:
            observation = [None, error.args[0], events]
        print(json.dumps([index, mask, observation]))
""")
    sources = {"rust": directory / "records.rs", "python": directory / "records.py"}
    sources["rust"].write_text("\n".join(rust), encoding="utf-8")
    sources["python"].write_text("\n".join(python), encoding="utf-8")
    return sources


def observations(command):
    output = subprocess.run(command, capture_output=True, check=True, text=True).stdout
    result = [json.loads(line) for line in output.splitlines()]
    assert len(result) == len({(entry[0], entry[1]) for entry in result})
    return {(index, mask): outcome for index, mask, outcome in result}


def reject_invalid():
    examples = {
        "missing": ([("alpha", "literal", 0, 11), ("beta", "trace", 1, 22)]),
        "repeated": ([("alpha", "literal", 0, 11), ("alpha", "literal", 0, 11),
                      ("gamma", "maybe", 2, 33)]),
        "unknown": ([("alpha", "literal", 0, 11), ("delta", "literal", 1, 22),
                     ("gamma", "maybe", 2, 33)]),
        "wrong_effect_role": ([("alpha", "trace", 2, 11), ("beta", "literal", 1, 22),
                               ("gamma", "maybe", 2, 33)]),
    }
    for fields in examples.values():
        for lower, source in ((rust_lower, rust_terms(fields)), (python_lower, python_terms(0, fields))):
            try:
                lower(source)
            except ValueError:
                pass
            else:
                raise AssertionError("Malformed field inventory was admitted")
    try:
        rust_lower(rust_terms(examples["missing"] + [("gamma", "maybe", 2, 33)]).replace("?", ""))
    except ValueError:
        return sorted(examples) + ["missing_rust_propagation"]
    raise AssertionError("Rust operand without propagation was admitted")


def run(directory):
    universe = []
    for index, (order, kinds) in enumerate(product(permutations(FIELDS), product(OPERANDS, repeat=3))):
        choices = dict(zip(FIELDS, kinds))
        universe.append((index, order, choices, [(name, choices[name], FIELDS.index(name), VALUES[name])
                                                  for name in order]))
    sources = emit(universe, directory)
    native = {"cpython": observations([sys.executable, "-B", str(sources["python"])])}
    for level in (0, 3):
        executable = directory / f"rust-{level}"
        subprocess.run(["rustc", "--edition=2021", "-A", "unused_variables", "-C", f"opt-level={level}",
                        str(sources["rust"]), "-o", str(executable)], check=True)
        native[f"rust_O{level}"] = observations([str(executable)])

    store = ContentStore()
    evidence = []
    exact_mismatches = Counter()
    class_pairs = {policy: Counter() for policy in POLICIES}
    by_policy = {policy: defaultdict(list) for policy in POLICIES}
    for index, order, choices, fields in universe:
        # Lower the real generated operands again, then consume the exact stored graphs.
        rust = rust_lower(rust_terms(fields))
        python = python_lower(python_terms(index, fields))
        addresses = {policy: canonical(store, rust, policy) for policy in POLICIES}
        assert addresses == {policy: canonical(store, python, policy) for policy in POLICIES}
        values = [oracle(order, choices, mask) for mask in range(8)]
        for implementation in native.values():
            assert [implementation[index, mask] for mask in range(8)] == values
        for policy, artifact in addresses.items():
            graph = store.get(artifact).payload
            observed = [evaluate(graph, mask) for mask in range(8)]
            exact_mismatches[policy] += sum(left != right for left, right in zip(observed, values))
            by_policy[policy][artifact].append((index, json.dumps(values)))
        evidence.append({"case": index, "order": order, "operands": choices,
                         "spg": addresses, "native_and_oracle": values})

    for policy, classes in by_policy.items():
        for group in classes.values():
            for first, second in combinations(group, 2):
                verdict = "same_behavior" if first[1] == second[1] else "distinct_behavior"
                class_pairs[policy][verdict] += 1

    complete_equivalence_pairs = sum(first["native_and_oracle"] == second["native_and_oracle"]
                                     for first, second in combinations(evidence, 2))
    assert exact_mismatches["surface_order"] == exact_mismatches["ordered_effects"] == 0
    assert class_pairs["ordered_effects"]["same_behavior"] == complete_equivalence_pairs
    assert class_pairs["ordered_effects"]["distinct_behavior"] == 0
    assert class_pairs["field_map"]["distinct_behavior"] > 0
    assert exact_mismatches["field_map"] > 0
    return {
        "schema": "llmlang-rt05-named-record/1",
        "python": platform.python_version(),
        "rustc": subprocess.run(["rustc", "-Vv"], capture_output=True, check=True, text=True).stdout.splitlines(),
        "source_sha256": {name: sha_bytes(path.read_bytes()) for name, path in sources.items()},
        "runner_sha256": sha_bytes(Path(__file__).read_bytes()), "fixture_cases": len(universe),
        "input_masks": list(range(8)), "native_observations": {backend: len(data) for backend, data in native.items()},
        "observationally_equivalent_case_pairs": complete_equivalence_pairs,
        "policies": {policy: {"classes": len(by_policy[policy]),
                              "same_behavior_pairs": class_pairs[policy]["same_behavior"],
                              "distinct_behavior_pairs": class_pairs[policy]["distinct_behavior"],
                              "observation_mismatches": exact_mismatches[policy]} for policy in POLICIES},
        "malformed_controls_rejected": reject_invalid(), "observations": evidence,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-named-record-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
