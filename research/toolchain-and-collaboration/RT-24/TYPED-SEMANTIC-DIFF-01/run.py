"""Validate typed diff projections against independently named fixtures."""
import argparse
from dataclasses import asdict, replace
from itertools import permutations, product
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(GRAPH))

from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_diff_core import Lineage, Occurrence, semantic_diff
from src.semantic_graph import ContentStore, make_snapshot
from src.semantic_merge_core import pin_merge_input


def scenario():
    store = ContentStore()

    def put(kind, name, content, **fields):
        return publish_declaration(store, {"format": FORMAT, "schema_version": SCHEMA_VERSION,
            "kind": kind, "declaration_id": name, "content": content, **fields})

    def ref(identifier, relation, target, kind):
        return {"reference_id": identifier, "relation": relation, "target_hash": target,
                "target_kind": kind}

    contract = put("contract", "call-contract", {"value": "small-range"})
    alternate_contract = put("contract", "strict-contract", {"value": "narrow-range"})
    type_before = put("type", "word-8", {"bits": 8})
    type_after = put("type", "word-16", {"bits": 16})
    provides = ref("provides", "provides_contract", contract, "contract")
    provider = put("function", "supply", {"body": "original"}, references=[provides])
    replacement = put("function", "supply", {"body": "revised"}, references=[provides])

    def caller(name, targets, reference):
        return put("function", name, {"body": "defined"}, call_sites=[
            {"call_site_id": "choice", "targets": [
                {"target_id": route, "target_hash": target, "condition": when,
                 "required_contract_hash": require}
                for route, target, when, require in targets
            ]}], references=[provides, ref("arg-type", "uses_type", reference, "type")])

    targets = (("direct", provider, "known", contract),
               ("fallback", provider, "other", contract))
    changed_targets = (("direct", replacement, "known", contract),
                       ("fallback", provider, "special", alternate_contract))
    old_caller = caller("perform", targets, type_before)
    new_caller = caller("perform", changed_targets, type_after)
    different_occurrence = caller("run-alias", changed_targets, type_after)
    old_slots = {
        "api": old_caller, "old-name": put("contract", "aliased", {"label": "same"}),
        "split": put("contract", "split", {"part": "whole"}),
        "merge-a": put("contract", "merge-a", {"part": "left"}),
        "merge-b": put("contract", "merge-b", {"part": "right"}),
    }
    common = {"call-contract": contract, "strict-contract": alternate_contract,
              "word-8": type_before, "word-16": type_after, "provider-old": provider,
              "provider-new": replacement}
    new_slots = {
        "api": new_caller, "new-name": old_slots["old-name"],
        "part-a": put("contract", "part-a", {"part": "left"}),
        "part-b": put("contract", "part-b", {"part": "right"}),
        "merged": put("contract", "merged", {"part": "whole"}),
    }
    before = pin_merge_input(make_snapshot({**common, **old_slots}), {"entry": "api", "alias": "old-name"})
    after = pin_merge_input(make_snapshot({**common, **new_slots}), {"entry": "api", "alias": "new-name"})

    def lineage(kind, origin_slots, candidate_slots):
        return Lineage(kind, before.exact_pin, after.exact_pin,
                       tuple(Occurrence(slot, old_slots[slot]) for slot in origin_slots),
                       tuple(Occurrence(slot, new_slots[slot]) for slot in candidate_slots),
                       "fixture-evidence/" + kind)

    records = (lineage("rename", ("old-name",), ("new-name",)),
               lineage("split", ("split",), ("part-a", "part-b")),
               lineage("merge", ("merge-a", "merge-b"), ("merged",)))
    return store, before, after, records, different_occurrence


