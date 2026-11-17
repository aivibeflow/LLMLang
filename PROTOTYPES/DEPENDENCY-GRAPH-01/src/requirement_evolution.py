"""Requirement evolution and semantic impact research prototype.

Requirement states and derived artifacts are immutable content-addressed values.
Lineage/provenance is stored separately and does not invalidate semantic hashes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .semantic_graph import (
    ContentStore, Dependency, RelationStore, Snapshot, make_snapshot,
    merge_snapshots, verification_key,
)


class EvolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ImpactReport:
    changed: bool
    old_state: str
    new_state: str
    direct_dependents: tuple[str, ...]
    transitive_dependents: tuple[str, ...]
    active_baseline_dependents: tuple[str, ...]
    changed_selection_keys: tuple[str, ...]


@dataclass(frozen=True)
class MergeReport:
    snapshot: Snapshot | None
    conflicts: tuple[tuple[str, str, str], ...]


def create_requirement_state(
    store: ContentStore,
    requirement_key: str,
    semantic_payload: Mapping[str, Any],
    semantic_dependencies: Iterable[tuple[str, str]] = (),
) -> str:
    """Create a new immutable semantic state for one snapshot selection key."""
    if not requirement_key:
        raise EvolutionError("requirement key is required")
    dependencies = tuple(
        Dependency("requires", target_hash, role)
        for role, target_hash in semantic_dependencies
    )
    return store.put(
        "requirement_state",
        {"semantic": dict(semantic_payload)},
        dependencies,
    )


def create_derived_artifact(
    store: ContentStore,
    kind: str,
    payload: Mapping[str, Any],
    inputs: Iterable[tuple[str, str]],
) -> str:
    """Create an artifact whose semantic identity depends on exact input states."""
    if not kind:
        raise EvolutionError("artifact kind is required")
    dependencies = tuple(
        Dependency("derived_from", input_hash, role)
        for role, input_hash in inputs
    )
    if not dependencies:
        raise EvolutionError("derived artifact must identify at least one input")
    return store.put(kind, dict(payload), dependencies)


def record_lineage(
    relations: RelationStore,
    scope: str,
    source_hash: str,
    relation: str,
    target_hash: str,
) -> None:
    """Record non-hash-relevant history such as supersedes, split_into, merged_from."""
    allowed = {"supersedes", "split_into", "merged_from", "clarifies", "rephrases"}
    if relation not in allowed:
        raise EvolutionError(f"unsupported lineage relation: {relation}")
    relations.add(scope, source_hash, relation, target_hash)


def analyze_impact(
    store: ContentStore,
    old_state: str,
    new_state: str,
    baseline: Snapshot,
    candidate: Snapshot,
) -> ImpactReport:
    if old_state not in store or new_state not in store:
        raise EvolutionError("both requirement states must exist in the content store")
    direct = store.dependents(old_state)
    transitive = store.dependents(old_state, transitive=True)
    baseline_selected = set(baseline.mapping.values())
    active = transitive & baseline_selected
    before, after = baseline.mapping, candidate.mapping
    changed_keys = tuple(sorted(
        key for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    ))
    return ImpactReport(
        changed=old_state != new_state,
        old_state=old_state,
        new_state=new_state,
        direct_dependents=tuple(sorted(direct)),
        transitive_dependents=tuple(sorted(transitive)),
        active_baseline_dependents=tuple(sorted(active)),
        changed_selection_keys=changed_keys,
    )


def merge_requirement_branches(
    base: Snapshot, left: Snapshot, right: Snapshot
) -> MergeReport:
    merged, conflicts = merge_snapshots(base, left, right)
    return MergeReport(
        snapshot=merged,
        conflicts=tuple(sorted((key, pair[0], pair[1])
                               for key, pair in conflicts.items())),
    )


def make_verification_key(
    store: ContentStore,
    artifact_hash: str,
    verifier_id: str,
    config: Mapping[str, Any],
    assumptions: Iterable[str] = (),
) -> str:
    """Verification identity pins the artifact and its exact semantic closure."""
    return verification_key(
        artifact_hash,
        store.closure_digest(artifact_hash),
        verifier_id,
        config,
        assumptions,
    )


def evolve_selection(
    snapshot: Snapshot,
    selection_key: str,
    new_value_hash: str,
) -> Snapshot:
    selections = snapshot.mapping
    selections[selection_key] = new_value_hash
    return make_snapshot(selections, (snapshot.root_hash,))


def split_selection(
    snapshot: Snapshot,
    old_key: str,
    new_values: Mapping[str, str],
) -> Snapshot:
    if old_key not in snapshot.mapping or not new_values:
        raise EvolutionError("split requires an existing key and at least one result")
    selections = snapshot.mapping
    del selections[old_key]
    for key, value_hash in new_values.items():
        if key in selections:
            raise EvolutionError(f"split target already exists: {key}")
        selections[key] = value_hash
    return make_snapshot(selections, (snapshot.root_hash,))


def merge_selections(
    snapshot: Snapshot,
    old_keys: Iterable[str],
    new_key: str,
    new_value_hash: str,
) -> Snapshot:
    keys = tuple(old_keys)
    if len(keys) < 2 or any(key not in snapshot.mapping for key in keys):
        raise EvolutionError("merge requires at least two existing selection keys")
    selections = snapshot.mapping
    for key in keys:
        del selections[key]
    if new_key in selections:
        raise EvolutionError(f"merge target already exists: {new_key}")
    selections[new_key] = new_value_hash
    return make_snapshot(selections, (snapshot.root_hash,))
