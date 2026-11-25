"""Compare whole-graph merge admission over independent source and reverse projections."""
import argparse
from collections import Counter
from dataclasses import dataclass, replace
from itertools import product
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(GRAPH))

from src.semantic_dependency_index import (
    EXTRACTOR_ID, FORMAT, INDEX_SCHEMA_VERSION, SCHEMA_VERSION, CompletenessStatus,
    audit_snapshot_incoming_independently, dependency_edge_set_digest, publish_declaration,
    query_snapshot_incoming,
)
from src.semantic_graph import ContentStore, digest, make_snapshot
from src.semantic_merge_core import merge_closed, pin_merge_input

SCOPE = "rt24-closed-merge-all-selected/1"
SOURCE_MODES = ("exact", "wrong-input-pins", "missing-slot", "wrong-slot-hash", "extra-slot")
REVERSE_MODES = ("exact", "missing-query", "outdated-root", "wrong-scope", "wrong-extractor",
                 "wrong-schema", "omitted-edge-redigested", "invented-edge-redigested",
                 "incorrect-digest", "duplicate-query", "duplicate-edge-redigested")


@dataclass(frozen=True)
class SourceInventory:
    input_pins: tuple[str, str, str]
    rows: tuple[tuple[str, str], ...]

    @property
    def receipt(self):
        return digest({"domain": "rt24-source-inventory/1", "input_pins": self.input_pins,
                       "rows": self.rows})


def fixture():
    store = ContentStore()

    def create(kind, name, content, **extra):
        return publish_declaration(store, {
            "format": FORMAT, "schema_version": SCHEMA_VERSION, "kind": kind,
            "declaration_id": name, "content": content, **extra,
        })

    contract = create("contract", "domain", {"input": "integer"})
    references = [{"reference_id": "provided", "relation": "provides_contract",
                   "target_kind": "contract", "target_hash": contract}]
    old = create("function", "selected", {"result": 1}, references=references)
    new = create("function", "selected", {"result": 2}, references=references)
    caller = create("function", "caller", {"body": "call"}, references=references, call_sites=[
        {"call_site_id": "emit", "targets": [
            {"target_id": "current", "target_hash": old, "condition": None,
             "required_contract_hash": contract},
        ]},
    ])

    def pin(selections):
        return pin_merge_input(make_snapshot(selections), {})

    baseline = pin({"contract": contract, "operation": old})
    ours = pin({"contract": contract, "operation": new, "retained": old})
    theirs = pin({"contract": contract, "operation": old, "caller": caller})
    all_source = tuple(sorted({"contract": contract, "operation": new,
                              "retained": old, "caller": caller}.items()))
    inputs = {
        "structurally-closed": (baseline, ours, theirs),
        "closed-projection-omits-source": (baseline, ours, baseline),
        "dangling-merged-reference": (baseline, pin({"contract": contract, "operation": new}), theirs),
    }
    return store, inputs, all_source, old


def admit(store, merged, baseline, source, trusted_source_receipt, observed):
    if merged.candidate is None:
        return "structural-conflict"
    snapshot = merged.candidate.snapshot
    if source.input_pins != merged.input_pins:
        return "source-scope"
    if source.receipt != trusted_source_receipt:
        return "source-receipt"
    if source.rows != snapshot.selections:
        return "source-inventory"
    required = set(baseline.snapshot.mapping.values()) | set(snapshot.mapping.values())
    if len(observed) != len(required) or {query.target_hash for query in observed} != required:
        return "reverse-roster"
    for query in observed:
        if (query.snapshot_root, query.scope, query.extractor_id, query.index_schema_version) != (
            snapshot.root_hash, SCOPE, EXTRACTOR_ID, INDEX_SCHEMA_VERSION,
        ):
            return "reverse-scope"
        if len(query.edges) != len(set(query.edges)):
            return "reverse-edge-gap"
        audit = audit_snapshot_incoming_independently(store, snapshot, query)
        if audit.status is not CompletenessStatus.SUPPORTED_WITHIN_SCOPE:
            return "reverse-edge-gap"
    return "clean-within-profile"


def source_modes(valid):
    return {
        "exact": valid,
        "wrong-input-pins": replace(valid, input_pins=("another-baseline", *valid.input_pins[1:])),
        "missing-slot": replace(valid, rows=valid.rows[1:]),
        "wrong-slot-hash": replace(valid, rows=((valid.rows[0][0], "old-cached-hash"), *valid.rows[1:])),
        "extra-slot": replace(valid, rows=(*valid.rows, ("unknown-slot", "unverified"))),
    }


