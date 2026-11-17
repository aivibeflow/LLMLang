"""Deterministic JSON persistence for Dependency Graph Prototype 01.

The format is an experimental interchange/snapshot format, not a database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Iterable

from .semantic_graph import (
    ContentStore, Dependency, RelationStore, Snapshot, SemanticValue,
    canonical_bytes, digest, make_snapshot,
)

SCHEMA_VERSION = 1
FORMAT = "llmlang.dependency-graph-store"


class PersistenceError(ValueError):
    """Invalid, corrupt, or unsupported persisted graph."""


def _document(store: ContentStore, relations: RelationStore,
              snapshots: Iterable[Snapshot]) -> dict:
    values = []
    for value_hash in sorted(store.hashes()):
        value = store.get(value_hash)
        values.append({
            "value_hash": value.value_hash,
            "kind": value.kind,
            "payload": value.payload,
            "dependencies": [dep.record() for dep in value.dependencies],
        })
    relation_rows = [list(row) for row in sorted(relations._relations)]
    snapshot_rows = []
    for snapshot in sorted(snapshots, key=lambda item: item.root_hash):
        snapshot_rows.append({
            "root_hash": snapshot.root_hash,
            "selections": [list(pair) for pair in snapshot.selections],
            "parent_roots": list(snapshot.parent_roots),
        })
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "values": values,
        "relations": relation_rows,
        "snapshots": snapshot_rows,
    }


def dumps_graph(store: ContentStore, relations: RelationStore,
                snapshots: Iterable[Snapshot] = ()) -> bytes:
    """Return deterministic bytes; the checksum covers the complete payload."""
    payload = _document(store, relations, snapshots)
    envelope = {
        "payload": payload,
        "checksum": digest(payload),
    }
    return canonical_bytes(envelope) + b"\n"


def save_graph(path: str | os.PathLike[str], store: ContentStore,
               relations: RelationStore,
               snapshots: Iterable[Snapshot] = ()) -> None:
    """Atomically replace path after writing and flushing a complete file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = dumps_graph(store, relations, snapshots)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.",
                                     suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def loads_graph(data: bytes | str) -> tuple[ContentStore, RelationStore, tuple[Snapshot, ...]]:
    """Validate and reconstruct a graph, rejecting corruption and dangling refs."""
    try:
        envelope = json.loads(data)
        payload = envelope["payload"]
        checksum = envelope["checksum"]
    except (TypeError, ValueError, KeyError) as exc:
        raise PersistenceError("invalid graph document") from exc

    if not isinstance(payload, dict):
        raise PersistenceError("payload must be an object")
    if payload.get("format") != FORMAT:
        raise PersistenceError("unknown persistence format")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise PersistenceError(
            f"unsupported schema version: {payload.get('schema_version')!r}"
        )
    if digest(payload) != checksum:
        raise PersistenceError("document checksum mismatch")

    store = ContentStore()
    pending = list(payload.get("values", []))
    while pending:
        remaining = []
        progressed = False
        for row in pending:
            try:
                dependencies = tuple(Dependency(
                    relation=item["relation"],
                    target_hash=item["target_hash"],
                    role=item.get("role", ""),
                    hash_relevant=item.get("hash_relevant", True),
                ) for item in row["dependencies"])
                value_hash = store.put(row["kind"], row["payload"], dependencies)
            except KeyError as exc:
                # A missing target may be a value that appears later in file order.
                missing = str(exc)
                if "unknown dependency:" in missing:
                    remaining.append(row)
                    continue
                raise PersistenceError("malformed semantic value") from exc
            except (TypeError, ValueError) as exc:
                raise PersistenceError("malformed semantic value") from exc
            if value_hash != row.get("value_hash"):
                raise PersistenceError("semantic value hash mismatch")
            progressed = True
        if not progressed and remaining:
            raise PersistenceError("missing dependency or dependency cycle")
        pending = remaining

    relations = RelationStore()
    try:
        for row in payload.get("relations", []):
            if len(row) != 4:
                raise PersistenceError("malformed relation row")
            relations.add(*row)
    except (TypeError, ValueError) as exc:
        raise PersistenceError("malformed relation row") from exc

    snapshots = []
    try:
        for row in payload.get("snapshots", []):
            selections = dict(row["selections"])
            parents = tuple(row["parent_roots"])
            snapshot = make_snapshot(selections, parents)
            if snapshot.root_hash != row["root_hash"]:
                raise PersistenceError("snapshot root hash mismatch")
            for selected_hash in selections.values():
                if selected_hash not in store:
                    raise PersistenceError("snapshot references missing semantic value")
            snapshots.append(snapshot)
    except PersistenceError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise PersistenceError("malformed snapshot") from exc

    return store, relations, tuple(sorted(snapshots, key=lambda item: item.root_hash))


def load_graph(path: str | os.PathLike[str]):
    return loads_graph(Path(path).read_bytes())
