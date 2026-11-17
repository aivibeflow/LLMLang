"""Deterministic streaming ZIP archive experiment for LLMLang packages.

ZIP is only a prototype transport container here, not a normative LLMLang format.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

from package_index import IndexError, TABLES, _canonical, _external_sort_records, validate_streamed_index
from package_identity import PackageFormatError, _u32, canonical as identity_canonical, package_content_root_from_index_hash, parse_manifest

CHUNK_SIZE = 1024 * 1024
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


class ArchiveError(ValueError):
    """Invalid package archive input or integrity failure."""


def _entry_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits = 0
    return info


def _write_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    with archive.open(_entry_info(name), "w", force_zip64=True) as target:
        target.write(data)


def _copy_verified(source: BinaryIO, target: BinaryIO, expected_hash: str, expected_size: int) -> None:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = source.read(CHUNK_SIZE)
        if not chunk:
            break
        if not isinstance(chunk, bytes):
            raise ArchiveError("object streams must return bytes")
        digest.update(chunk)
        size += len(chunk)
        target.write(chunk)
    actual_hash = "sha256:" + digest.hexdigest()
    if actual_hash != expected_hash:
        raise ArchiveError(f"object Content Hash mismatch: expected {expected_hash}, got {actual_hash}")
    if size != expected_size:
        raise ArchiveError(f"object size mismatch for {expected_hash}: expected {expected_size}, got {size}")


def _spool_index(index_stream, directory: str, max_records_in_memory: int) -> dict[str, str]:
    if not isinstance(index_stream, dict) or set(index_stream) != set(TABLES):
        raise ArchiveError("index stream must provide exactly the four logical tables")
    paths = {}
    for table in TABLES:
        path = os.path.join(directory, f"{table}.jsonl")
        with open(path, "w", encoding="utf-8") as output:
            previous = None
            from package_index import _validate_stream_row, key
            for raw in index_stream[table]:
                row = _validate_stream_row(table, raw)
                current = key(table, row)
                if previous is not None and current <= previous:
                    reason = "duplicate key" if current == previous else "not sorted"
                    raise ArchiveError(f"{table} table is {reason}")
                previous = current
                output.write(_canonical(row).decode("utf-8") + "\n")
        paths[table] = path

    validate_streamed_index(
        {table: _table_rows(paths[table]) for table in TABLES},
        max_records_in_memory=max_records_in_memory,
    )
    return paths


def _table_rows(path: str):
    with open(path, "r", encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)

def _logical_index_hash_from_paths(paths, *, max_records_in_memory, temp_dir):
    """Reproduce the identity prototype's logical index hash without materializing tables."""
    hasher = hashlib.sha256()
    hasher.update(b"LLMLANG\0package-index.logical.v1\0")
    ordered_tables = sorted(TABLES, key=identity_canonical)
    hasher.update(b"M" + _u32(len(ordered_tables)))
    for table in ordered_tables:
        hasher.update(identity_canonical(table))
        with open(paths[table], "r", encoding="utf-8") as source:
            count = sum(1 for _ in source)
        hasher.update(b"L" + _u32(count))
        sorted_rows = _external_sort_records(
            _table_rows(paths[table]), key_fn=lambda row: identity_canonical(row),
            max_records_in_memory=max_records_in_memory, temp_dir=temp_dir,
        )
        for row in sorted_rows:
            hasher.update(identity_canonical(row))
    return "sha256:" + hasher.hexdigest()


def _assert_roots_included(manifest, object_rows):
    roots = sorted(manifest["content"]["roots"])
    position = 0
    for row in object_rows:
        while position < len(roots) and roots[position] < row["hash"]:
            raise ArchiveError("package root is not present in included object membership: " + roots[position])
        if position < len(roots) and roots[position] == row["hash"]:
            position += 1
    if position != len(roots):
        raise ArchiveError("package root is not present in included object membership: " + roots[position])


def _index_entry_names(manifest):
    base = manifest["index"]["path"]
    if base in {"manifest.toml", "objects"}:
        raise ArchiveError("manifest index path collides with a reserved archive path")
    return {table: f"{base}/{table}.jsonl" for table in TABLES}


def _verify_manifest_and_index(manifest_bytes, table_paths, *, max_records_in_memory, temp_dir):
    manifest = parse_manifest(manifest_bytes)
    actual_hash = _logical_index_hash_from_paths(
        table_paths, max_records_in_memory=max_records_in_memory, temp_dir=temp_dir
    )
    _assert_roots_included(manifest, _table_rows(table_paths["objects"]))
    try:
        return package_content_root_from_index_hash(manifest, actual_hash)
    except PackageFormatError as exc:
        raise ArchiveError(str(exc)) from exc