def reverse_modes(exact, selected):
    actual = next(query for query in exact if query.target_hash == selected)
    assert len(actual.edges) == 1
    extra = replace(actual.edges[0], edge_id="unobserved-source")
    false_edges = tuple(sorted((*actual.edges, extra)))
    transforms = {
        "outdated-root": replace(actual, snapshot_root="older"),
        "wrong-scope": replace(actual, scope="current-branch-only"),
        "wrong-extractor": replace(actual, extractor_id="unbound"),
        "wrong-schema": replace(actual, index_schema_version=actual.index_schema_version + 1),
        "omitted-edge-redigested": replace(actual, edges=(), edge_set_digest=dependency_edge_set_digest(())),
        "invented-edge-redigested": replace(actual, edges=false_edges, edge_set_digest=dependency_edge_set_digest(false_edges)),
        "incorrect-digest": replace(actual, edge_set_digest="different"),
        "duplicate-edge-redigested": replace(
            actual, edges=actual.edges * 2, edge_set_digest=dependency_edge_set_digest(actual.edges * 2),
        ),
    }
    return {
        "exact": exact, "missing-query": exact[1:], "duplicate-query": (*exact, exact[0]),
        **{mode: tuple(revised if row is actual else row for row in exact)
           for mode, revised in transforms.items()},
    }


def check():
    store, examples, source_rows, selected = fixture()
    complete_inputs = examples["structurally-closed"]
    aligned = merge_closed(store, *complete_inputs)
    assert aligned.candidate is not None
    snapshot = aligned.candidate.snapshot
    full_queries = tuple(
        query_snapshot_incoming(store, snapshot, value_hash, SCOPE)
        for value_hash in sorted(set(complete_inputs[0].snapshot.mapping.values()) | set(snapshot.mapping.values()))
    )
    reversed_choices = reverse_modes(full_queries, selected)
    gate_counts = Counter()
    rows = []
    for structure, source_mode, reverse_mode in product(examples, SOURCE_MODES, REVERSE_MODES):
        base, ours, theirs = examples[structure]
        merged = merge_closed(store, base, ours, theirs)
        source = SourceInventory((base.exact_pin, ours.exact_pin, theirs.exact_pin), source_rows)
        observed = admit(store, merged, base, source_modes(source)[source_mode], source.receipt,
                         reversed_choices[reverse_mode])
        expected_clean = (structure, source_mode, reverse_mode) == ("structurally-closed", "exact", "exact")
        assert (observed == "clean-within-profile") == expected_clean, (structure, source_mode, reverse_mode, observed)
        gate_counts[observed] += 1
        rows.append({"structure": structure, "source": source_mode, "reverse": reverse_mode,
                     "structural_candidate": merged.candidate is not None, "gate": observed})
    assert len(rows) == 165 and sum(row["structural_candidate"] for row in rows) == 110
    assert gate_counts == {
        "structural-conflict": 55, "source-scope": 22, "source-receipt": 66, "source-inventory": 11,
        "reverse-roster": 2, "reverse-scope": 4, "reverse-edge-gap": 4, "clean-within-profile": 1,
    }, gate_counts
    omitted_inputs = examples["closed-projection-omits-source"]
    incomplete = merge_closed(store, *omitted_inputs)
    assert incomplete.candidate is not None
    reduced = incomplete.candidate.snapshot
    corroborating = SourceInventory(incomplete.input_pins, reduced.selections)
    authoritative = SourceInventory(incomplete.input_pins, source_rows)
    local_queries = tuple(query_snapshot_incoming(store, reduced, value_hash, SCOPE)
                          for value_hash in sorted(set(reduced.mapping.values())))
    assert admit(store, incomplete, omitted_inputs[0], corroborating, corroborating.receipt,
                 local_queries) == "clean-within-profile"
    assert admit(store, incomplete, omitted_inputs[0], corroborating, authoritative.receipt,
                 local_queries) == "source-receipt"
    return {
        "matrix_size": len(rows), "structural_candidates": 110,
        "same_projection_as_source_control": "falsely clean when self-authorized; independent receipt refuses",
        "clean_candidate_pin": aligned.candidate.exact_pin,
        "reverse_queries_in_complete_roster": len(full_queries),
        "gate_counts": dict(sorted(gate_counts.items())), "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2) + "\n")


if __name__ == "__main__":
    main()
