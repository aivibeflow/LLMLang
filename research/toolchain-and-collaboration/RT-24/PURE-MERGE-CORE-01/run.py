"""Check the closed pure merge core with finite and typed counterexamples."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from itertools import product
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(GRAPH))
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, make_snapshot
from src.semantic_merge_core import merge_closed, pin_merge_input


def declaration(kind, name, content, **fields):
    return {"format": FORMAT, "schema_version": SCHEMA_VERSION, "kind": kind,
            "declaration_id": name, "content": content, **fields}


def envelope(selections, entries=None):
    return pin_merge_input(make_snapshot(selections), {} if entries is None else entries)


def expected(slot_case):
    base, ours, theirs = slot_case
    deltas = {value for value in (ours, theirs) if value != base}
    if base is None and ours is not None and theirs is not None:
        return "identity-lineage", None
    if len(deltas) >= 2:
        return ("delete-update" if None in deltas else "update-update"), None
    return None, next(iter(deltas), base)


def finite(store, values):
    counts = Counter()
    options = (None, *values)
    triples = tuple(product(options, repeat=3))
    one_slot = Counter()
    for candidate in triples:
        conflict, selected = expected(candidate)
        one_slot[conflict or "resolved"] += 1
    for first, second in product(triples, repeat=2):
        states = [envelope({name: value for name, value in zip(("a", "b"), staged)
                            if value is not None}) for staged in zip(first, second)]
        baseline, ours, theirs = states
        actual = merge_closed(store, baseline, ours, theirs)
        reversed_result = merge_closed(store, baseline, theirs, ours)
        assert actual.input_pins == tuple(input.exact_pin for input in states)
        truth = [expected(change) for change in (first, second)]
        conflicts = [(name, conflict) for name, (conflict, _) in zip(("a", "b"), truth) if conflict]
        if conflicts:
            assert actual.candidate is None and reversed_result.candidate is None
            assert [(conflict.subject, conflict.kind) for conflict in actual.conflicts] == conflicts
            assert reversed_result.conflicts == tuple(
                replace(conflict, ours=conflict.theirs, theirs=conflict.ours)
                for conflict in actual.conflicts
            )
            counts["conflicted"] += 1
        else:
            assert actual.candidate is not None and actual.candidate == reversed_result.candidate
            assert actual.candidate.snapshot.mapping == {
                name: selected for name, (_, selected) in zip(("a", "b"), truth) if selected is not None
            }
            assert not actual.conflicts
            counts["resolved"] += 1
    assert counts == {"conflicted": 2727, "resolved": 1369}
    return {"single_slot_oracle_classes": dict(sorted(one_slot.items())),
            "two_slot_results": dict(sorted(counts.items())), "side_order_checks": sum(counts.values())}


def typed_cases(store, values, contract):
    provides = [{"reference_id": "behavior", "relation": "provides_contract",
                 "target_hash": contract, "target_kind": "contract"}]

    def caller(target):
        return publish_declaration(store, declaration(
            "function", "caller", {"body": "fixed"}, references=provides, call_sites=[
                {"call_site_id": "dispatch", "targets": [{
                    "target_id": "direct", "target_hash": target, "condition": None,
                    "required_contract_hash": contract,
                }]},
            ],
        ))

    def check(label, inputs, kind, subject):
        actual = merge_closed(store, *inputs)
        assert actual.candidate is None and len(actual.conflicts) == 1, (label, actual)
        conflict = actual.conflicts[0]
        assert (conflict.kind, conflict.subject) == (kind, subject), (label, actual)
        return asdict(conflict)

    callers = tuple(caller(value) for value in values)
    shared = {"contract": contract, **{f"target-{i}": val for i, val in enumerate(values)}}
    called = [envelope(dict(shared, caller=hash_), {"entry": "caller"}) for hash_ in callers]
    retarget = check("retarget", called, "retarget", "caller")
    assert retarget["details"] == ("dispatch/direct",)

    old = envelope({"contract": contract, "target": values[0]})
    new = envelope({"contract": contract, "target": values[1]})
    addition = envelope({"contract": contract, "target": values[0], "caller": callers[0]},
                        {"entry": "caller"})
    missing = check("dependency", (old, new, addition), "dependency", "candidate")
    assert missing["details"] == (f"unselected dependency {values[0]}",)
    retained = envelope({"contract": contract, "target": values[1], "retained": values[0]})
    closed = merge_closed(store, old, retained, addition)
    assert closed.candidate is not None and not closed.conflicts
    assert closed.candidate.snapshot.mapping == {
        "contract": contract, "target": values[1], "retained": values[0], "caller": callers[0],
    }

    slots = {"contract": contract, "x": values[0], "y": values[1], "z": values[2]}
    root = envelope(slots, {"entry": "x"})
    left_root = envelope(slots, {"entry": "y"})
    right_root = envelope(slots, {"entry": "z"})
    divergent_roots = check("different roots", (root, left_root, right_root), "root", "entry")
    assert (divergent_roots["baseline"], divergent_roots["ours"], divergent_roots["theirs"]) == ("x", "y", "z")
    deleted = envelope({name: value for name, value in slots.items() if name != "y"}, {"entry": "x"})
    lost_root = check("lost root", (root, deleted, left_root), "root", "entry")
    wrong_pin = check("wrong pin", (root, replace(root, exact_pin="wrong"), right_root), "root", "ours")
    stale_semantic_root = check("wrong semantic root", (
        root, root, pin_merge_input(replace(root.snapshot, root_hash="wrong"), {"entry": "x"}),
    ), "root", "theirs")
    open_context = check("unsupported", (
        root, pin_merge_input(root.snapshot, {"entry": "x"}, policy="open-world"), right_root,
    ), "unsupported-context", "ours")
    return {"retarget": retarget, "missing_candidate_dependency": missing,
            "retained_candidate_root": closed.candidate.snapshot.root_hash,
            "divergent_roots": divergent_roots, "lost_entrypoint": lost_root,
            "stale_pin": wrong_pin, "stale_semantic_root": stale_semantic_root,
            "unsupported_context": open_context}


def run():
    store = ContentStore()
    contract = publish_declaration(store, declaration("contract", "bounded", {"input": "int"}))
    provides = [{"reference_id": "behavior", "relation": "provides_contract",
                 "target_hash": contract, "target_kind": "contract"}]
    targets = tuple(publish_declaration(store, declaration("function", "callee", {"offset": value},
                       references=provides)) for value in range(3))
    # Use standalone contract values for the exhaustive slot matrix.
    options = tuple(publish_declaration(store, declaration("contract", "label", {"index": value}))
                    for value in range(3))
    before = store.hashes()
    exhaustive = finite(store, options)
    assert store.hashes() == before
    controls = typed_cases(store, targets, contract)
    return {"exhaustive": exhaustive, "structural_controls": controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2) + "\n")


if __name__ == "__main__":
    main()
