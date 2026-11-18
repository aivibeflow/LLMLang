"""Explicit SPG subset and typed semantic dependency extractor (research prototype).

This module accepts only the versioned declaration envelope defined here. It does
not parse arbitrary Entity payloads or LLMLang source. Hashes are produced by the
existing experimental ContentStore; this is not a normative SPG wire schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Mapping

from .impact_planning import CompletenessStatus
from .semantic_graph import ContentStore, Dependency, Snapshot, canonical_bytes


FORMAT = "llmlang.semantic-object"
SCHEMA_VERSION = 2
EXTRACTOR_ID = "semantic-dependency-extractor/2"


KINDS = {"function", "operation", "type", "contract", "implementation", "effect"}
REFERENCE_RELATIONS = {
    "function": {"uses_type", "uses_contract", "provides_contract"},
    "operation": {"uses_type", "uses_contract", "provides_contract"},
    "type": {"extends_type"},
    "contract": {"uses_type"},
    "implementation": {"implements_contract", "uses_effect"},
    "effect": {"uses_type"},
}
TARGET_KINDS = {
    "uses_type": {"type"},
    "extends_type": {"type"},
    "uses_contract": {"contract"},
    "provides_contract": {"contract"},
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
    required_contract_hash: str | None = None
    provided_contract_hash: str | None = None

    def record(self) -> dict[str, Any]:
        return {
            "source_hash": self.source_hash,
            "edge_id": self.edge_id,
            "relation": self.relation,
            "target_hash": self.target_hash,
            "target_kind": self.target_kind,
            "condition": self.condition,
            "required_contract_hash": self.required_contract_hash,
            "provided_contract_hash": self.provided_contract_hash,
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



@dataclass(frozen=True)
class ReverseLookupEvidence:
    """Externally produced, scope-limited audit bound to one exact index query.

    This record is an evidence envelope, not a cryptographic signature or proof.
    The producer must independently justify its status and preserve its evidence.
    """
    evidence_id: str
    snapshot_root: str
    target_hash: str
    scope: str
    index_schema_version: int
    extractor_id: str
    edge_set_digest: str
    status: CompletenessStatus
    observation_model_id: str
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    discrepancies: tuple[str, ...] = ()

    def __post_init__(self):
        required = (self.evidence_id, self.snapshot_root, self.target_hash,
                    self.scope, self.extractor_id, self.edge_set_digest,
                    self.observation_model_id)
        if not all(isinstance(value, str) and value for value in required):
            raise ValueError("reverse lookup evidence identities are required")
        if self.index_schema_version < 1:
            raise ValueError("index_schema_version must be positive")
        if not isinstance(self.status, CompletenessStatus):
            raise ValueError("invalid completeness status")
        if self.status is CompletenessStatus.GAP_FOUND and not self.discrepancies:
            raise ValueError("GAP_FOUND evidence must identify at least one discrepancy")
        if self.status is CompletenessStatus.SUPPORTED_WITHIN_SCOPE and self.discrepancies:
            raise ValueError("supported evidence cannot contain unresolved discrepancies")


@dataclass(frozen=True)
class SnapshotIncomingResult:
    snapshot_root: str
    target_hash: str
    scope: str
    edges: tuple[IndexedEdge, ...]
    edge_set_digest: str
    index_schema_version: int
    extractor_id: str
    completeness_status: CompletenessStatus
    reason: str
    evidence_id: str | None = None
    discrepancies: tuple[str, ...] = ()


def dependency_edge_set_digest(edges: Iterable[IndexedEdge]) -> str:
    """Digest the exact deterministic edge set returned by a reverse query."""
    return sha256(canonical_bytes([edge.record() for edge in sorted(edges)])).hexdigest()


def audit_snapshot_incoming_independently(
    store: ContentStore, snapshot: Snapshot, result: SnapshotIncomingResult,
) -> ReverseLookupEvidence:
    """Produce differential evidence by rescanning selected declaration payloads.

    This is an independent traversal of the stored declaration projection, not an
    independent trust domain: it shares the same Content Store and source payloads.
    """
    if result.snapshot_root != snapshot.root_hash:
        raise ValueError("incoming result is bound to a different Snapshot")
    if not result.scope or not result.target_hash:
        raise ValueError("incoming result target and scope are required")
    store.get(result.target_hash)
    expected: list[IndexedEdge] = []
    for source_hash in sorted(set(snapshot.mapping.values())):
        source = store.get(source_hash)
        payload = source.payload
        if not isinstance(payload, Mapping):
            raise SemanticObjectError("stored declaration payload must be a mapping")
        for row in payload.get("references", ()):
            target_hash = row.get("target_hash")
            if target_hash == result.target_hash:
                target = store.get(target_hash)
                expected.append(IndexedEdge(
                    source_hash, row.get("reference_id"), row.get("relation"),
                    target_hash, target.kind, row.get("condition"),
                ))
        for site in payload.get("call_sites", ()):
            for target_row in site.get("targets", ()):
                edge_id = f"{site.get('call_site_id')}/{target_row.get('target_id')}"
                target_hash = target_row.get("target_hash")
                required_contract_hash = target_row.get("required_contract_hash")
                required_contract = store.get(required_contract_hash)
                if required_contract.kind != "contract":
                    raise SemanticObjectError("call-site requirement must target a contract")
                if target_hash == result.target_hash:
                    target = store.get(target_hash)
                    provided = _provided_contract_hash(store, target_hash)
                    expected.append(IndexedEdge(
                        source_hash, edge_id, "calls", target_hash, target.kind,
                        target_row.get("condition"), required_contract_hash, provided,
                    ))
                if required_contract_hash == result.target_hash:
                    expected.append(IndexedEdge(
                        source_hash, edge_id + "/required-contract", "requires_contract",
                        result.target_hash, "contract",
                    ))
    expected_edges = tuple(sorted(expected))
    actual_edges = tuple(sorted(result.edges))
    missing = sorted(set(expected_edges) - set(actual_edges))
    unexpected = sorted(set(actual_edges) - set(expected_edges))
    discrepancies = tuple(sorted(set(
        list(result.discrepancies)
        + ["missing-index-edge:" + edge.source_hash + ":" + edge.edge_id for edge in missing]
        + ["unexpected-index-edge:" + edge.source_hash + ":" + edge.edge_id for edge in unexpected]
        + (["result-edge-digest-mismatch"] if dependency_edge_set_digest(actual_edges) != result.edge_set_digest else [])
    )))
    status = CompletenessStatus.GAP_FOUND if discrepancies else CompletenessStatus.SUPPORTED_WITHIN_SCOPE
    observation_model_id = "snapshot-payload-reference-scan/1"
    identity = {
        "snapshot_root": snapshot.root_hash, "target_hash": result.target_hash,
        "scope": result.scope, "index_schema_version": result.index_schema_version,
        "extractor_id": result.extractor_id, "edge_set_digest": result.edge_set_digest,
        "observation_model_id": observation_model_id, "discrepancies": discrepancies,
    }
    evidence_id = "audit:" + sha256(canonical_bytes(identity)).hexdigest()
    return ReverseLookupEvidence(
        evidence_id=evidence_id, snapshot_root=snapshot.root_hash,
        target_hash=result.target_hash, scope=result.scope,
        index_schema_version=result.index_schema_version,
        extractor_id=result.extractor_id, edge_set_digest=result.edge_set_digest,
        status=status, observation_model_id=observation_model_id,
        assumptions=("all selected Snapshot declarations are readable and conform to the declared envelope",),
        exclusions=("runtime reflection", "external dynamic dispatch", "unselected historical objects"),
        discrepancies=discrepancies,
    )


def query_snapshot_incoming(
    store: ContentStore, snapshot: Snapshot, target_hash: str, scope: str,
    evidence: ReverseLookupEvidence | None = None,
) -> SnapshotIncomingResult:
    """Return exact incoming edges plus a fail-closed completeness assessment.

    Evidence is binding-checked, not authenticated or independently proven here.
    """
    if not scope:
        raise ValueError("reverse lookup scope is required")
    store.get(target_hash)
    index = build_snapshot_dependency_index(store, snapshot)
    edges = index.incoming(target_hash)
    edge_digest = dependency_edge_set_digest(edges)
    if evidence is None:
        status = CompletenessStatus.NOT_CHECKED
        reason = "no independent reverse-lookup completeness evidence was supplied"
        evidence_id, discrepancies = None, ()
    else:
        matches = (
            evidence.snapshot_root == snapshot.root_hash
            and evidence.target_hash == target_hash
            and evidence.scope == scope
            and evidence.index_schema_version == index.schema_version
            and evidence.extractor_id == EXTRACTOR_ID
            and evidence.edge_set_digest == edge_digest
        )
        evidence_id, discrepancies = evidence.evidence_id, evidence.discrepancies
        if not matches:
            status = CompletenessStatus.UNKNOWN
            reason = "evidence is stale or bound to a different snapshot, target, scope, index, extractor, or edge set"
        else:
            status = evidence.status
            reason = (
                "reverse lookup is supported only within the evidence's declared scope and assumptions"
                if status is CompletenessStatus.SUPPORTED_WITHIN_SCOPE
                else "independent audit found missing or unresolved dependency information"
                if status is CompletenessStatus.GAP_FOUND
                else "independent evidence does not support a completeness conclusion"
            )
    return SnapshotIncomingResult(
        snapshot.root_hash, target_hash, scope, edges, edge_digest,
        index.schema_version, EXTRACTOR_ID, status, reason, evidence_id, discrepancies,
    )


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SemanticObjectError(f"{field} must be a non-empty string")
    return value


def _validate_condition(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field)


def _provided_contract_hash(store: ContentStore, callee_hash: str) -> str:
    """Resolve the one explicit contract provided by a callable declaration."""
    callee = store.get(callee_hash)
    if callee.kind not in {"function", "operation"} or not isinstance(callee.payload, Mapping):
        raise SemanticObjectError("callee must be a function or operation declaration")
    rows = [
        row for row in callee.payload.get("references", ())
        if row.get("relation") == "provides_contract"
    ]
    if len(rows) != 1:
        raise SemanticObjectError(
            "callable target must declare exactly one provides_contract reference"
        )
    contract_hash = _require_string(rows[0].get("target_hash"), "provided contract hash")
    contract = store.get(contract_hash)
    if contract.kind != "contract":
        raise SemanticObjectError("provided contract reference must target a contract")
    return contract_hash


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
        if "/" in site_id:
            raise SemanticObjectError("call_site_id cannot contain '/' because it delimits call-target edge identity")
        if site_id in seen_sites:
            raise SemanticObjectError(f"duplicate call_site_id: {site_id}")
        seen_sites.add(site_id)
        targets = site["targets"]
        if not isinstance(targets, list) or not targets:
            raise SemanticObjectError("call site must have at least one explicit target")
        seen_target_ids: set[str] = set()
        normalized_targets = []
        for target in targets:
            if not isinstance(target, Mapping) or set(target) != {"target_id", "target_hash", "condition", "required_contract_hash"}:
                raise SemanticObjectError("call target must contain target_id, target_hash, condition, required_contract_hash")
            target_id = _require_string(target["target_id"], "target_id")
            target_hash = _require_string(target["target_hash"], "target_hash")
            required_contract_hash = _require_string(target["required_contract_hash"], "required_contract_hash")
            if "/" in target_id:
                raise SemanticObjectError("target_id cannot contain '/' because it delimits call-target edge identity")
            if target_id in seen_target_ids:
                raise SemanticObjectError(f"duplicate target_id at call site {site_id}")
            seen_target_ids.add(target_id)
            normalized_targets.append({
                "target_id": target_id, "target_hash": target_hash,
                "condition": _validate_condition(target["condition"], "condition"),
                "required_contract_hash": required_contract_hash,
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
            required_contract = store.get(target_row["required_contract_hash"])
            if required_contract.kind != "contract":
                raise SemanticObjectError("call-site requirement must reference a contract")
            _provided_contract_hash(store, target_row["target_hash"])
            edge_id = f"{site['call_site_id']}/{target_row['target_id']}"
            dependencies.append(Dependency("calls", target_row["target_hash"], edge_id))
            dependencies.append(Dependency(
                "requires_contract", target_row["required_contract_hash"], edge_id + "/required-contract",
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
                required_contract = store.get(target_row["required_contract_hash"])
                if required_contract.kind != "contract":
                    raise SemanticObjectError("call-site requirement must target a contract")
                provided_contract_hash = _provided_contract_hash(store, target_row["target_hash"])
                edge_id = f"{site['call_site_id']}/{target_row['target_id']}"
                edges.append(IndexedEdge(
                    source_hash, edge_id, "calls", target_row["target_hash"], target.kind,
                    target_row["condition"], target_row["required_contract_hash"],
                    provided_contract_hash,
                ))
                edges.append(IndexedEdge(
                    source_hash, edge_id + "/required-contract", "requires_contract",
                    target_row["required_contract_hash"], "contract",
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
