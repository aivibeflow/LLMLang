"""Executable logical package-index schema and deterministic merge experiment.

This is an in-memory research prototype, not the binary index wire format.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

HASH_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
TABLES = ("objects", "dependencies", "exports", "modules")
FIELDS = {
    "objects": {"hash", "kind", "size"},
    "dependencies": {"source_hash", "edge_id", "kind", "target_hash", "included", "condition"},
    "exports": {"module_id", "name", "object_hash"},
    "modules": {"module_id", "members"},
}
REQUIRED = {
    "objects": {"hash", "kind", "size"},
    "dependencies": {"source_hash", "edge_id", "kind", "target_hash", "included"},
    "exports": {"module_id", "name", "object_hash"},
    "modules": {"module_id", "members"},
}
DEPENDENCY_KINDS = {"required", "optional", "target", "evidence"}


class IndexError(ValueError):
    """Invalid logical index or merge conflict."""


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise IndexError(f"{field} must be a lowercase sha256 Content Hash")
    return value


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise IndexError(f"{field} must be a non-empty canonical identifier")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def key(table: str, row: dict[str, Any]) -> tuple:
    if table == "objects":
        return (bytes.fromhex(_hash(row["hash"], "objects.hash").split(":")[1]),)
    if table == "dependencies":
        return (_hash(row["source_hash"], "dependencies.source_hash"),
                _id(row["edge_id"], "dependencies.edge_id"))
    if table == "exports":
        return (_id(row["module_id"], "exports.module_id"),
                _id(row["name"], "exports.name"))
    if table == "modules":
        return (_id(row["module_id"], "modules.module_id"),)
    raise IndexError(f"unknown table: {table}")


def normalize(index: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(index, dict) or set(index) != set(TABLES):
        raise IndexError("index must contain exactly objects, dependencies, exports, modules")
    result: dict[str, list[dict[str, Any]]] = {}
    for table in TABLES:
        rows = index[table]
        if not isinstance(rows, list):
            raise IndexError(f"{table} must be an array")
        normalized = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise IndexError(f"{table} rows must be objects")
            if set(row) - FIELDS[table] or REQUIRED[table] - set(row):
                raise IndexError(f"{table} row has missing or unknown fields")
            row = deepcopy(row)
            k = key(table, row)
            if k in seen:
                raise IndexError(f"duplicate key in {table}: {k!r}")
            seen.add(k)
            if table == "objects":
                _hash(row["hash"], "objects.hash")
                _id(row["kind"], "objects.kind")
                if type(row["size"]) is not int or row["size"] < 0:
                    raise IndexError("objects.size must be a non-negative integer")
            elif table == "dependencies":
                _hash(row["source_hash"], "dependencies.source_hash")
                _id(row["edge_id"], "dependencies.edge_id")
                _hash(row["target_hash"], "dependencies.target_hash")
                if row["kind"] not in DEPENDENCY_KINDS:
                    raise IndexError("unsupported dependency kind")
                if type(row["included"]) is not bool:
                    raise IndexError("dependencies.included must be boolean")
                if "condition" in row:
                    _canonical(row["condition"])
            elif table == "exports":
                _id(row["module_id"], "exports.module_id")
                _id(row["name"], "exports.name")
                _hash(row["object_hash"], "exports.object_hash")
            else:
                _id(row["module_id"], "modules.module_id")
                if not isinstance(row["members"], list):
                    raise IndexError("modules.members must be an array")
                members = [_hash(x, "modules.members[]") for x in row["members"]]
                if len(members) != len(set(members)):
                    raise IndexError("duplicate module member")
                row["members"] = sorted(members, key=lambda x: bytes.fromhex(x.split(":")[1]))
            normalized.append(row)
        normalized.sort(key=lambda row: key(table, row))
        result[table] = normalized
    _validate_references(result)
    return result


def _validate_references(index: dict[str, list[dict[str, Any]]]) -> None:
    objects = {row["hash"] for row in index["objects"]}
    modules = {row["module_id"] for row in index["modules"]}
    for row in index["dependencies"]:
        if row["source_hash"] not in objects:
            raise IndexError("dependency source is not an included object")
        if row["included"] and row["target_hash"] not in objects:
            raise IndexError("included dependency target is absent from objects")
    for row in index["modules"]:
        if not set(row["members"]) <= objects:
            raise IndexError("module references an absent object")
    for row in index["exports"]:
        if row["module_id"] not in modules:
            raise IndexError("export references an absent module")
        if row["object_hash"] not in objects:
            raise IndexError("export references an absent object")


def logical_hash(index: dict[str, Any]) -> str:
    normalized = normalize(index)
    payload = b"LLMLANG\0package-index.logical.prototype-01\0" + _canonical(normalized)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def merge(*indexes: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not indexes:
        raise IndexError("merge requires at least one index")
    inputs = [normalize(index) for index in indexes]
    output = {table: {} for table in TABLES}
    for index in inputs:
        for table in TABLES:
            for row in index[table]:
                k = key(table, row)
                previous = output[table].get(k)
                if previous is not None and _canonical(previous) != _canonical(row):
                    raise IndexError(f"conflicting record in {table} for key {k!r}")
                output[table][k] = row
    merged = {table: list(output[table].values()) for table in TABLES}
    return normalize(merged)


def _validate_stream_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    """Validate one row without materializing a table or its cross-table references."""
    if not isinstance(row, dict):
        raise IndexError(f"{table} rows must be objects")
    if set(row) - FIELDS[table] or REQUIRED[table] - set(row):
        raise IndexError(f"{table} row has missing or unknown fields")
    row = deepcopy(row)
    # key() validates the key fields and gives a comparable canonical key.
    key(table, row)
    if table == "objects":
        _hash(row["hash"], "objects.hash")
        _id(row["kind"], "objects.kind")
        if type(row["size"]) is not int or row["size"] < 0:
            raise IndexError("objects.size must be a non-negative integer")
    elif table == "dependencies":
        _hash(row["source_hash"], "dependencies.source_hash")
        _id(row["edge_id"], "dependencies.edge_id")
        _hash(row["target_hash"], "dependencies.target_hash")
        if row["kind"] not in DEPENDENCY_KINDS:
            raise IndexError("unsupported dependency kind")
        if type(row["included"]) is not bool:
            raise IndexError("dependencies.included must be boolean")
        if "condition" in row:
            _canonical(row["condition"])
    elif table == "exports":
        _hash(row["object_hash"], "exports.object_hash")
    elif table == "modules":
        if not isinstance(row["members"], list):
            raise IndexError("modules.members must be an array")
        members = [_hash(x, "modules.members[]") for x in row["members"]]
        if len(members) != len(set(members)):
            raise IndexError("duplicate module member")
        row["members"] = sorted(members, key=lambda x: bytes.fromhex(x.split(":")[1]))
    return row


def merge_sorted_rows(table: str, *streams):
    """Lazily merge canonical sorted row iterables for one table.

    Memory use is O(number of streams), excluding the current/output rows.
    Each input stream must be strictly increasing by the table's canonical key.
    Equal keys across different streams are deduplicated only when their complete
    logical records match. A repeated key within one input stream is invalid.
    Cross-table reference validation is intentionally a separate operation.
    """
    import heapq

    if table not in TABLES:
        raise IndexError(f"unknown table: {table}")
    if not streams:
        raise IndexError("merge_sorted_rows requires at least one stream")

    iterators = [iter(stream) for stream in streams]
    previous_keys = [None] * len(iterators)
    heap = []

    def advance(stream_id):
        try:
            raw = next(iterators[stream_id])
        except StopIteration:
            return
        row = _validate_stream_row(table, raw)
        row_key = key(table, row)
        previous = previous_keys[stream_id]
        if previous is not None and row_key <= previous:
            if row_key == previous:
                raise IndexError(f"duplicate key in input stream for {table}: {row_key!r}")
            raise IndexError(f"input stream is not sorted for {table}: {row_key!r}")
        previous_keys[stream_id] = row_key
        heapq.heappush(heap, (row_key, stream_id, row))

    for stream_id in range(len(iterators)):
        advance(stream_id)

    while heap:
        current_key = heap[0][0]
        same_key_rows = []
        while heap and heap[0][0] == current_key:
            _, stream_id, row = heapq.heappop(heap)
            same_key_rows.append(row)
            advance(stream_id)

        canonical_rows = {_canonical(row) for row in same_key_rows}
        if len(canonical_rows) != 1:
            raise IndexError(f"conflicting record in {table} for key {current_key!r}")
        yield same_key_rows[0]


def merge_sorted_indexes(index_streams: list[dict[str, Any]]) -> dict[str, Any]:
    """Return lazy per-table merged iterators from sorted index table streams.

    Each input is a mapping of table name to an iterable of already-sorted rows.
    The returned table values are one-shot iterators. This function does not
    materialize the merged tables and does not perform cross-table validation.
    """
    if not index_streams:
        raise IndexError("merge_sorted_indexes requires at least one index stream")
    for index in index_streams:
        if not isinstance(index, dict) or set(index) != set(TABLES):
            raise IndexError("each streamed index must provide exactly the four tables")
    return {
        table: merge_sorted_rows(table, *(index[table] for index in index_streams))
        for table in TABLES
    }
