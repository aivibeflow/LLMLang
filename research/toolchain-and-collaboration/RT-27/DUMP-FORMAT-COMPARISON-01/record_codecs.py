"""Record codecs for one restricted, explicitly typed SPG projection."""

import json
import zlib

import cbor2
import flatbuffers
from flatbuffers import encode, number_types as numbers, packer, table
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory


KEYS = ("kind", "name", "i64", "refs", "body")
PROFILES = (
    "jsonl", "json-seq", "cbor", "protobuf", "flatbuffers", "cbor-zlib"
)


def logical_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=True, allow_nan=False).encode("utf-8")


def protobuf_type():
    """Build the descriptor for schema.proto without a protoc dependency."""
    schema = descriptor_pb2.FileDescriptorProto(name="schema.proto", syntax="proto3")
    message = schema.message_type.add(name="Record")
    field = descriptor_pb2.FieldDescriptorProto
    fields = (
        (field.TYPE_UINT32, field.LABEL_OPTIONAL),
        (field.TYPE_STRING, field.LABEL_OPTIONAL),
        (field.TYPE_SINT64, field.LABEL_OPTIONAL),
        (field.TYPE_UINT32, field.LABEL_REPEATED),
        (field.TYPE_STRING, field.LABEL_OPTIONAL),
    )
    for number, (name, (kind, label)) in enumerate(zip(KEYS, fields), 1):
        message.field.add(name=name, number=number, type=kind, label=label)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(schema)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("Record"))


Record = protobuf_type()


def flat_encode(value):
    # Table slots match schema.fbs. Keep strings and the vector outside the table.
    builder = flatbuffers.Builder(512)
    body = builder.CreateString(value["body"])
    name = builder.CreateString(value["name"])
    refs = value["refs"]
    builder.StartVector(4, len(refs), 4)
    for ref in reversed(refs):
        builder.PrependUint32(ref)
    vector = builder.EndVector()
    builder.StartObject(5)
    builder.PrependUOffsetTRelativeSlot(4, body, 0)
    builder.PrependUOffsetTRelativeSlot(3, vector, 0)
    builder.PrependInt64Slot(2, int(value["i64"]), 0)
    builder.PrependUOffsetTRelativeSlot(1, name, 0)
    builder.PrependUint32Slot(0, value["kind"], 0)
    builder.Finish(builder.EndObject())
    return bytes(builder.Output())


def flat_decode(data):
    root = table.Table(data, encode.Get(packer.uoffset, data, 0))
    kind, name, i64, refs, body = (root.Offset(offset) for offset in range(4, 14, 2))
    start = root.Vector(refs)
    length = root.VectorLen(refs)
    return {
        "kind": root.Get(numbers.Uint32Flags, root.Pos + kind) if kind else 0,
        "name": root.String(root.Pos + name).decode("utf-8"),
        "i64": str(root.Get(numbers.Int64Flags, root.Pos + i64) if i64 else 0),
        "refs": [root.Get(numbers.Uint32Flags, start + 4 * j) for j in range(length)],
        "body": root.String(root.Pos + body).decode("utf-8"),
    }


def serialize(profile, value):
    if profile == "jsonl":
        return logical_bytes(value) + b"\n"
    if profile == "json-seq":
        return b"\x1e" + logical_bytes(value) + b"\n"
    if profile in ("cbor", "cbor-zlib"):
        packed = cbor2.dumps([value["kind"], value["name"], int(value["i64"]),
                              value["refs"], value["body"]], canonical=True)
        return zlib.compress(packed, level=6) if profile == "cbor-zlib" else packed
    if profile == "protobuf":
        return Record(**(value | {"i64": int(value["i64"])})).SerializeToString(
            deterministic=True
        )
    if profile == "flatbuffers":
        return flat_encode(value)
    raise ValueError(f"unknown profile {profile}")


def deserialize(profile, data):
    if profile == "jsonl":
        if not data.endswith(b"\n"):
            raise ValueError("missing JSONL delimiter")
        return json.loads(data)
    if profile == "json-seq":
        if not data.startswith(b"\x1e") or not data.endswith(b"\n"):
            raise ValueError("invalid JSON text sequence framing")
        return json.loads(data[1:])
    if profile == "cbor-zlib":
        data = zlib.decompress(data)
    if profile in ("cbor", "cbor-zlib"):
        kind, name, i64, refs, body = cbor2.loads(data)
        return dict(zip(KEYS, (kind, name, str(i64), refs, body)))
    if profile == "protobuf":
        value = Record.FromString(data)
        return dict(zip(KEYS, (value.kind, value.name, str(value.i64),
                              list(value.refs), value.body)))
    if profile == "flatbuffers":
        return flat_decode(data)
    raise ValueError(f"unknown profile {profile}")
