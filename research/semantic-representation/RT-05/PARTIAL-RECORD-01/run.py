#!/usr/bin/env python3
"""Compare field-order and phase-specific ownership graphs to native Rust drops."""

from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore

FIELDS = ("alpha", "beta", "gamma")
SLOTS = dict(zip(FIELDS, range(3)))
ORDERS = tuple(permutations(FIELDS))
SHAPES = ("direct", "staged")
POLICIES = ("separate_orders", "canonical_fields", "init_for_both", "schema_for_both", "reverse_all",
            "forward_abort", "schema_abort")
RUST_PREFIX = """
use std::cell::RefCell;

struct Token<'a> { id: i32, events: &'a RefCell<Vec<i32>> }
impl Drop for Token<'_> {
    fn drop(&mut self) { self.events.borrow_mut().push(-1 - self.id); }
}
fn acquire(slot: i32, fail: u8, events: &RefCell<Vec<i32>>) -> Result<Token<'_>, i32> {
    events.borrow_mut().push(slot + 1);
    if fail & (1 << slot) != 0 {
        return Err(slot + 1);
    }
    events.borrow_mut().push(slot + 11);
    Ok(Token { id: slot, events })
}
"""


def emit(path, corpus):
    program = [RUST_PREFIX]
    for index, declaration_order in enumerate(ORDERS):
        fields = ", ".join(f"{name}: Token<'a>" for name in declaration_order)
        program.append(f"struct Record_{index}<'a> {{ {fields} }}\n")
    for index, decl, init, shape in corpus:
        record = f"Record_{ORDERS.index(decl)}"
        if shape == "direct":
            operands = ", ".join(f"{name}: acquire({SLOTS[name]}, fail, events)?" for name in init)
            setup = f"let record = {record} {{ {operands} }};"
        else:
            staging = [f"let tmp_{name} = acquire({SLOTS[name]}, fail, events)?;" for name in init]
            values = ", ".join(f"{name}: tmp_{name}" for name in FIELDS)
            setup = "\n        ".join([*staging, f"let record = {record} {{ {values} }};"])
        moves = "\n".join(f"            {slot} => Some(record.{name})," for name, slot in SLOTS.items())
        program.append(f"""
fn probe_{index}(fail: u8, preserve: u8, events: &RefCell<Vec<i32>>) -> Result<(), i32> {{
    let transferred = {{
        {setup}
        events.borrow_mut().push(30);
        match preserve {{
{moves}
            _ => None,
        }}
    }};
    events.borrow_mut().push(40);
    drop(transferred);
    Ok(())
}}
""")
    programs = ", ".join(f"probe_{index}" for index, *_ in corpus)
    program.append(f"""
fn main() {{
    let probes: &[fn(u8, u8, &RefCell<Vec<i32>>) -> Result<(), i32>] = &[{programs}];
    for (index, probe) in probes.iter().enumerate() {{
        for fail in 0..8 {{
            for preserve in 0..4 {{
                let events = RefCell::new(Vec::new());
                let status = match probe(fail, preserve, &events) {{
                    Ok(()) => 0,
                    Err(field) => field,
                }};
                println!("[{{}}, {{}} , {{}} , [{{}}, {{:?}}]]", index, fail, preserve, status, events.into_inner());
            }}
        }}
    }}
}}
""")
    path.write_text("\n".join(program), encoding="utf-8")


def reference(decl, init, fail, preserve):
    # Derive the successful prefix and expected release schedule from the input permutation.
    ids = [SLOTS[field] for field in init]
    failed = next((index for index, slot in enumerate(ids) if fail & (2**slot)), len(ids))
    acquired = ids[:failed]
    prefix = [event for slot in acquired for event in (slot + 1, slot + 11)]
    if failed != len(ids):
        failing_slot = ids[failed] + 1
        return [failing_slot, [*prefix, failing_slot, *(-1 - slot for slot in reversed(acquired))]]
    released = [-1 - SLOTS[field] for field in decl if SLOTS[field] != preserve]
    later = [-1 - preserve] if preserve < len(FIELDS) else []
    return [0, [*prefix, 30, *released, 40, *later]]


def graph(store, decl, init, policy):
    abort = "reverse_acquired"
    if policy == "canonical_fields":
        captures, destruction = FIELDS, FIELDS
    elif policy == "init_for_both":
        captures, destruction = init, init
    elif policy == "schema_for_both":
        captures, destruction = decl, decl
    elif policy == "reverse_all":
        captures, destruction = init, init[::-1]
    else:
        captures, destruction = init, decl
    if policy == "forward_abort":
        abort = "forward_acquired"
    elif policy == "schema_abort":
        abort = "declaration_filtered"
    payload = {
        "kind": "owned-named-record",
        "fields": {name: {"slot": slot, "type": "linear-token"} for name, slot in SLOTS.items()},
        "acquire_order": captures, "complete_drop_order": destruction, "abort_drop": abort,
        "commit_after_all": True, "transfer_removes_completed_obligation": True,
    }
    return store.put("rt05-owned-record-projection-v1", payload)