def control_errors(store, old, new, records, other_occurrence):
    rename, split, merge = records
    swapped_roots = pin_merge_input(new.snapshot, {"entry": "api"})
    without_target = pin_merge_input(make_snapshot({
        slot: value for slot, value in new.snapshot.selections if slot != "provider-new"
    }), dict(new.entrypoints))
    attempted = {
        "declared_lineage_stale_scope": (old, swapped_roots, records, "attached to different inputs"),
        "lineage_endpoint_binding": (old, new, (replace(rename,
             origins=(replace(rename.origins[0], value_hash="older"),)),), "endpoint is absent or stale"),
        "lineage_cardinality": (old, new, (replace(split, successors=split.successors[:1]),),
                                "cardinality"),
        "malformed_pin": (replace(old, exact_pin="different"), new, (), "exact pin"),
        "missing_selected_dependency": (old, without_target, (), "unselected dependency"),
        "unsupported_context": (old, pin_merge_input(new.snapshot, dict(new.entrypoints), "open"), (),
                                "unsupported-context"),
    }
    outcomes = {}
    for name, (before, after, lineage, expected) in attempted.items():
        invalid = semantic_diff(store, before, after, lineage)
        assert invalid.difference_id is None and any(expected in message for message in invalid.errors), invalid
        outcomes[name] = expected

    replaced = pin_merge_input(make_snapshot({**new.snapshot.mapping, "api": other_occurrence}),
                               dict(new.entrypoints))
    result = semantic_diff(store, new, replaced)
    assert result.difference_id and all(edge.operation in ("add", "remove") for edge in result.edges)
    operations = [edge.operation for edge in result.edges if edge.edge_kind == "call"]
    assert operations == ["remove", "remove", "add", "add"]
    outcomes["unpaired_replacement"] = operations
    return outcomes


def check():
    store, before, after, lineage, other_occurrence = scenario()
    previous_store = store.hashes()
    distinct = semantic_diff(store, before, after)
    exact = semantic_diff(store, before, after, lineage)
    assert exact.difference_id and not exact.errors and exact.difference_id != distinct.difference_id
    assert tuple(row.kind for row in exact.lineage) == ("merge", "rename", "split")
    assert not distinct.lineage and distinct.edges == exact.edges
    assert {row.logical_key: row.change_kind for row in exact.selections} == {
        "api": "replace", "merge-a": "remove", "merge-b": "remove", "merged": "add",
        "new-name": "add", "old-name": "remove", "part-a": "add", "part-b": "add", "split": "remove",
    }
    assert {row.edge_id: row.operation for row in exact.edges} == {
        "choice/direct": "retarget", "choice/fallback": "modify", "arg-type": "retarget",
    }
    labels = {row.edge_id: row for row in exact.edges}
    assert labels["choice/direct"].before.target_hash == before.snapshot.mapping["provider-old"]
    assert labels["choice/direct"].after.target_hash == after.snapshot.mapping["provider-new"]
    assert labels["choice/fallback"].before.condition == "other"
    assert labels["choice/fallback"].after.condition == "special"
    assert labels["choice/fallback"].after.required_contract_hash == after.snapshot.mapping["strict-contract"]
    assert len(exact.added_values) == len(exact.removed_values) == 4
    entries = {row.entrypoint: row for row in exact.entrypoints}
    assert entries["alias"].before.slot != entries["alias"].after.slot
    assert entries["alias"].before.value_hash == entries["alias"].after.value_hash
    assert entries["entry"].before.slot == entries["entry"].after.slot
    assert entries["entry"].before.value_hash != entries["entry"].after.value_hash

    swapped = semantic_diff(store, after, before)
    assert swapped.difference_id != distinct.difference_id
    assert swapped.added_values == exact.removed_values and swapped.removed_values == exact.added_values
    assert swapped.edges == tuple(replace(row, before=row.after, after=row.before) for row in exact.edges)
    assert swapped.entrypoints == tuple(replace(row, before=row.after, after=row.before) for row in exact.entrypoints)

    count = 0
    for ordered, orientations in product(permutations(lineage), product((False, True), repeat=3)):
        reformatted = tuple(replace(row, origins=row.origins[::-1], successors=row.successors[::-1])
                            if reverse else row for row, reverse in zip(ordered, orientations))
        assert exact == semantic_diff(store, before, after, reformatted)
        count += 1
    assert count == 48 and store.hashes() == previous_store
    return {"exact": asdict(exact), "undeclared_identity": distinct.difference_id,
            "reversed_identity": swapped.difference_id, "ordering_checks": count,
            "controls": control_errors(store, before, after, lineage, other_occurrence)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2) + "\n")


if __name__ == "__main__":
    main()
