"""Experimental in-memory semantic workspace engine for RT-19.

This is a lifecycle/transaction prototype, not a canonical LLMLang SPG schema,
wire format, compiler, or MCP server.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, Literal


FORMAT_VERSION = 1


class ToolchainError(Exception):
    """Base class for expected domain errors."""


class NotFound(ToolchainError):
    pass


class StaleRevision(ToolchainError):
    pass


class StaleObject(ToolchainError):
    pass


class SemanticConflict(ToolchainError):
    pass


class InvalidSnapshot(ToolchainError):
    pass


def canonical_json(value: Any) -> bytes:
    """Prototype-only canonical JSON encoding (not the final LLMLang encoding)."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


@dataclass(frozen=True, init=False)
class Entity:
    stable_id: str
    kind: str
    _payload_json: bytes

    def __init__(self, stable_id: str, kind: str, payload: dict[str, Any]) -> None:
        if not isinstance(stable_id, str) or not stable_id or not isinstance(kind, str) or not kind:
            raise ValueError("stable_id and kind must be non-empty strings")
        if not isinstance(payload, dict):
            raise ValueError("entity payload must be a JSON object")
        encoded_payload = canonical_json(payload)
        # Fail at construction for values outside the JSON data model.
        json.loads(encoded_payload)
        object.__setattr__(self, "stable_id", stable_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "_payload_json", encoded_payload)

    @property
    def payload(self) -> dict[str, Any]:
        # Return a detached copy so callers cannot mutate stored entity state.
        return json.loads(self._payload_json)

    def encoded(self) -> bytes:
        return canonical_json({"kind": self.kind, "payload": self.payload})

    @property
    def content_hash(self) -> str:
        return digest(self.encoded())


@dataclass(frozen=True)
class Snapshot:
    root_hash: str
    entities: dict[str, str]  # Stable ID -> immutable Entity Content Hash


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    base_snapshot: str
    working_snapshot: str
    revision: int
    state: Literal["open", "accepted", "discarded"]


@dataclass
class _Workspace:
    workspace_id: str
    base_snapshot: str
    working_snapshot: str
    revision: int = 0
    state: Literal["open", "accepted", "discarded"] = "open"
    lock: RLock = field(default_factory=RLock, repr=False, compare=False)


@dataclass(frozen=True)
class Change:
    action: Literal["add", "update", "remove"]
    stable_id: str
    expected_hash: str | None
    kind: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChangeSet:
    changeset_id: str
    workspace_id: str
    base_revision: int
    changes: tuple[Change, ...]


