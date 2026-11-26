"""Indexed LZ4-compressed Protobuf storage for resolved syscall package records."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.message import DecodeError
import lz4.block


PROFILE = "llmlang.syscalls.storage.v1"
DUMP = "records.dump"
INDEX = "records.index.json"
MAGIC = b"LLSPG\x01\r\n"
HEADER = struct.Struct("<II32s")
MAX_RECORD_SIZE = 1 << 20
MAX_COMPRESSED_SIZE = MAX_RECORD_SIZE + MAX_RECORD_SIZE // 255 + 16
MAX_INDEX_SIZE = 16 << 20
MAX_DEPTH = 24


class StorageError(ValueError):
    """An unsupported, missing, or corrupt package record."""


def _record_type():
    definition = descriptor_pb2.FileDescriptorProto(
        name="storage.proto", package=PROFILE, syntax="proto3"
    )
    field = descriptor_pb2.FieldDescriptorProto
    optional = field.LABEL_OPTIONAL
    repeated = field.LABEL_REPEATED
    strings = field.TYPE_STRING
    message = field.TYPE_MESSAGE
    fields = {
        "Record": (("key", strings, optional, None), ("content", message, optional, "Object")),
        "Object": (("fields", message, repeated, "Field"),),
        "Field": (("key", strings, optional, None), ("value", message, optional, "Value")),
        "List": (("values", message, repeated, "Value"),),
        "Value": (
            ("null_value", field.TYPE_BOOL, optional, None),
            ("bool_value", field.TYPE_BOOL, optional, None),
            ("int_value", field.TYPE_SINT64, optional, None),
            ("string_value", strings, optional, None),
            ("list_value", message, optional, "List"),
            ("object_value", message, optional, "Object"),
        ),
    }
    for name, children in fields.items():
        current = definition.message_type.add(name=name)
        if name == "Value":
            current.oneof_decl.add(name="kind")
        for number, (label, kind, cardinality, target) in enumerate(children, 1):
            member = current.field.add(name=label, number=number, type=kind, label=cardinality)
            if target is not None:
                member.type_name = f".{PROFILE}.{target}"
            if name == "Value":
                member.oneof_index = 0
    pool = descriptor_pool.DescriptorPool()
    pool.Add(definition)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName(f"{PROFILE}.Record"))


Record = _record_type()


def _set_object(target, value, depth):
    if not all(isinstance(key, str) for key in value):
        raise StorageError("record object keys must be strings")
    target.SetInParent()
    for key in sorted(value):
        _set_value(target.fields.add(key=key).value, value[key], depth)


def _set_value(target, value, depth):
    if depth > MAX_DEPTH:
        raise StorageError("record exceeds nesting limit")
    if value is None:
        target.null_value = True
    elif type(value) is bool:
        target.bool_value = value
    elif type(value) is int and -(1 << 63) <= value < 1 << 63:
        target.int_value = value
    elif isinstance(value, str):
        target.string_value = value
    elif isinstance(value, list):
        target.list_value.SetInParent()
        for item in value:
            _set_value(target.list_value.values.add(), item, depth + 1)
    elif isinstance(value, dict):
        _set_object(target.object_value, value, depth + 1)
    else:
        raise StorageError(f"unsupported record field {type(value).__name__}")


def _get_object(value, depth):
    result = {}
    previous = None
    for entry in value.fields:
        if previous is not None and entry.key <= previous:
            raise StorageError("record keys are duplicated or out of order")
        result[entry.key] = _get_value(entry.value, depth)
        previous = entry.key
    return result


def _get_value(value, depth):
    if depth > MAX_DEPTH:
        raise StorageError("record exceeds nesting limit")
    kind = value.WhichOneof("kind")
    if kind == "null_value" and value.null_value:
        return None
    if kind in ("int_value", "bool_value", "string_value"):
        return getattr(value, kind)
    if kind == "list_value":
        return [_get_value(item, depth + 1) for item in value.list_value.values]
    if kind == "object_value":
        return _get_object(value.object_value, depth + 1)
    raise StorageError("invalid or missing Protobuf field kind")


def _encode(key, content):
    if not isinstance(key, str) or not key or not isinstance(content, dict):
        raise StorageError("record requires a nonempty string key and object content")
    message = Record(key=key)
    _set_object(message.content, content, 0)
    data = message.SerializeToString(deterministic=True)
    if not 1 <= len(data) <= MAX_RECORD_SIZE:
        raise StorageError("record exceeds byte limit")
    return data


def _logical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def content_hash(key, content):
    """Identify a logical record independently of the compression and index format."""
    material = _logical_bytes({"key": key, "content": content})
    return sha256(b"llmlang-spg-content/v1\x00" + material).hexdigest()


def _entry(offset, length, digest):
    return {"data_file": DUMP, "offset": offset, "compressed_length": length,
            "content_hash": digest.hex()}


def _index_bytes(entries):
    data = _logical_bytes({"profile": PROFILE, "entries": entries}) + b"\n"
    if len(data) > MAX_INDEX_SIZE:
        raise StorageError("index exceeds byte limit")
    return data


def _write_index(path, entries):
    temporary = None
    try:
        with NamedTemporaryFile(dir=path, delete=False) as output:
            temporary = Path(output.name)
            output.write(_index_bytes(entries))
        temporary.replace(path / INDEX)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_records(records, path):
    """Export records in key order with one independently decodable frame per object."""
    path = Path(path)
    if not isinstance(records, dict) or not all(isinstance(key, str) for key in records):
        raise StorageError("records must be an object indexed by string keys")
    path.mkdir(parents=True, exist_ok=True)
    entries = {}
    temporary = None
    try:
        with NamedTemporaryFile(dir=path, delete=False) as output:
            temporary = Path(output.name)
            output.write(MAGIC)
            for key, content in sorted(records.items()):
                raw = _encode(key, content)
                block = lz4.block.compress(raw, mode="fast", acceleration=1, store_size=False)
                digest = bytes.fromhex(content_hash(key, content))
                output.write(HEADER.pack(len(block), len(raw), digest))
                entries[key] = _entry(output.tell(), len(block), digest)
                output.write(block)
        _index_bytes(entries)
        temporary.replace(path / DUMP)
        _write_index(path, entries)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return entries


def _valid_size(compressed, size):
    return 1 <= compressed <= MAX_COMPRESSED_SIZE and 1 <= size <= MAX_RECORD_SIZE


def _read_frame(stream, header):
    if len(header) != HEADER.size:
        raise StorageError("truncated record header")
    compressed, size, digest = HEADER.unpack(header)
    if not _valid_size(compressed, size):
        raise StorageError("invalid frame size")
    offset = stream.tell()
    block = stream.read(compressed)
    if len(block) != compressed:
        raise StorageError("truncated record block")
    try:
        raw = lz4.block.decompress(block, uncompressed_size=size)
        if len(raw) != size:
            raise StorageError("decompressed record size mismatch")
        record = Record.FromString(raw)
        content = _get_object(record.content, 0)
        if _encode(record.key, content) != raw:
            raise StorageError("noncanonical Protobuf record")
        if content_hash(record.key, content) != digest.hex():
            raise StorageError("record content hash mismatch")
    except (DecodeError, lz4.block.LZ4BlockError) as error:
        raise StorageError("unreadable Protobuf or LZ4 record") from error
    return record.key, content, _entry(offset, compressed, digest)


def _scan(path):
    entries = {}
    previous = None
    with (path / DUMP).open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise StorageError("unsupported or corrupt dump profile")
        while header := stream.read(HEADER.size):
            key, _, entry = _read_frame(stream, header)
            if previous is not None and key <= previous:
                raise StorageError("record keys are duplicated or out of order")
            entries[key] = entry
            previous = key
    return entries


def rebuild_index(path):
    """Rebuild a missing or damaged index only from a fully validated dump."""
    path = Path(path)
    entries = _scan(path)
    _write_index(path, entries)
    return entries


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StorageError("duplicate key in index")
        result[key] = value
    return result


def _read_index(path):
    with (path / INDEX).open("rb") as stream:
        data = stream.read(MAX_INDEX_SIZE + 1)
    if len(data) > MAX_INDEX_SIZE:
        raise StorageError("index exceeds byte limit")
    try:
        index = json.loads(data, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
        raise StorageError("invalid index encoding") from error
    if not isinstance(index, dict) or set(index) != {"profile", "entries"}:
        raise StorageError("invalid index object")
    entries = index["entries"]
    if index["profile"] != PROFILE or not isinstance(entries, dict):
        raise StorageError("unsupported index profile")
    next_offset = len(MAGIC) + HEADER.size
    for key, entry in sorted(entries.items()):
        if not key or not isinstance(entry, dict) or set(entry) != {
            "data_file", "offset", "compressed_length", "content_hash"
        }:
            raise StorageError("invalid index entry")
        digest = entry["content_hash"]
        length = entry["compressed_length"]
        if not isinstance(digest, str) or len(digest) != 64 or not all(
            char in "0123456789abcdef" for char in digest
        ):
            raise StorageError("invalid index content hash")
        if (entry["data_file"] != DUMP or type(entry["offset"]) is not int
                or entry["offset"] != next_offset or type(length) is not int
                or not 1 <= length <= MAX_COMPRESSED_SIZE):
            raise StorageError("invalid indexed record range")
        next_offset += length + HEADER.size
    if (path / DUMP).stat().st_size != next_offset - HEADER.size:
        raise StorageError("index ranges do not describe dump length")
    return entries


def verify_records(path):
    """Check every indexed range and record payload in a package directory."""
    path = Path(path)
    entries = _read_index(path)
    if _scan(path) != entries:
        raise StorageError("index does not describe the dump")
    return entries


def _load_range(path, key, entry):
    with (path / DUMP).open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise StorageError("unsupported or corrupt dump profile")
        stream.seek(entry["offset"] - HEADER.size)
        stored_key, content, observed = _read_frame(stream, stream.read(HEADER.size))
    if stored_key != key or observed != entry:
        raise StorageError("indexed range describes a different record")
    return content


def load_record(path, key, *, cache=None):
    """Resolve one indexed object, rebuilding a damaged index on validated data."""
    path = Path(path)
    try:
        entries = _read_index(path)
    except (StorageError, FileNotFoundError):
        entries = rebuild_index(path)
    else:
        if key not in entries:
            # A dump may have been published while its old index was still present.
            entries = rebuild_index(path)
    if key not in entries:
        raise StorageError(f"record {key!r} is absent")
    entry = entries[key]
    digest = entry["content_hash"]
    if cache is not None and digest in cache:
        content = cache[digest]
        _encode(key, content)
        if content_hash(key, content) != digest:
            raise StorageError("cached record content hash mismatch")
        return content
    try:
        content = _load_range(path, key, entry)
    except StorageError:
        entries = rebuild_index(path)
        if key not in entries:
            raise StorageError(f"record {key!r} is absent")
        entry = entries[key]
        content = _load_range(path, key, entry)
    if cache is not None:
        cache[entry["content_hash"]] = content
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "rebuild"):
        subs.add_parser(command).add_argument("path", type=Path)
    export = subs.add_parser("export")
    export.add_argument("input", type=Path)
    export.add_argument("path", type=Path)
    lookup = subs.add_parser("load")
    lookup.add_argument("path", type=Path)
    lookup.add_argument("key")
    args = parser.parse_args()
    try:
        match args.command:
            case "verify":
                result = verify_records(args.path)
            case "rebuild":
                result = rebuild_index(args.path)
            case "load":
                result = load_record(args.path, args.key)
            case "export":
                source = json.loads(args.input.read_bytes(), object_pairs_hook=_unique_object)
                result = export_records(source, args.path)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    except (StorageError, OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(1, f"storage: {error}\n")


if __name__ == "__main__":
    main()
