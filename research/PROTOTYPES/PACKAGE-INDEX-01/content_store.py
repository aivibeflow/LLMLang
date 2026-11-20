"""Persistent SQLite prototype for immutable Content Store snapshots.

The store persists opaque content-addressed payloads and dependency-index rows
supplied by a semantic/indexing layer. It does not infer LLMLang dependencies.

A snapshot is a live read transaction over one SQLite WAL generation. Keep it
open for the complete read operation and close all payload streams before
closing the snapshot.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
from typing import Any, Protocol


SCHEMA_VERSION = 1


class ContentStoreError(Exception):
    """Base class for Content Store contract errors."""


class ContentStoreConflict(ContentStoreError):
    """An immutable object or dependency set was reintroduced differently."""


class SnapshotClosed(ContentStoreError):
    """An operation was attempted after the snapshot lease was closed."""


def content_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate_hash(value: Any, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 71
            or not value.startswith("sha256:")
            or any(ch not in "0123456789abcdef" for ch in value[7:])):
        raise ValueError(f"{field} must be a lowercase sha256 Content Hash")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )


def _normalize_dependencies(
    dependencies: Iterable[Mapping[str, Any]],
) -> list[tuple[str, str, str, str | None]]:
    rows = []
    seen = set()
    for edge in dependencies:
        if not isinstance(edge, Mapping):
            raise ValueError("dependency entries must be mappings")
        if set(edge) - {"edge_id", "kind", "target_hash", "condition"}:
            raise ValueError("dependency entry contains unknown fields")
        edge_id, kind = edge.get("edge_id"), edge.get("kind")
        target = _validate_hash(edge.get("target_hash"), "dependency target_hash")
        if not isinstance(edge_id, str) or not edge_id or edge_id.strip() != edge_id:
            raise ValueError("dependency edge_id must be a non-empty trimmed string")
        if not isinstance(kind, str) or not kind or kind.strip() != kind:
            raise ValueError("dependency kind must be a non-empty trimmed string")
        if edge_id in seen:
            raise ValueError(f"duplicate dependency edge_id: {edge_id}")
        seen.add(edge_id)
        condition_json = (
            _canonical_json(edge["condition"]) if "condition" in edge else None
        )
        rows.append((edge_id, kind, target, condition_json))
    return sorted(rows)


class ContentStoreSnapshot(Protocol):
    """Public read contract; one instance is one pinned immutable store view."""

    snapshot_id: str

    def get_object(self, exact_hash: str) -> Mapping[str, Any]: ...
    def get_dependencies(self, source_hash: str) -> Iterator[Mapping[str, Any]]: ...
    def open_object(self, exact_hash: str): ...
    def close(self) -> None: ...
    def __enter__(self) -> ContentStoreSnapshot: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...


class ContentStore(Protocol):
    """Backend-neutral factory for read snapshots."""

    def open_snapshot(self) -> ContentStoreSnapshot: ...


class SQLiteContentStore:
    """Append-only local store; SQLite is derived/reconstructible, not authority."""

    def __init__(self, path: str | os.PathLike):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            schema_statements = (
                """CREATE TABLE IF NOT EXISTS store_metadata (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS objects (
                    row_id INTEGER PRIMARY KEY,
                    content_hash TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    size INTEGER NOT NULL CHECK(size >= 0),
                    payload BLOB NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS dependency_sets (
                    source_hash TEXT PRIMARY KEY REFERENCES objects(content_hash),
                    complete INTEGER NOT NULL CHECK(complete = 1)
                )""",
                """CREATE TABLE IF NOT EXISTS dependencies (
                    source_hash TEXT NOT NULL REFERENCES dependency_sets(source_hash),
                    edge_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target_hash TEXT NOT NULL,
                    condition_json TEXT,
                    PRIMARY KEY(source_hash, edge_id)
                )""",
            )
            for statement in schema_statements:
                connection.execute(statement)
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise ContentStoreError(f"unsupported Content Store schema version: {version}")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.execute(
                "INSERT OR IGNORE INTO store_metadata(key, value) VALUES ('store_uuid', ?)",
                (uuid.uuid4().hex,),
            )
            connection.execute(
                "INSERT OR IGNORE INTO store_metadata(key, value) VALUES ('generation', '0')"
            )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def put_object(
        self,
        payload: bytes,
        kind: str,
        dependencies: Iterable[Mapping[str, Any]],
    ) -> str:
        """Atomically add an immutable object and its complete outgoing edge set.

        Dependency rows are supplied by a semantic/indexing layer. An empty
        iterable explicitly means that the object has no outgoing dependencies.
        Repeating identical input is idempotent; changing kind or edges conflicts.
        """
        if not isinstance(payload, bytes):
            raise ValueError("payload must be bytes")
        if not isinstance(kind, str) or not kind or kind.strip() != kind:
            raise ValueError("kind must be a non-empty trimmed string")
        object_hash = content_hash(payload)
        edges = _normalize_dependencies(dependencies)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT kind, size, payload FROM objects WHERE content_hash = ?",
                (object_hash,),
            ).fetchone()
            changed = False
            if current is None:
                connection.execute(
                    "INSERT INTO objects(content_hash, kind, size, payload) VALUES (?, ?, ?, ?)",
                    (object_hash, kind, len(payload), sqlite3.Binary(payload)),
                )
                changed = True
            elif current != (kind, len(payload), payload):
                raise ContentStoreConflict(
                    f"immutable object metadata/payload conflict for {object_hash}"
                )

            edge_set = connection.execute(
                "SELECT complete FROM dependency_sets WHERE source_hash = ?",
                (object_hash,),
            ).fetchone()
            if edge_set is None:
                connection.execute(
                    "INSERT INTO dependency_sets(source_hash, complete) VALUES (?, 1)",
                    (object_hash,),
                )
                connection.executemany(
                    """INSERT INTO dependencies
                       (source_hash, edge_id, kind, target_hash, condition_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    ((object_hash, *edge) for edge in edges),
                )
                changed = True
            else:
                stored = connection.execute(
                    """SELECT edge_id, kind, target_hash, condition_json
                       FROM dependencies WHERE source_hash = ? ORDER BY edge_id""",
                    (object_hash,),
                ).fetchall()
                if stored != edges:
                    raise ContentStoreConflict(
                        f"immutable dependency set conflict for {object_hash}"
                    )

            if changed:
                connection.execute(
                    "UPDATE store_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation'"
                )
            connection.commit()
            return object_hash
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def open_snapshot(self) -> "SQLiteContentStoreSnapshot":
        """Open a pinned read transaction; its lifetime defines the snapshot."""
        return SQLiteContentStoreSnapshot(self.path)


class SQLiteContentStoreSnapshot:
    """Read-only, generation-pinned view used by the package Provider."""

    def __init__(self, path: str):
        self._connection = sqlite3.connect(path, timeout=30, isolation_level=None)
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._connection.execute("PRAGMA query_only = ON")
        self._connection.execute("BEGIN")
        row = self._connection.execute(
            """SELECT
                 (SELECT value FROM store_metadata WHERE key = 'store_uuid'),
                 (SELECT value FROM store_metadata WHERE key = 'generation')"""
        ).fetchone()
        if row is None or row[0] is None or row[1] is None:
            self._connection.close()
            raise ContentStoreError("Content Store metadata is missing")
        self.snapshot_id = f"sqlite-content-store:{row[0]}:{row[1]}"
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise SnapshotClosed("Content Store snapshot is closed")

    def get_object(self, exact_hash: str) -> dict[str, Any]:
        self._ensure_open()
        exact_hash = _validate_hash(exact_hash, "object hash")
        row = self._connection.execute(
            "SELECT content_hash, kind, size FROM objects WHERE content_hash = ?",
            (exact_hash,),
        ).fetchone()
        if row is None:
            raise KeyError(exact_hash)
        return {"hash": row[0], "kind": row[1], "size": row[2]}

    def get_dependencies(self, source_hash: str) -> Iterator[dict[str, Any]]:
        self._ensure_open()
        source_hash = _validate_hash(source_hash, "dependency source_hash")
        complete = self._connection.execute(
            "SELECT complete FROM dependency_sets WHERE source_hash = ?",
            (source_hash,),
        ).fetchone()
        if complete is None:
            raise KeyError(f"dependency metadata missing for {source_hash}")
        cursor = self._connection.execute(
            """SELECT edge_id, kind, target_hash, condition_json
               FROM dependencies WHERE source_hash = ? ORDER BY edge_id""",
            (source_hash,),
        )

        def rows():
            try:
                while True:
                    self._ensure_open()
                    batch = cursor.fetchmany(128)
                    if not batch:
                        break
                    for edge_id, kind, target_hash, condition_json in batch:
                        result = {
                            "edge_id": edge_id, "kind": kind,
                            "target_hash": target_hash,
                        }
                        if condition_json is not None:
                            result["condition"] = json.loads(condition_json)
                        yield result
            finally:
                cursor.close()

        return rows()

    def open_object(self, exact_hash: str):
        """Open a read-only SQLite BLOB stream; caller must close it."""
        self._ensure_open()
        exact_hash = _validate_hash(exact_hash, "object hash")
        row = self._connection.execute(
            "SELECT row_id FROM objects WHERE content_hash = ?",
            (exact_hash,),
        ).fetchone()
        if row is None:
            raise KeyError(exact_hash)
        return self._connection.blobopen("objects", "payload", row[0], readonly=True)

    def close(self) -> None:
        if not self._closed:
            self._connection.rollback()
            self._connection.close()
            self._closed = True

    def __enter__(self) -> "SQLiteContentStoreSnapshot":
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