class InMemoryToolchain:
    """Minimal semantic API with immutable objects and isolated workspaces."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._snapshots: dict[str, Snapshot] = {}
        self._workspaces: dict[str, _Workspace] = {}
        self._accepted: set[str] = set()
        self._lock = RLock()

    def _store_entity(self, entity: Entity) -> str:
        encoded = entity.encoded()
        object_hash = digest(encoded)
        self._objects.setdefault(object_hash, encoded)
        return object_hash

    def _snapshot(self, entities: dict[str, str]) -> Snapshot:
        normalized = dict(sorted(entities.items()))
        root = digest(canonical_json({"entities": normalized, "format_version": FORMAT_VERSION}))
        snapshot = Snapshot(root, normalized)
        self._snapshots.setdefault(root, snapshot)
        return self._snapshots[root]

    def create_snapshot(self, entities: list[Entity]) -> str:
        mapping: dict[str, str] = {}
        for entity in entities:
            if entity.stable_id in mapping:
                raise SemanticConflict(f"duplicate Stable ID: {entity.stable_id}")
            mapping[entity.stable_id] = self._store_entity(entity)
        return self._snapshot(mapping).root_hash

    def open_workspace(self, snapshot_id: str) -> Workspace:
        with self._lock:
            if snapshot_id not in self._snapshots:
                raise NotFound(f"snapshot not found: {snapshot_id}")
            workspace = _Workspace(
                workspace_id="ws-" + os.urandom(12).hex(),
                base_snapshot=snapshot_id,
                working_snapshot=snapshot_id,
            )
            self._workspaces[workspace.workspace_id] = workspace
            return self._workspace_view(workspace)

    @staticmethod
    def _workspace_view(workspace: _Workspace) -> Workspace:
        return Workspace(
            workspace.workspace_id, workspace.base_snapshot,
            workspace.working_snapshot, workspace.revision, workspace.state,
        )

    def _get_workspace(self, workspace_id: str) -> _Workspace:
        try:
            return self._workspaces[workspace_id]
        except KeyError as exc:
            raise NotFound(f"workspace not found: {workspace_id}") from exc

    def get_workspace(self, workspace_id: str) -> Workspace:
        return self._workspace_view(self._get_workspace(workspace_id))

    def get_entity(self, snapshot_id: str, stable_id: str) -> Entity:
        try:
            object_hash = self._snapshots[snapshot_id].entities[stable_id]
            value = json.loads(self._objects[object_hash])
        except KeyError as exc:
            raise NotFound(f"entity not found: {stable_id}") from exc
        return Entity(stable_id=stable_id, kind=value["kind"], payload=value["payload"])

    def propose(
        self, workspace_id: str, base_revision: int, changes: list[Change],
        changeset_id: str | None = None,
    ) -> ChangeSet:
        if not changes:
            raise ValueError("Change Set must contain at least one change")
        return ChangeSet(
            changeset_id or "cs-" + os.urandom(12).hex(),
            workspace_id, base_revision, tuple(changes),
        )

    def apply(self, changeset: ChangeSet, expected_revision: int) -> str:
        workspace = self._get_workspace(changeset.workspace_id)
        with workspace.lock:
            if workspace.state != "open":
                raise SemanticConflict(f"workspace is {workspace.state}")
            if workspace.revision != expected_revision or changeset.base_revision != expected_revision:
                raise StaleRevision(
                    f"workspace revision is {workspace.revision}, expected {expected_revision}"
                )
            current = self._snapshots[workspace.working_snapshot]
            next_entities = dict(current.entities)
            seen: set[str] = set()

            # Validate the entire Change Set against one baseline before publishing.
            for change in changeset.changes:
                if not change.stable_id or change.stable_id in seen:
                    raise SemanticConflict("empty or duplicate target Stable ID in Change Set")
                seen.add(change.stable_id)
                actual = current.entities.get(change.stable_id)
                if change.action == "add":
                    if actual is not None or change.expected_hash is not None:
                        raise SemanticConflict(f"entity already exists or add precondition invalid: {change.stable_id}")
                    if change.kind is None or change.payload is None:
                        raise ValueError("add requires kind and payload")
                elif change.action in ("update", "remove"):
                    if actual is None:
                        raise NotFound(f"entity not found: {change.stable_id}")
                    if change.expected_hash != actual:
                        raise StaleObject(f"stale object {change.stable_id}: expected {change.expected_hash}, actual {actual}")
                    if change.action == "update" and (change.kind is None or change.payload is None):
                        raise ValueError("update requires kind and payload")
                else:
                    raise ValueError(f"unsupported action: {change.action}")

            # Only after all preconditions pass do we create immutable objects and a new root.
            for change in changeset.changes:
                if change.action == "remove":
                    del next_entities[change.stable_id]
                else:
                    entity = Entity(change.stable_id, change.kind or "", change.payload or {})
                    next_entities[change.stable_id] = self._store_entity(entity)

            new_snapshot = self._snapshot(next_entities)
            workspace.working_snapshot = new_snapshot.root_hash
            workspace.revision += 1
            return new_snapshot.root_hash

    def accept(self, workspace_id: str, expected_revision: int) -> str:
        workspace = self._get_workspace(workspace_id)
        with workspace.lock:
            if workspace.state != "open":
                raise SemanticConflict(f"workspace is {workspace.state}")
            if workspace.revision != expected_revision:
                raise StaleRevision(
                    f"workspace revision is {workspace.revision}, expected {expected_revision}"
                )
            self._accepted.add(workspace.working_snapshot)
            workspace.state = "accepted"
            return workspace.working_snapshot

    def export_snapshot(
        self, snapshot_id: str, path: str | Path, expected_file_hash: str | None = None,
    ) -> str:
        if snapshot_id not in self._accepted:
            raise SemanticConflict("only accepted snapshots may be exported")
        snapshot = self._snapshots[snapshot_id]
        entities = []
        for stable_id, object_hash in snapshot.entities.items():
            value = json.loads(self._objects[object_hash])
            entities.append({
                "stable_id": stable_id,
                "kind": value["kind"],
                "payload": value["payload"],
                "content_hash": object_hash,
            })
        document = {
            "format_version": FORMAT_VERSION,
            "snapshot_root": snapshot_id,
            "entities": entities,
        }
        data = canonical_json(document) + b"\n"
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            current_hash = digest(destination.read_bytes())
            if expected_file_hash is None or current_hash != expected_file_hash:
                raise StaleObject("repository file changed outside this Toolchain export")
        elif expected_file_hash is not None:
            raise StaleObject("expected repository file is missing")

        fd, temporary = tempfile.mkstemp(prefix=".llmlang-export-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return digest(data)

    def import_snapshot(self, path: str | Path) -> str:
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            if type(document["format_version"]) is not int or document["format_version"] != FORMAT_VERSION:
                raise InvalidSnapshot("unsupported repository format version")
            mapping: dict[str, str] = {}
            for item in document["entities"]:
                entity = Entity(item["stable_id"], item["kind"], item["payload"])
                if entity.stable_id in mapping:
                    raise InvalidSnapshot(f"duplicate Stable ID: {entity.stable_id}")
                if entity.content_hash != item["content_hash"]:
                    raise InvalidSnapshot(f"entity hash mismatch: {entity.stable_id}")
                mapping[entity.stable_id] = self._store_entity(entity)
            snapshot = self._snapshot(mapping)
            if snapshot.root_hash != document["snapshot_root"]:
                raise InvalidSnapshot("snapshot root mismatch")
            return snapshot.root_hash
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, InvalidSnapshot):
                raise
            raise InvalidSnapshot(f"malformed repository representation: {exc}") from exc
