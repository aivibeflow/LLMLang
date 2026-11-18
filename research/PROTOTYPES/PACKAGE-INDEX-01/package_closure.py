"""Exact dependency-closure resolver."""
from __future__ import annotations
from typing import Any, Mapping
from package_index import DEPENDENCY_KINDS, IndexError as LogicalIndexError, normalize

POLICIES = {"closure", "roots_only", "closure_with_optional"}
FOLLOW_KINDS = {"closure": {"required"}, "roots_only": set(),
                "closure_with_optional": {"required", "optional"}}


class ClosureError(ValueError):
    """Dependency closure cannot be resolved exactly and consistently."""


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ClosureError(f"{field} must be an exact sha256 Content Hash")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ClosureError(f"{field} must be an exact sha256 Content Hash") from exc
    if value[7:] != value[7:].lower():
        raise ClosureError(f"{field} must use lowercase hexadecimal")
    return value


def resolve_dependency_closure(roots, snapshot, *, policy: str = "closure",
                               condition_values: Mapping[tuple[str, str], bool] | None = None) -> dict[str, Any]:
    """Resolve exact roots against one immutable Content Store snapshot.

    Snapshot API: snapshot_id, get_object(exact_hash), get_dependencies(source_hash).
    Conditional required/optional edges require an explicit boolean selection in
    condition_values[(source_hash, edge_id)]; the condition expression is not evaluated.
    """
    if policy not in POLICIES:
        raise ClosureError(f"unsupported dependency policy: {policy!r}")
    if not isinstance(roots, (list, tuple, set, frozenset)) or not roots:
        raise ClosureError("roots must be a non-empty collection of Content Hash values")
    normalized_roots = sorted({_validate_hash(root, "root") for root in roots})
    if len(normalized_roots) != len(roots):
        raise ClosureError("duplicate package root")
    if condition_values is None:
        condition_values = {}
    if not isinstance(condition_values, Mapping):
        raise ClosureError("condition_values must be a mapping")
    try:
        snapshot_id = snapshot.snapshot_id
    except AttributeError as exc:
        raise ClosureError("snapshot must expose snapshot_id") from exc
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ClosureError("snapshot_id must be a non-empty string")

    objects: dict[str, dict[str, Any]] = {}
    dependencies: dict[tuple[str, str], dict[str, Any]] = {}
    pending = list(reversed(normalized_roots))
    queued = set(normalized_roots)
    follow_kinds = FOLLOW_KINDS[policy]

    def load_exact(content_hash: str) -> dict[str, Any]:
        try:
            record = snapshot.get_object(content_hash)
        except (KeyError, LookupError) as exc:
            raise ClosureError(f"missing exact dependency object: {content_hash}") from exc
        if not isinstance(record, Mapping) or record.get("hash") != content_hash:
            raise ClosureError(f"Content Store returned a different hash for exact request {content_hash}")
        kind, size = record.get("kind"), record.get("size")
        if not isinstance(kind, str) or not kind or type(size) is not int or size < 0:
            raise ClosureError(f"invalid object metadata for {content_hash}")
        return {"hash": content_hash, "kind": kind, "size": size}

    while pending:
        source_hash = pending.pop()
        if source_hash in objects:
            continue
        objects[source_hash] = load_exact(source_hash)
        try:
            edges = snapshot.get_dependencies(source_hash)
        except (KeyError, LookupError) as exc:
            raise ClosureError(f"dependency metadata missing for source: {source_hash}") from exc
        if edges is None:
            raise ClosureError(f"dependency metadata missing for source: {source_hash}")
        edge_ids = set()
        for raw in edges:
            if not isinstance(raw, Mapping):
                raise ClosureError(f"invalid dependency edge for source: {source_hash}")
            edge_id, kind = raw.get("edge_id"), raw.get("kind")
            target_hash = _validate_hash(raw.get("target_hash"), "dependency target_hash")
            if not isinstance(edge_id, str) or not edge_id or edge_id.strip() != edge_id:
                raise ClosureError(f"invalid dependency edge_id for source: {source_hash}")
            if edge_id in edge_ids:
                raise ClosureError(f"duplicate dependency edge_id {edge_id!r} for {source_hash}")
            edge_ids.add(edge_id)
            if kind not in DEPENDENCY_KINDS:
                raise ClosureError(f"unsupported dependency kind for {source_hash}/{edge_id}")
            if set(raw) - {"edge_id", "kind", "target_hash", "condition"}:
                raise ClosureError(f"unknown dependency fields for {source_hash}/{edge_id}")

            active = True
            if "condition" in raw and kind in follow_kinds:
                selection_key = (source_hash, edge_id)
                if selection_key not in condition_values or type(condition_values[selection_key]) is not bool:
                    raise ClosureError(f"conditional dependency requires an explicit boolean selection: {source_hash}/{edge_id}")
                active = condition_values[selection_key]
            should_follow = kind in follow_kinds and active
            edge = {"source_hash": source_hash, "edge_id": edge_id, "kind": kind,
                    "target_hash": target_hash, "included": False}
            if "condition" in raw:
                edge["condition"] = raw["condition"]
            dependencies[(source_hash, edge_id)] = edge
            if should_follow and target_hash not in queued:
                queued.add(target_hash)
                pending.append(target_hash)

    included = set(objects)
    for edge in dependencies.values():
        edge["included"] = edge["target_hash"] in included
    index = {"objects": sorted(objects.values(), key=lambda row: row["hash"]),
             "dependencies": sorted(dependencies.values(), key=lambda row: (row["source_hash"], row["edge_id"])),
             "exports": [], "modules": []}
    try:
        index = normalize(index)
    except LogicalIndexError as exc:
        raise ClosureError(str(exc)) from exc
    if snapshot.snapshot_id != snapshot_id:
        raise ClosureError("Content Store snapshot changed during dependency resolution")
    return {"snapshot_id": snapshot_id, "policy": policy,
            "roots": normalized_roots, "index": index}