def build_archive(
    manifest: bytes,
    index_stream: dict,
    object_stream: Iterable[tuple[str, BinaryIO]],
    output_path: str | os.PathLike,
    *,
    max_records_in_memory: int = 4096,
) -> str:
    """Build an archive atomically from sorted index rows and sorted object streams.

    object_stream yields (ContentHash, readable binary stream) in strictly
    increasing ContentHash order. The caller retains ownership of each stream.
    The output path is replaced only after the complete archive is written.
    """
    if not isinstance(manifest, bytes):
        raise ArchiveError("manifest must be supplied as UTF-8 bytes")
    try:
        manifest.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArchiveError("manifest must contain valid UTF-8") from exc
    if type(max_records_in_memory) is not int or max_records_in_memory < 1:
        raise ArchiveError("max_records_in_memory must be a positive integer")

    destination = Path(output_path)
    if not destination.parent.exists():
        raise ArchiveError("output directory does not exist")

    temp_output = None
    try:
        with tempfile.TemporaryDirectory(prefix="llmlang-package-build-") as work_dir:
            table_paths = _spool_index(index_stream, work_dir, max_records_in_memory)
            manifest_model = parse_manifest(manifest)
            index_entry_names = _index_entry_names(manifest_model)
            _verify_manifest_and_index(manifest, table_paths, max_records_in_memory=max_records_in_memory, temp_dir=work_dir)
            object_rows = _table_rows(table_paths["objects"])
            fd, temp_output = tempfile.mkstemp(prefix=".llmlang-package-", dir=str(destination.parent))
            os.close(fd)

            with zipfile.ZipFile(temp_output, "w", allowZip64=True) as archive:
                _write_bytes(archive, "manifest.toml", manifest)
                for table in TABLES:
                    with archive.open(_entry_info(index_entry_names[table]), "w", force_zip64=True) as target:
                        for row in _table_rows(table_paths[table]):
                            target.write(_canonical(row) + b"\n")

                previous_hash = None
                supplied = iter(object_stream)
                for row in object_rows:
                    expected_hash = row["hash"]
                    if previous_hash is not None and expected_hash <= previous_hash:
                        raise ArchiveError("object index is not strictly sorted")
                    previous_hash = expected_hash
                    try:
                        supplied_hash, source = next(supplied)
                    except StopIteration as exc:
                        raise ArchiveError(f"missing object payload: {expected_hash}") from exc
                    if supplied_hash != expected_hash:
                        raise ArchiveError(
                            f"object stream mismatch: expected {expected_hash}, got {supplied_hash}"
                        )
                    name = f"objects/{expected_hash.split(':', 1)[1]}"
                    with archive.open(_entry_info(name), "w", force_zip64=True) as target:
                        _copy_verified(source, target, expected_hash, row["size"])

                try:
                    extra_hash, _ = next(supplied)
                except StopIteration:
                    pass
                else:
                    raise ArchiveError(f"object payload is absent from index: {extra_hash}")

            os.replace(temp_output, destination)
            temp_output = None
            return str(destination)
    except (IndexError, OSError, zipfile.BadZipFile, ValueError) as exc:
        if isinstance(exc, ArchiveError):
            raise
        raise ArchiveError(str(exc)) from exc
    finally:
        if temp_output and os.path.exists(temp_output):
            os.unlink(temp_output)


def verify_archive(path: str | os.PathLike, *, max_records_in_memory: int = 4096) -> bool:
    """Verify ZIP structure, logical index references, object membership and hashes."""
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ArchiveError("archive contains duplicate entry names")
            if "manifest.toml" not in names:
                raise ArchiveError("manifest.toml is missing")
            manifest_bytes = archive.read("manifest.toml")
            manifest_model = parse_manifest(manifest_bytes)
            index_entry_names = _index_entry_names(manifest_model)
            expected_index_names = set(index_entry_names.values())
            if not expected_index_names <= set(names):
                raise ArchiveError("one or more manifest-declared index tables are missing")

            # Reopen each ZIP member on demand; the validator spools it to disk.
            def replay_table(table):
                with archive.open(index_entry_names[table], "r") as source:
                    for line in source:
                        yield json.loads(line)
            validate_streamed_index(
                {table: replay_table(table) for table in TABLES},
                max_records_in_memory=max_records_in_memory,
            )
            with tempfile.TemporaryDirectory(prefix="llmlang-package-verify-") as work_dir:
                table_paths = {}
                for table in TABLES:
                    temp_path = os.path.join(work_dir, f"{table}.jsonl")
                    with open(temp_path, "w", encoding="utf-8") as output:
                        for row in replay_table(table):
                            output.write(_canonical(row).decode("utf-8") + "\n")
                    table_paths[table] = temp_path
                _verify_manifest_and_index(
                    manifest_bytes, table_paths,
                    max_records_in_memory=max_records_in_memory, temp_dir=work_dir,
                )

            object_rows = replay_table("objects")
            expected_object_names = set()
            for row in object_rows:
                name = f"objects/{row['hash'].split(':', 1)[1]}"
                expected_object_names.add(name)
                if name not in names:
                    raise ArchiveError(f"object payload is missing: {row['hash']}")
                digest = hashlib.sha256()
                size = 0
                with archive.open(name, "r") as source:
                    while True:
                        chunk = source.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                if "sha256:" + digest.hexdigest() != row["hash"]:
                    raise ArchiveError(f"object Content Hash mismatch: {row['hash']}")
                if size != row["size"]:
                    raise ArchiveError(f"object size mismatch: {row['hash']}")

            allowed = {"manifest.toml"} | expected_index_names | expected_object_names
            if set(names) != allowed:
                raise ArchiveError("archive contains unexpected entries")
            return True
    except ArchiveError:
        raise
    except PackageFormatError as exc:
        raise ArchiveError(str(exc)) from exc
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, IndexError) as exc:
        raise ArchiveError(str(exc)) from exc
