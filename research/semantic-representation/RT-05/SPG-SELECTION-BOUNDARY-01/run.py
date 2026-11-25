"""Distinguish persisted values, reachable objects and typed SPG selections."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.persistence import PersistenceError, dumps_graph, loads_graph
from src.semantic_graph import RelationStore, canonical_bytes, digest, make_snapshot
from src.spg_admission import validate
from src.spg_representation import Graph, RepresentationError, compile_program, observe
from tests.test_spg_representation import dispatch_program

BASELINE = "f62bdbced7488ecf244f3028dd51826c5ddfd3b0"
INPUTS = (-2, 0, 3)


def closure(store, addresses):
    remaining = list(addresses)
    found = set()
    while remaining:
        address = remaining.pop()
        if address not in found:
            remaining.extend(dep.target_hash for dep in store.get(address).dependencies)
            found.add(address)
    return found


def omit(selections, *slots):
    return {slot: address for slot, address in selections.items() if slot not in slots}


def physically_filter(raw, removed):
    payload = json.loads(raw)["payload"]
    payload["values"] = [row for row in payload["values"] if row["value_hash"] not in removed]
    return canonical_bytes({"payload": payload, "checksum": digest(payload)}) + b"\n"


def inspect(archive, original, addresses, expected):
    info = {"archive_sha256": hashlib.sha256(archive).hexdigest(),
            "selection_root": original.root_hash, "selected_slots": dict(original.selections)}
    try:
        store, _, snapshots = loads_graph(archive)
    except PersistenceError as error:
        assert expected == "persistence-failure"
        return info | {"persistence": "refused", "typed_admission": "not-run", "reason": str(error)}
    snapshot, = snapshots
    assert snapshot == original
    selected = set(snapshot.mapping.values())
    reachable = closure(store, selected)
    graph = Graph(store, snapshot)
    observations = {}
    try:
        validate(graph)
    except RepresentationError as error:
        assert expected == str(error), (expected, str(error))
        disposition = {"typed_admission": "refused", "reason": str(error)}
    else:
        assert expected == "admitted", expected
        disposition = {"typed_admission": "admitted"}
        for name in ("direct", "late"):
            if f"implementation:{name}" in snapshot.mapping:
                observations[name] = [observe(graph, name, (word,)) for word in INPUTS]
    return info | {
        "persistence": "admitted", **disposition, "stored_values": len(store),
        "reachable_values": len(reachable), "selected_values": len(selected),
        "address_membership": {
            name: {"stored": address in store, "reachable": address in reachable,
                   "selected": address in selected}
            for name, address in addresses.items()
        },
        "observations": observations,
    }


def exercise():
    fixture = dispatch_program()
    graph = compile_program(fixture)
    alternate = compile_program(replace(fixture, bindings={"provider": "alternate"}))
    base = graph.snapshot.mapping
    alternate_slots = alternate.snapshot.mapping
    primary = base["implementation:primary"]
    extra = base["implementation:alternate"]
    contract = base["contract:provider"]
    assert contract == base["contract:forward"]
    assert alternate_slots["implementation:primary"] == primary
    cases = {
        "baseline": (graph, base, set(), "admitted"),
        "remove-unused-selection": (graph, omit(base, "implementation:alternate"), set(), "admitted"),
        "rename-selected-primary": (
            graph, omit(base, "implementation:primary") | {"implementation:retained": primary}, set(), "admitted",
        ),
        "extra-alias-to-primary": (
            graph, base | {"implementation:second_name": primary}, set(), "admitted",
        ),
        "selected-contract-alias-remains": (graph, omit(base, "contract:provider"), set(), "admitted"),
        "no-selected-contract": (
            graph, omit(base, "contract:provider", "contract:forward"), set(), "contract missing from selection",
        ),
        "unbind-and-remove-late-body": (
            graph, omit(base, "binding:provider", "implementation:late"), set(), "admitted",
        ),
        "late-body-without-binding": (
            graph, omit(base, "binding:provider"), set(), "operation binding missing",
        ),
        "binding-target-not-selected": (
            graph, omit(base, "implementation:primary"), set(), "binding provider mismatch",
        ),
        "pin-target-not-selected": (
            alternate, omit(alternate_slots, "implementation:primary"), set(), "exact call target missing from selection",
        ),
        "owner-operation-not-selected": (
            graph, omit(base, "operation:provider"), set(), "body owner missing from selection",
        ),
        "wrong-selected-kind": (
            graph, base | {"implementation:primary": base["operation:provider"]}, set(),
            "unsupported implementation value",
        ),
        "prune-unreachable-storage": (graph, omit(base, "implementation:alternate"), {extra}, "admitted"),
        "missing-physical-reference": (graph, base, {primary}, "persistence-failure"),
    }
    rows = {}
    for name, (original, selections, removed, expected) in cases.items():
        snapshot = make_snapshot(selections)
        archive = dumps_graph(original.store, RelationStore(), (snapshot,))
        if removed:
            archive = physically_filter(archive, removed)
        rows[name] = inspect(archive, snapshot, {
            "primary": primary, "alternate": extra, "provider_contract": contract,
            "provider_operation": base["operation:provider"],
            "active_binding": original.snapshot.mapping["binding:provider"],
        }, expected)
    for name in ("pin-target-not-selected", "binding-target-not-selected"):
        assert rows[name]["address_membership"]["primary"] == {
            "stored": True, "reachable": True, "selected": False,
        }
    assert rows["late-body-without-binding"]["address_membership"]["active_binding"] == {
        "stored": True, "reachable": False, "selected": False,
    }
    assert rows["remove-unused-selection"]["address_membership"]["alternate"] == {
        "stored": True, "reachable": False, "selected": False,
    }
    keep = rows["remove-unused-selection"]
    dropped = rows["prune-unreachable-storage"]
    assert keep["archive_sha256"] != dropped["archive_sha256"]
    assert keep["selection_root"] == dropped["selection_root"] and keep["observations"] == dropped["observations"]
    assert rows["rename-selected-primary"]["selection_root"] != rows["baseline"]["selection_root"]
    for row in rows.values():
        for observations in row.get("observations", {}).values():
            assert observations == [(value + 1, ("first", "last")) for value in INPUTS]
    return rows


def main():
    pins = {}
    for relative in (
        "src/spg_representation.py", "src/spg_admission.py", "src/semantic_graph.py",
        "src/persistence.py", "src/recursive_identity.py", "tests/test_spg_representation.py",
    ):
        path = PROTOTYPE / relative
        name = str(path.relative_to(ROOT))
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT)
        assert archived == path.read_bytes()
        pins[name] = hashlib.sha256(archived).hexdigest()
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": pins, "inputs": INPUTS, "cases": exercise(),
    }, indent=2))


if __name__ == "__main__":
    main()
