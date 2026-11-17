"""Experimental package identity model; not a normative LLMLang implementation."""
from __future__ import annotations
import hashlib, re, struct, tomllib
from pathlib import PurePosixPath
from typing import Any

HASH_RE = re.compile(r"^(sha256):([0-9a-f]{64})$")
TOP_KEYS = {"format", "schema_version", "package", "content", "index", "cache"}
TABLE_KEYS = {
    "package": {"id", "name", "version", "description"},
    "content": {"roots", "dependency_policy", "content_root", "resolution_inputs"},
    "index": {"path", "format_version", "logical_hash"},
    "cache": {"indexes"},
}
IDENTITY_TABLES = {"objects", "dependencies", "exports", "modules"}

class PackageFormatError(ValueError):
    pass

def _u32(n: int) -> bytes:
    if not 0 <= n <= 0xFFFFFFFF:
        raise PackageFormatError("canonical value too large")
    return struct.pack(">I", n)

def canonical(value: Any) -> bytes:
    """Explicit typed encoding used only for this research prototype."""
    if value is None: return b"N"
    if value is False: return b"F"
    if value is True: return b"T"
    if isinstance(value, int):
        raw = str(value).encode("ascii")
        return b"I" + _u32(len(raw)) + raw
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return b"S" + _u32(len(raw)) + raw
    if isinstance(value, bytes): return b"B" + _u32(len(value)) + value
    if isinstance(value, list):
        return b"L" + _u32(len(value)) + b"".join(canonical(x) for x in value)
    if isinstance(value, dict):
        pairs = []
        for key, item in value.items():
            if not isinstance(key, str): raise PackageFormatError("map keys must be strings")
            pairs.append((canonical(key), canonical(item)))
        pairs.sort(key=lambda pair: pair[0])
        return b"M" + _u32(len(pairs)) + b"".join(k + v for k, v in pairs)
    raise PackageFormatError(f"unsupported canonical type: {type(value).__name__}")

def digest(domain: str, value: Any) -> str:
    payload = b"LLMLANG\\0" + domain.encode("ascii") + b"\\0" + canonical(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()

def parse_hash(value: str) -> tuple[str, bytes]:
    match = HASH_RE.fullmatch(value)
    if not match: raise PackageFormatError(f"invalid content hash: {value!r}")
    return match.group(1), bytes.fromhex(match.group(2))

def _validate_relative_path(value: str) -> None:
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or "\\\\" in value:
        raise PackageFormatError(f"unsafe relative archive path: {value!r}")

def parse_manifest(raw: bytes) -> dict[str, Any]:
    try: data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PackageFormatError(str(exc)) from exc
    if set(data) - TOP_KEYS: raise PackageFormatError("unknown top-level keys")
    if data.get("format") != "llmlang.package" or data.get("schema_version") != 1:
        raise PackageFormatError("unsupported package format/schema version")
    for table, allowed in TABLE_KEYS.items():
        value = data.get(table)
        if value is not None and (not isinstance(value, dict) or set(value) - allowed):
            raise PackageFormatError(f"invalid or unknown fields in [{table}]")
    content, index = data.get("content"), data.get("index")
    if not isinstance(content, dict) or not isinstance(index, dict):
        raise PackageFormatError("[content] and [index] are required")
    roots = content.get("roots")
    if not isinstance(roots, list) or not roots or not all(isinstance(x, str) for x in roots):
        raise PackageFormatError("content.roots must be a non-empty string array")
    for root in roots: parse_hash(root)
    if len(set(roots)) != len(roots): raise PackageFormatError("duplicate package root")
    if content.get("dependency_policy") not in {"closure", "roots_only", "closure_with_optional"}:
        raise PackageFormatError("unsupported dependency policy")
    if not isinstance(content.get("resolution_inputs", {}), dict):
        raise PackageFormatError("resolution_inputs must be a table")
    parse_hash(content.get("content_root", ""))
    if index.get("format_version") != 1: raise PackageFormatError("unsupported index format version")
    parse_hash(index.get("logical_hash", ""))
    _validate_relative_path(index.get("path", ""))
    cache = data.get("cache", {})
    if not isinstance(cache, dict): raise PackageFormatError("[cache] must be a table")
    for path in cache.get("indexes", []):
        if not isinstance(path, str): raise PackageFormatError("cache index paths must be strings")
        _validate_relative_path(path)
    return data

def logical_index_hash(index: dict[str, Any]) -> str:
    if set(index) != IDENTITY_TABLES:
        raise PackageFormatError("index must contain exactly the identity table set")
    normalized = {}
    for table, records in index.items():
        if not isinstance(records, list): raise PackageFormatError(f"{table} must be a list")
        encoded = [(canonical(record), record) for record in records]
        encoded.sort(key=lambda pair: pair[0])
        if len({key for key, _ in encoded}) != len(encoded):
            raise PackageFormatError(f"duplicate record in {table}")
        normalized[table] = [record for _, record in encoded]
    return digest("package-index.logical.v1", normalized)

def package_content_root(manifest: dict[str, Any], index: dict[str, Any]) -> str:
    actual_index_hash = logical_index_hash(index)
    if manifest["index"]["logical_hash"] != actual_index_hash:
        raise PackageFormatError("declared index logical hash mismatch")
    content = manifest["content"]
    projection = {
        "roots": sorted(content["roots"], key=lambda x: (parse_hash(x)[0], parse_hash(x)[1])),
        "dependency_policy": content["dependency_policy"],
        "explicit_resolution_inputs": content.get("resolution_inputs", {}),
        "index_logical_hash": actual_index_hash,
    }
    return digest("package-content-root.v1", projection)

def verify_manifest(manifest_bytes: bytes, index: dict[str, Any]) -> str:
    manifest = parse_manifest(manifest_bytes)
    actual = package_content_root(manifest, index)
    if actual != manifest["content"]["content_root"]:
        raise PackageFormatError("declared package content root mismatch")
    return actual
