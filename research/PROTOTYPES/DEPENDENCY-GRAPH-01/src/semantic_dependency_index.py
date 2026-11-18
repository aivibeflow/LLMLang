"""Explicit SPG subset and typed semantic dependency extractor (research prototype).

This module accepts only the versioned declaration envelope defined here. It does
not parse arbitrary Entity payloads or LLMLang source. Hashes are produced by the
existing experimental ContentStore; this is not a normative SPG wire schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .semantic_graph import ContentStore, Dependency, Snapshot


FORMAT = "llmlang.semantic-object"
SCHEMA_VERSION = 1

KINDS = {"function", "operation", "type", "contract", "implementation", "effect"}
REFERENCE_RELATIONS = {
    "function": {"uses_type", "uses_contract"},
    "operation": {"uses_type", "uses_contract"},
    "type": {"extends_type"},
    "contract": {"uses_type"},
    "implementation": {"implements_contract", "uses_effect"},
    "effect": {"uses_type"},
}
TARGET_KINDS = {
    "uses_type": {"type"},
    "extends_type": {"type"},
    "uses_contract": {"contract"},
    "implements_contract": {"contract"},
    "uses_effect": {"effect"},
}


class SemanticObjectError(ValueError):
    """Malformed or semantically inconsistent declaration."""


@dataclass(frozen=True, order=True)
class IndexedEdge:
    source_hash: str
    edge_id: str
    relation: str
    target_hash: str
    target_kind: str
    condition: str | None = None

    def record(self) -> dict[str, Any]:
        return {
            "source_hash": self.source_hash,
            "edge_id": self.edge_id,
            "relation": self.relation,
            "target_hash": self.target_hash,
            "target_kind": self.target_kind,
            "condition": self.condition,
        }


@dataclass(frozen=True)
class DependencyIndex:
    schema_version: int
    edges: tuple[IndexedEdge, ...]
    snapshot_root: str | None = None

    def outgoing(self, source_hash: str) -> tuple[IndexedEdge, ...]:
        return tuple(edge for edge in self.edges if edge.source_hash == source_hash)

    def incoming(self, target_hash: str) -> tuple[IndexedEdge, ...]:
        return tuple(edge for edge in self.edges if edge.target_hash == target_hash)


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SemanticObjectError(f"{field} must be a non-empty string")
    return value


def _validate_condition(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field)


def validate_declaration(declaration: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and detach one canonical declaration envelope."""
    if not isinstance(declaration, Mapping):
        raise SemanticObjectError("declaration must be an object")
    required = {"format", "schema_version", "kind", "declaration_id", "content"}
    optional = {"references", "call_sites"}
    if set(declaration) - required - optional or not required.issubset(declaration):
        raise SemanticObjectError("declaration has missing or unknown top-level fields")
    if declaration["format"] != FORMAT or declaration["schema_version"] != SCHEMA_VERSION:
        raise SemanticObjectError("unsupported semantic-object format/schema")
    kind = _require_string(declaration["kind"], "kind")
    if kind not in KINDS:
        raise SemanticObjectError(f"unsupported semantic object kind: {kind}")
    _require_string(declaration["declaration_id"], "declaration_id")
    if not isinstance(declaration["content"], Mapping):
        raise SemanticObjectError("content must be an object")

    references = declaration.get("references", [])
    call_sites = declaration.get("call_sites", [])
    if not isinstance(references, list) or not isinstance(call_sites, list):
        raise SemanticObjectError("references and call_sites must be arrays")
    if call_sites and kind not in {"function", "operation"}:
        raise SemanticObjectError("only function and operation may own call_sites")

    seen_reference_ids: set[str] = set()
    normalized_refs = []
    for row in references:
        if not isinstance(row, Mapping) or set(row) - {"reference_id", "relation", "target_hash", "target_kind", "condition"}:
            raise SemanticObjectError("malformed reference")
        ref_id = _require_string(row.get("reference_id"), "reference_id")
        relation = _require_string(row.get("relation"), "relation")
        target_hash = _require_string(row.get("target_hash"), "target_hash")
        target_kind = _require_string(row.get("target_kind"), "target_kind")
        if ref_id in seen_reference_ids:
            raise SemanticObjectError(f"duplicate reference_id: {ref_id}")
        seen_reference_ids.add(ref_id)
        if relation not in REFERENCE_RELATIONS[kind]:
            raise SemanticObjectError(f"relation {relation} is not allowed from {kind}")
        if target_kind not in TARGET_KINDS[relation]:
            raise SemanticObjectError(f"relation {relation} cannot target {target_kind}")
        normalized_refs.append({
            "reference_id": ref_id, "relation": relation,
            "target_hash": target_hash, "target_kind": target_kind,
            "condition": _validate_condition(row.get("condition"), "condition"),
        })

    seen_sites: set[str] = set()
    normalized_sites = []
    for site in call_sites:
        if not isinstance(site, Mapping) or set(site) != {"call_site_id", "targets"}:
            raise SemanticObjectError("call site must contain exactly call_site_id and targets")
        site_id = _require_string(site["call_site_id"], "call_site_id")
        if site_id in seen_sites:
            raise SemanticObjectError(f"duplicate call_site_id: {site_id}")
        seen_sites.add(site_id)
        targets = site["targets"]
        if not isinstance(targets, list) or not targets:
            raise SemanticObjectError("call site must have at least one explicit target")
        seen_target_ids: set[str] = set()
        normalized_targets = []
        for target in targets:
            if not isinstance(target, Mapping) or set(target) != {"target_id", "target_hash", "condition"}:
                raise SemanticObjectError("call target must contain target_id, target_hash, condition")
            target_id = _require_string(target["target_id"], "target_id")
            target_hash = _require_string(target["target_hash"], "target_hash")
            if target_id in seen_target_ids:
                raise SemanticObjectError(f"duplicate target_id at call site {site_id}")
            seen_target_ids.add(target_id)
            normalized_targets.append({
                "target_id": target_id, "target_hash": target_hash,
                "condition": _validate_condition(target["condition"], "condition"),
            })
        normalized_sites.append({
            "call_site_id": site_id,
            "targets": sorted(normalized_targets, key=lambda row: row["target_id"]),
        })

    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration["declaration_id"],
        "content": dict(declaration["content"]),
        "references": sorted(normalized_refs, key=lambda row: row["reference_id"]),
        "call_sites": sorted(normalized_sites, key=lambda row: row["call_site_id"]),
    }


