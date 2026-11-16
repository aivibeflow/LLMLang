"""Single-document persistence for semantic graph and binding snapshots."""
from __future__ import annotations
import json
from typing import Iterable
from .binding import BindingError, BindingSnapshot, dumps_binding_snapshot, loads_binding_snapshot
from .persistence import PersistenceError, dumps_graph, loads_graph
from .semantic_graph import ContentStore, RelationStore, Snapshot, canonical_bytes, digest

FORMAT = "llmlang.project-state"
SCHEMA_VERSION = 1

class ProjectStateError(ValueError):
    pass

def dumps_project_state(store: ContentStore, relations: RelationStore,
                        snapshots: Iterable[Snapshot] = (),
                        binding_snapshots: Iterable[BindingSnapshot] = ()) -> bytes:
    graph = json.loads(dumps_graph(store, relations, snapshots))
    bindings = [json.loads(dumps_binding_snapshot(s)) for s in
                sorted(binding_snapshots, key=lambda item: item.root_hash)]
    payload = {"format": FORMAT, "schema_version": SCHEMA_VERSION,
               "graph": graph, "binding_snapshots": bindings}
    return canonical_bytes({"payload": payload, "checksum": digest(payload)}) + b"\\n"

def loads_project_state(data: bytes | str):
    try:
        envelope = json.loads(data)
        payload = envelope["payload"]
    except (TypeError, ValueError, KeyError) as exc:
        raise ProjectStateError("invalid project-state document") from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ProjectStateError("unknown project-state format")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ProjectStateError("unsupported project-state schema")
    if digest(payload) != envelope.get("checksum"):
        raise ProjectStateError("project-state checksum mismatch")
    try:
        store, relations, snapshots = loads_graph(
            canonical_bytes(payload["graph"]))
        bindings = tuple(loads_binding_snapshot(canonical_bytes(item), store)
                         for item in payload["binding_snapshots"])
    except (KeyError, TypeError, ValueError, PersistenceError, BindingError) as exc:
        raise ProjectStateError("invalid project-state contents") from exc
    roots = [item.root_hash for item in bindings]
    if len(roots) != len(set(roots)):
        raise ProjectStateError("duplicate binding snapshot")
    return store, relations, snapshots, tuple(sorted(bindings, key=lambda x: x.root_hash))
