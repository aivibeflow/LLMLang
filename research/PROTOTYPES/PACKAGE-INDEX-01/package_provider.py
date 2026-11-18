"""Disk-backed Provider-to-archive pipeline for the package prototype."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from package_archive import ArchiveError, build_archive
from package_identity import PackageFormatError, parse_manifest
from package_index import DEPENDENCY_KINDS, _canonical


class ProviderError(ValueError):
    """Provider resolution or snapshot access failed."""


FOLLOW_KINDS = {
    "closure": {"required"},
    "roots_only": set(),
    "closure_with_optional": {"required", "optional"},
}


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ProviderError(f"{field} must be an exact sha256 Content Hash")
    if any(ch not in "0123456789abcdef" for ch in value[7:]):
        raise ProviderError(f"{field} must be a lowercase sha256 Content Hash")
    return value


def _rows(connection: sqlite3.Connection, query: str):
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    while True:
        batch = cursor.fetchmany(128)
        if not batch:
            break
        for values in batch:
            yield dict(zip(columns, values))


def _object_payloads(connection: sqlite3.Connection, snapshot):
    for row in _rows(connection, "SELECT hash FROM objects ORDER BY hash"):
        source = snapshot.open_object(row["hash"])
        try:
            yield row["hash"], source
        finally:
            close = getattr(source, "close", None)
            if close is not None:
                close()


def _copy_optional_tables(connection, snapshot):
    exports_reader = getattr(snapshot, "get_exports", None)
    if exports_reader is not None:
        for row in exports_reader():
            if not isinstance(row, Mapping):
                raise ProviderError("invalid export row from Content Store snapshot")
            try:
                connection.execute(
                    "INSERT INTO exports(module_id, name, object_hash) VALUES (?, ?, ?)",
                    (row["module_id"], row["name"], row["object_hash"]),
                )
            except (KeyError, sqlite3.IntegrityError) as exc:
                raise ProviderError(f"invalid or duplicate export row: {exc}") from exc

    modules_reader = getattr(snapshot, "get_modules", None)
    if modules_reader is not None:
        for row in modules_reader():
            if not isinstance(row, Mapping):
                raise ProviderError("invalid module row from Content Store snapshot")
            try:
                members = json.dumps(row["members"], ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False)
                connection.execute(
                    "INSERT INTO modules(module_id, members_json) VALUES (?, ?)",
                    (row["module_id"], members),
                )
            except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as exc:
                raise ProviderError(f"invalid or duplicate module row: {exc}") from exc


def build_archive_from_snapshot(
    roots,
    snapshot,
    manifest: bytes,
    output_path: str | os.PathLike,
    *,
    policy: str | None = None,
    condition_values: Mapping[tuple[str, str], bool] | None = None,
    max_records_in_memory: int = 4096,
    sqlite_cache_kib: int = 4096,
) -> str:
    """Resolve exact dependency closure and build an archive from one snapshot.

    Required snapshot API:
      snapshot_id, get_object(exact_hash), get_dependencies(source_hash),
      open_object(exact_hash). Optional get_exports()/get_modules() supply
      package exports and module rows. Object streams are opened one at a time.

    The traversal queue, visited objects, and dependency rows are disk-backed.
    The final destination is published only after archive validation and a
    final snapshot-token check. This is an experimental provider adapter.
    """
    if not isinstance(manifest, bytes):
        raise ProviderError("manifest must be supplied as UTF-8 bytes")
    try:
        manifest_model = parse_manifest(manifest)
    except PackageFormatError as exc:
        raise ProviderError(str(exc)) from exc

    selected_policy = manifest_model["content"]["dependency_policy"] if policy is None else policy
    if not isinstance(selected_policy, str) or selected_policy not in FOLLOW_KINDS:
        raise ProviderError(f"unsupported dependency policy: {selected_policy!r}")
    if selected_policy != manifest_model["content"]["dependency_policy"]:
        raise ProviderError("requested dependency policy differs from manifest")
    if not isinstance(roots, (list, tuple, set, frozenset)) or not roots:
        raise ProviderError("roots must be a non-empty collection")
    normalized_roots = sorted({_validate_hash(root, "root") for root in roots})
    if len(normalized_roots) != len(roots):
        raise ProviderError("duplicate package root")
    if normalized_roots != sorted(manifest_model["content"]["roots"]):
        raise ProviderError("requested roots differ from manifest content.roots")
    if condition_values is None:
        condition_values = {}
    if not isinstance(condition_values, Mapping):
        raise ProviderError("condition_values must be a mapping")
    if type(max_records_in_memory) is not int or max_records_in_memory < 1:
        raise ProviderError("max_records_in_memory must be a positive integer")
    if type(sqlite_cache_kib) is not int or sqlite_cache_kib < 64:
        raise ProviderError("sqlite_cache_kib must be an integer of at least 64")

    try:
        snapshot_id = snapshot.snapshot_id
    except AttributeError as exc:
        raise ProviderError("snapshot must expose snapshot_id") from exc
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ProviderError("snapshot_id must be a non-empty string")

    destination = Path(output_path)
    if not destination.parent.exists():
        raise ProviderError("output directory does not exist")
    staging_path = None

    try:
        with tempfile.TemporaryDirectory(prefix="llmlang-provider-") as work_dir:
            connection = sqlite3.connect(os.path.join(work_dir, "closure.sqlite3"))
            try:
                connection.execute(f"PRAGMA cache_size = -{sqlite_cache_kib}")
                connection.execute("PRAGMA temp_store = FILE")
                connection.execute("PRAGMA journal_mode = OFF")
                connection.execute("PRAGMA synchronous = OFF")
                connection.executescript("""
                    CREATE TABLE objects (
                        hash TEXT PRIMARY KEY, kind TEXT NOT NULL, size INTEGER NOT NULL
                    );
                    CREATE TABLE queue (
                        hash TEXT PRIMARY KEY, processed INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE dependencies (
                        source_hash TEXT NOT NULL, edge_id TEXT NOT NULL,
                        kind TEXT NOT NULL, target_hash TEXT NOT NULL, condition_json TEXT,
                        PRIMARY KEY (source_hash, edge_id)
                    );
                    CREATE TABLE exports (
                        module_id TEXT NOT NULL, name TEXT NOT NULL, object_hash TEXT NOT NULL,
                        PRIMARY KEY (module_id, name)
                    );
                    CREATE TABLE modules (
                        module_id TEXT PRIMARY KEY, members_json TEXT NOT NULL
                    );
                """)
                connection.executemany(
                    "INSERT INTO queue(hash, processed) VALUES (?, 0)",
                    ((root,) for root in normalized_roots),
                )
                connection.commit()

                follow_kinds = FOLLOW_KINDS[selected_policy]
                while True:
                    pending = connection.execute(
                        "SELECT hash FROM queue WHERE processed = 0 ORDER BY hash LIMIT 1"
                    ).fetchone()
                    if pending is None:
                        break
                    source_hash = pending[0]
                    try:
                        metadata = snapshot.get_object(source_hash)
                    except (KeyError, LookupError) as exc:
                        raise ProviderError(f"missing exact dependency object: {source_hash}") from exc
                    if not isinstance(metadata, Mapping) or metadata.get("hash") != source_hash:
                        raise ProviderError(
                            f"Content Store returned a different hash for exact request {source_hash}"
                        )
                    kind, size = metadata.get("kind"), metadata.get("size")
                    if not isinstance(kind, str) or not kind or type(size) is not int or size < 0:
                        raise ProviderError(f"invalid object metadata for {source_hash}")
                    connection.execute(
                        "INSERT INTO objects(hash, kind, size) VALUES (?, ?, ?)",
                        (source_hash, kind, size),
                    )
                    try:
                        edges = snapshot.get_dependencies(source_hash)
                    except (KeyError, LookupError) as exc:
                        raise ProviderError(f"dependency metadata missing for source: {source_hash}") from exc
                    if edges is None:
                        raise ProviderError(f"dependency metadata missing for source: {source_hash}")

                    for edge in edges:
                        if not isinstance(edge, Mapping):
                            raise ProviderError(f"invalid dependency edge for source: {source_hash}")
                        edge_id, edge_kind = edge.get("edge_id"), edge.get("kind")
                        target_hash = _validate_hash(edge.get("target_hash"), "dependency target_hash")
                        if not isinstance(edge_id, str) or not edge_id or edge_id.strip() != edge_id:
                            raise ProviderError(f"invalid dependency edge_id for source: {source_hash}")
                        if not isinstance(edge_kind, str) or edge_kind not in DEPENDENCY_KINDS:
                            raise ProviderError(f"unsupported dependency kind for {source_hash}/{edge_id}")
                        if set(edge) - {"edge_id", "kind", "target_hash", "condition"}:
                            raise ProviderError(f"unknown dependency fields for {source_hash}/{edge_id}")

                        active = True
                        condition_json = None
                        if "condition" in edge:
                            try:
                                condition_json = _canonical(edge["condition"]).decode("utf-8")
                            except (TypeError, ValueError) as exc:
                                raise ProviderError(
                                    f"invalid condition payload for {source_hash}/{edge_id}"
                                ) from exc
                            if edge_kind in follow_kinds:
                                key = (source_hash, edge_id)
                                if key not in condition_values or type(condition_values[key]) is not bool:
                                    raise ProviderError(
                                        f"conditional dependency requires an explicit boolean selection: {source_hash}/{edge_id}"
                                    )
                                active = condition_values[key]
                        try:
                            connection.execute(
                                """INSERT INTO dependencies
                                   (source_hash, edge_id, kind, target_hash, condition_json)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (source_hash, edge_id, edge_kind, target_hash, condition_json),
                            )
                        except sqlite3.IntegrityError as exc:
                            raise ProviderError(
                                f"duplicate dependency edge_id {edge_id!r} for {source_hash}"
                            ) from exc
                        if edge_kind in follow_kinds and active:
                            connection.execute(
                                "INSERT OR IGNORE INTO queue(hash, processed) VALUES (?, 0)",
                                (target_hash,),
                            )
                    connection.execute("UPDATE queue SET processed = 1 WHERE hash = ?", (source_hash,))
                    connection.commit()

                _copy_optional_tables(connection, snapshot)
                connection.execute("""
                    CREATE TABLE dependency_rows AS
                    SELECT d.source_hash, d.edge_id, d.kind, d.target_hash,
                           CASE WHEN o.hash IS NULL THEN 0 ELSE 1 END AS included,
                           d.condition_json
                    FROM dependencies d LEFT JOIN objects o ON o.hash = d.target_hash
                """)
                connection.execute("CREATE UNIQUE INDEX dependency_rows_key ON dependency_rows(source_hash, edge_id)")
                connection.commit()

                def object_rows():
                    yield from _rows(connection, "SELECT hash, kind, size FROM objects ORDER BY hash")

                def dependency_rows():
                    for row in _rows(connection,
                        """SELECT source_hash, edge_id, kind, target_hash, included, condition_json
                           FROM dependency_rows ORDER BY source_hash, edge_id"""):
                        result = {"source_hash": row["source_hash"], "edge_id": row["edge_id"],
                                  "kind": row["kind"], "target_hash": row["target_hash"],
                                  "included": bool(row["included"])}
                        if row["condition_json"] is not None:
                            result["condition"] = json.loads(row["condition_json"])
                        yield result

                def export_rows():
                    yield from _rows(connection,
                        "SELECT module_id, name, object_hash FROM exports ORDER BY module_id, name")

                def module_rows():
                    for row in _rows(connection,
                        "SELECT module_id, members_json FROM modules ORDER BY module_id"):
                        yield {"module_id": row["module_id"], "members": json.loads(row["members_json"])}

                index_stream = {
                    "objects": object_rows(), "dependencies": dependency_rows(),
                    "exports": export_rows(), "modules": module_rows(),
                }
                fd, staging_path = tempfile.mkstemp(
                    prefix=".llmlang-provider-stage-", dir=str(destination.parent)
                )
                os.close(fd)
                os.unlink(staging_path)
                build_archive(
                    manifest, index_stream, _object_payloads(connection, snapshot),
                    staging_path, max_records_in_memory=max_records_in_memory,
                )
                if snapshot.snapshot_id != snapshot_id:
                    raise ProviderError("Content Store snapshot changed during archive construction")
                os.replace(staging_path, destination)
                staging_path = None
                return str(destination)
            finally:
                connection.close()
    except ProviderError:
        raise
    except (ArchiveError, OSError, sqlite3.Error, ValueError) as exc:
        raise ProviderError(str(exc)) from exc
    finally:
        if staging_path and os.path.exists(staging_path):
            os.unlink(staging_path)