def publish_declaration(store: ContentStore, declaration: Mapping[str, Any]) -> str:
    """Validate exact references and publish the declaration into ContentStore."""
    normalized = validate_declaration(declaration)
    dependencies: list[Dependency] = []
    for row in normalized["references"]:
        target = store.get(row["target_hash"])
        if target.kind != row["target_kind"]:
            raise SemanticObjectError(
                f"reference {row['reference_id']} expected {row['target_kind']}, got {target.kind}"
            )
        dependencies.append(Dependency(row["relation"], row["target_hash"], row["reference_id"]))
    for site in normalized["call_sites"]:
        for target_row in site["targets"]:
            target = store.get(target_row["target_hash"])
            if target.kind not in {"function", "operation"}:
                raise SemanticObjectError("call target must be a function or operation")
            dependencies.append(Dependency(
                "calls", target_row["target_hash"],
                f"{site['call_site_id']}/{target_row['target_id']}",
            ))
    return store.put(normalized["kind"], normalized, dependencies)


def build_dependency_index(store: ContentStore, source_hashes: Iterable[str] | None = None) -> DependencyIndex:
    """Build a deterministic typed edge projection from explicit stored declarations."""
    hashes = sorted(store.hashes() if source_hashes is None else set(source_hashes))
    edges: list[IndexedEdge] = []
    for source_hash in hashes:
        source = store.get(source_hash)
        declaration = validate_declaration(source.payload)
        if declaration["kind"] != source.kind:
            raise SemanticObjectError("stored kind does not match declaration kind")
        for row in declaration["references"]:
            target = store.get(row["target_hash"])
            edges.append(IndexedEdge(
                source_hash, row["reference_id"], row["relation"],
                row["target_hash"], target.kind, row["condition"],
            ))
        for site in declaration["call_sites"]:
            for target_row in site["targets"]:
                target = store.get(target_row["target_hash"])
                edges.append(IndexedEdge(
                    source_hash,
                    f"{site['call_site_id']}/{target_row['target_id']}",
                    "calls", target_row["target_hash"], target.kind,
                    target_row["condition"],
                ))
    return DependencyIndex(SCHEMA_VERSION, tuple(sorted(edges)))


def build_snapshot_dependency_index(store: ContentStore, snapshot: Snapshot) -> DependencyIndex:
    """Build a dependency projection over only objects selected by one snapshot.

    Historical immutable values remain in the store but are excluded unless selected
    by this snapshot. This makes incoming() suitable for snapshot-scoped impact planning.
    """
    selected_hashes = sorted(set(snapshot.mapping.values()))
    for value_hash in selected_hashes:
        store.get(value_hash)  # Fail closed if the snapshot references a missing value.
    index = build_dependency_index(store, selected_hashes)
    return DependencyIndex(index.schema_version, index.edges, snapshot.root_hash)
