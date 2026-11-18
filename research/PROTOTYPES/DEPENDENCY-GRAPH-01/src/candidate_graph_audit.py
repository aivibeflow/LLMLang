"""Audit the complete explicit dependency closure of a candidate Snapshot.

The audit is scoped to the versioned semantic-object declaration envelope. It checks
stored object hashes, typed references, and agreement between payload-derived edges
and the Content Store's hash-relevant dependency metadata.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from .semantic_dependency_index import (
    DependencyIndex,
    IndexedEdge,
    KINDS,
    SemanticObjectError,
    SCHEMA_VERSION,
    _provided_contract_hash,
    validate_declaration,
)
from .semantic_graph import ContentStore, Dependency, Snapshot, canonical_bytes, digest, make_snapshot


@dataclass(frozen=True)
class CandidateGraphAuditResult:
    valid: bool
    snapshot_root: str
    reachable_hashes: tuple[str, ...]
    dependency_index: DependencyIndex
    edge_set_digest: str
    graph_digest: str
    errors: tuple[str, ...]


def _stored_value_hash_matches(store: ContentStore, value_hash: str) -> bool:
    value = store.get(value_hash)
    canonical = {
        "domain": "llmlang.semantic-value.v1",
        "kind": value.kind,
        "payload": value.payload,
        "dependencies": [dependency.record() for dependency in value.dependencies],
    }
    return value.value_hash == value_hash and digest(canonical) == value_hash


def audit_candidate_snapshot_graph(
    store: ContentStore,
    snapshot: Snapshot,
) -> CandidateGraphAuditResult:
    """Validate every object reachable from candidate Snapshot selections.

    References need not themselves be direct Snapshot selections: they must resolve
    to immutable Content Store objects and are recursively included in the audited
    closure. Historical objects that are not reachable from a selected root are
    intentionally excluded.

    A valid result establishes structural/hash/reference consistency only for the
    explicit declaration subset. It does not prove behavioral compatibility,
    dynamic dispatch completeness, or that the candidate diff matches an approved plan.
    """
    errors: list[str] = []

    # Treat Snapshot fields as untrusted input. Validate their shape before
    # constructing mappings so malformed or unhashable keys fail closed.
    try:
        raw_selections = tuple(snapshot.selections)
    except TypeError:
        raw_selections = ()
        errors.append("candidate Snapshot selections are not iterable")

    normalized_selections: list[tuple[str, str]] = []
    seen_selection_keys: set[str] = set()
    selection_structure_valid = True
    for item in raw_selections:
        if not isinstance(item, tuple) or len(item) != 2:
            errors.append("candidate Snapshot contains a malformed selection entry")
            selection_structure_valid = False
            continue
        key, value_hash = item
        if not isinstance(key, str) or not key:
            errors.append("candidate Snapshot contains an empty or non-string selection key")
            selection_structure_valid = False
            continue
        if key in seen_selection_keys:
            errors.append("candidate Snapshot contains duplicate logical selection keys")
            selection_structure_valid = False
            continue
        seen_selection_keys.add(key)
        if not isinstance(value_hash, str) or not value_hash:
            errors.append(f"candidate Snapshot selection {key!r} has an invalid object hash")
            selection_structure_valid = False
            continue
        normalized_selections.append((key, value_hash))

    try:
        parent_roots = tuple(snapshot.parent_roots)
    except TypeError:
        parent_roots = ()
        errors.append("candidate Snapshot parent roots are not iterable")
        selection_structure_valid = False
    if any(not isinstance(root, str) or not root for root in parent_roots):
        errors.append("candidate Snapshot contains an invalid parent root")
        selection_structure_valid = False

    if selection_structure_valid:
        try:
            expected_snapshot = make_snapshot(dict(normalized_selections), parent_roots)
            if expected_snapshot.root_hash != snapshot.root_hash:
                errors.append("candidate Snapshot root does not match its selections and parents")
        except (TypeError, ValueError) as exc:
            errors.append(f"candidate Snapshot structure is invalid: {exc}")
    else:
        errors.append("candidate Snapshot root cannot be verified from malformed selections or parents")

    selected = dict(normalized_selections)
    valid_selected_hashes = set(selected.values())

    reachable: set[str] = set()
    visited: set[str] = set()
    pending = sorted(valid_selected_hashes, reverse=True)
    edges: list[IndexedEdge] = []

    while pending:
        value_hash = pending.pop()
        if value_hash in visited:
            continue
        visited.add(value_hash)
        try:
            value = store.get(value_hash)
        except KeyError:
            errors.append(f"missing Content Store object: {value_hash}")
            continue

        reachable.add(value_hash)
        try:
            if not _stored_value_hash_matches(store, value_hash):
                errors.append(f"stored semantic value hash mismatch: {value_hash}")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"cannot recompute semantic value hash {value_hash}: {exc}")

        if value.kind not in KINDS:
            errors.append(f"unsupported semantic object kind {value.kind!r}: {value_hash}")
            continue
        try:
            declaration = validate_declaration(value.payload)
        except (SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"invalid declaration {value_hash}: {exc}")
            continue
        if declaration["kind"] != value.kind:
            errors.append(f"stored kind differs from declaration kind: {value_hash}")
            continue

        expected_dependencies: list[Dependency] = []
        discovered_targets: list[str] = []
        for row in declaration["references"]:
            target_hash = row["target_hash"]
            expected_dependencies.append(
                Dependency(row["relation"], target_hash, row["reference_id"])
            )
            discovered_targets.append(target_hash)
            try:
                target = store.get(target_hash)
                if target.kind != row["target_kind"]:
                    errors.append(
                        f"{value_hash}:{row['reference_id']}: expected target kind "
                        f"{row['target_kind']}, found {target.kind}"
                    )
                edges.append(IndexedEdge(
                    value_hash, row["reference_id"], row["relation"],
                    target_hash, target.kind, row["condition"],
                ))
            except KeyError:
                errors.append(
                    f"{value_hash}:{row['reference_id']}: missing referenced object {target_hash}"
                )

        for site in declaration["call_sites"]:
            for target_row in site["targets"]:
                target_hash = target_row["target_hash"]
                required_contract_hash = target_row["required_contract_hash"]
                role = f"{site['call_site_id']}/{target_row['target_id']}"
                expected_dependencies.append(Dependency("calls", target_hash, role))
                expected_dependencies.append(Dependency(
                    "requires_contract", required_contract_hash, role + "/required-contract",
                ))
                discovered_targets.extend((target_hash, required_contract_hash))
                try:
                    target = store.get(target_hash)
                    if target.kind not in {"function", "operation"}:
                        errors.append(
                            f"{value_hash}:{role}: call target kind must be function or operation, "
                            f"found {target.kind}"
                        )
                    _provided_contract_hash(store, target_hash)
                    edges.append(IndexedEdge(
                        value_hash, role, "calls", target_hash,
                        target.kind, target_row["condition"], required_contract_hash,
                    ))
                    edges.append(IndexedEdge(
                        value_hash, role + "/required-contract", "requires_contract",
                        required_contract_hash, "contract",
                    ))
                except KeyError:
                    errors.append(
                        f"{value_hash}:{role}: missing call target object or contract {target_hash}"
                    )
                except SemanticObjectError as exc:
                    errors.append(f"{value_hash}:{role}: invalid provided contract: {exc}")
                try:
                    required_contract = store.get(required_contract_hash)
                    if required_contract.kind != "contract":
                        errors.append(
                            f"{value_hash}:{role}: required contract target kind must be contract, "
                            f"found {required_contract.kind}"
                        )
                except KeyError:
                    errors.append(
                        f"{value_hash}:{role}: missing required contract {required_contract_hash}"
                    )

        expected_counts = Counter(expected_dependencies)
        actual_counts = Counter(value.dependencies)
        if expected_counts != actual_counts:
            missing = sorted(expected_counts - actual_counts)
            unexpected = sorted(actual_counts - expected_counts)
            if missing:
                errors.append(f"{value_hash}: payload dependencies missing from stored metadata: {missing}")
            if unexpected:
                errors.append(f"{value_hash}: stored metadata has undeclared dependencies: {unexpected}")

        for target_hash in sorted(set(discovered_targets), reverse=True):
            if target_hash not in visited:
                pending.append(target_hash)

    ordered_edges = tuple(sorted(edges))
    edge_records = [edge.record() for edge in ordered_edges]
    edge_digest = sha256(canonical_bytes(edge_records)).hexdigest()
    ordered_hashes = tuple(sorted(reachable))
    graph_digest = digest({
        "domain": "llmlang.candidate-dependency-graph.v1",
        "snapshot_root": snapshot.root_hash,
        "reachable_hashes": ordered_hashes,
        "edges": edge_records,
    })
    index = DependencyIndex(SCHEMA_VERSION, ordered_edges, snapshot.root_hash)
    return CandidateGraphAuditResult(
        valid=not errors,
        snapshot_root=snapshot.root_hash,
        reachable_hashes=ordered_hashes,
        dependency_index=index,
        edge_set_digest=edge_digest,
        graph_digest=graph_digest,
        errors=tuple(sorted(set(errors))),
    )