def evaluate(body, fail, preserve):
    events, pending = [], []
    semantics = body["fields"]
    for name in body["acquire_order"]:
        slot = semantics[name]["slot"]
        events.append(slot + 1)
        if fail & (1 << slot):
            if body["abort_drop"] == "forward_acquired":
                release = pending
            elif body["abort_drop"] == "declaration_filtered":
                release = [semantics[slot_name]["slot"] for slot_name in body["complete_drop_order"]
                           if semantics[slot_name]["slot"] in pending]
            else:
                release = reversed(pending)
            events.extend(-1 - resource for resource in release)
            return [slot + 1, events]
        events.append(slot + 11)
        pending.append(slot)

    events.append(30)
    transferred = None
    for name in body["complete_drop_order"]:
        slot = semantics[name]["slot"]
        if slot == preserve:
            transferred = slot
        else:
            events.append(-1 - slot)
    events.append(40)
    if transferred is not None:
        events.append(-1 - transferred)
    return [0, events]


def check_ownership(observation, preserve):
    status, trace = observation
    acquired = {event - 11 for event in trace if 11 <= event <= 13}
    drops = [-event - 1 for event in trace if event < 0]
    assert len(drops) == len(acquired) and set(drops) == acquired
    if status:
        assert 30 not in trace and 40 not in trace
        assert status - 1 not in acquired
    else:
        assert acquired == set(SLOTS.values()) and trace.index(30) < trace.index(40)
        assert trace[trace.index(40) + 1:] == ([-1 - preserve] if preserve < len(FIELDS) else [])


def run(directory):
    corpus = [(index, decl, init, shape)
              for index, (decl, init, shape) in enumerate(product(ORDERS, ORDERS, SHAPES))]
    source = directory / "owned_records.rs"
    emit(source, corpus)
    native = {}
    for level in (0, 3):
        exe = directory / f"owned-{level}"
        subprocess.run(["rustc", "--edition=2021", "-A", "non_camel_case_types", "-C", f"opt-level={level}",
                        str(source), "-o", str(exe)], check=True)
        output = subprocess.check_output([str(exe)], text=True)
        rows = [json.loads(line) for line in output.splitlines()]
        native[level] = {(index, fail, preserve): observed for index, fail, preserve, observed in rows}
        assert len(rows) == len(native[level]) == len(corpus) * 32
    assert native[0] == native[3]

    store = ContentStore()
    metrics = {policy: Counter() for policy in POLICIES}
    addresses = {policy: set() for policy in POLICIES}
    evidence = []
    for index, decl, init, shape in corpus:
        exact = {policy: graph(store, decl, init, policy) for policy in POLICIES}
        for policy, key in exact.items():
            addresses[policy].add(key)
        observations = []
        for fail, preserve in product(range(8), range(4)):
            actual = native[0][index, fail, preserve]
            expected = reference(decl, init, fail, preserve)
            assert actual == expected
            check_ownership(actual, preserve)
            observations.append(actual)
            for policy, key in exact.items():
                lowered = evaluate(store.get(key).payload, fail, preserve)
                if lowered != expected:
                    phase = "abort_mismatch" if expected[0] else "completed_mismatch"
                    metrics[policy][phase] += 1
        evidence.append({"case": index, "declaration": decl, "initializer": init, "shape": shape,
                         "addresses": exact, "observations": observations})
    assert not metrics["separate_orders"]
    assert all(metrics[policy]["completed_mismatch"] == 0 for policy in ("forward_abort", "schema_abort"))
    assert all(metrics[policy] for policy in POLICIES if policy != "separate_orders")
    for direct, staged in zip(evidence[::2], evidence[1::2]):
        assert direct["observations"] == staged["observations"] and direct["addresses"] == staged["addresses"]
    return {
        "schema": "llmlang-rt05-partial-record/1", "python": platform.python_version(),
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": len(corpus), "native_observations": sum(map(len, native.values())),
        "oracle_vectors": len(native[0]),
        "paired_source_shapes": len(corpus) // 2, "failure_masks": list(range(8)),
        "transfer_roles": ["alpha", "beta", "gamma", "none"],
        "metrics": {policy: {"classes": len(addresses[policy]),
                             "abort_mismatch": metrics[policy]["abort_mismatch"],
                             "completed_mismatch": metrics[policy]["completed_mismatch"]}
                    for policy in POLICIES},
        "observations": evidence,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-owned-records-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
