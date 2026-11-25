"""Restricted binary package-table candidate over the existing logical schema."""

import json
import os
from pathlib import Path
import shutil
import struct
from tempfile import NamedTemporaryFile, TemporaryFile

from package_index import TABLES, _canonical, _validate_stream_row, key


HEADER = struct.Struct(">4sBBI")
U16 = struct.Struct(">H")
U32 = struct.Struct(">I")
U64 = struct.Struct(">Q")
MAGIC = b"LIDX"
VERSION = 1
KINDS = ("required", "optional", "target", "evidence")


class WireError(ValueError):
    """The candidate table is malformed or noncanonical."""


def text(value):
    data = value.encode("utf-8")
    return U16.pack(len(data)) + data


def address(value):
    return bytes.fromhex(value.split(":", 1)[1])


def encode_row(table, raw):
    row = _validate_stream_row(table, raw)
    if table == "objects":
        return address(row["hash"]) + text(row["kind"]) + U64.pack(row["size"])
    if table == "dependencies":
        guard = b"\0"
        if "condition" in row:
            encoded = _canonical(row["condition"])
            guard = b"\1" + U32.pack(len(encoded)) + encoded
        return (address(row["source_hash"]) + text(row["edge_id"]) + bytes([KINDS.index(row["kind"])])
                + address(row["target_hash"]) + bytes([row["included"]]) + guard)
    if table == "exports":
        return text(row["module_id"]) + text(row["name"]) + address(row["object_hash"])
    return text(row["module_id"]) + U32.pack(len(row["members"])) + b"".join(map(address, row["members"]))


class Cursor:
    def __init__(self, raw):
        self.data = raw
        self.offset = 0

    def take(self, length):
        end = self.offset + length
        if end > len(self.data):
            raise WireError("truncated row")
        result = self.data[self.offset:end]
        self.offset = end
        return result

    def number(self, schema):
        return schema.unpack(self.take(schema.size))[0]

    def address(self):
        return "sha256:" + self.take(32).hex()

    def label(self):
        return self.take(self.number(U16)).decode("utf-8")

    def tag(self, count):
        code = self.take(1)[0]
        if code >= count:
            raise WireError("unsupported tag")
        return code


def decode_row(table, raw):
    cursor = Cursor(raw)
    try:
        if table == "objects":
            row = {"hash": cursor.address(), "kind": cursor.label(), "size": cursor.number(U64)}
        elif table == "dependencies":
            row = {"source_hash": cursor.address(), "edge_id": cursor.label(),
                   "kind": KINDS[cursor.tag(len(KINDS))], "target_hash": cursor.address(),
                   "included": bool(cursor.tag(2))}
            if cursor.tag(2):
                row["condition"] = json.loads(cursor.take(cursor.number(U32)).decode("utf-8"))
        elif table == "exports":
            row = {"module_id": cursor.label(), "name": cursor.label(), "object_hash": cursor.address()}
        else:
            row = {"module_id": cursor.label(), "members":
                   [cursor.address() for _ in range(cursor.number(U32))]}
        if cursor.offset != len(raw) or encode_row(table, row) != raw:
            raise WireError("row is not in canonical form")
    except (ValueError, KeyError, TypeError, struct.error) as exc:
        raise WireError(str(exc)) from exc
    return row


def write_table(destination, table, rows):
    """Spool sorted rows and offsets before atomically adopting the completed table."""
    stage = None
    try:
        with TemporaryFile() as offsets, TemporaryFile() as body:
            count = 0
            previous = None
            offsets.write(U32.pack(0))
            for raw in rows:
                current = key(table, raw)
                if previous is not None and current <= previous:
                    raise WireError("row keys must be strictly increasing")
                body.write(encode_row(table, raw))
                offsets.write(U32.pack(body.tell()))
                previous = current
                count += 1
            with NamedTemporaryFile(dir=destination.parent, prefix=".index-", delete=False) as completed:
                stage = Path(completed.name)
                completed.write(HEADER.pack(MAGIC, VERSION, TABLES.index(table), count))
                for source in (offsets, body):
                    source.seek(0)
                    shutil.copyfileobj(source, completed, length=65536)
            os.replace(stage, destination)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


class Table:
    """One retained file with an audited offset directory and key order."""

    def __init__(self, path, name):
        self.path = path
        self.name = name
        self.file = None

    def __enter__(self):
        self.file = self.path.open("rb")
        try:
            total_size = os.fstat(self.file.fileno()).st_size
            header = self.file.read(HEADER.size)
            if len(header) != HEADER.size:
                raise WireError("short header")
            magic, version, category, self.count = HEADER.unpack(header)
            if (magic, version, category) != (MAGIC, VERSION, TABLES.index(self.name)):
                raise WireError("wrong table header")
            self.base = HEADER.size + U32.size * (self.count + 1)
            self.length = total_size - self.base
            if self.length < 0 or self.offset(0) != 0 or self.offset(self.count) != self.length:
                raise WireError("offsets do not cover the exact row section")
            for _ in self.rows():
                pass
        except BaseException:
            self.file.close()
            raise
        return self

    def __exit__(self, *args):
        self.file.close()

    def offset(self, index):
        self.file.seek(HEADER.size + U32.size * index)
        return U32.unpack(self.file.read(U32.size))[0]

    def row(self, index):
        start = self.offset(index)
        end = self.offset(index + 1)
        if not 0 <= start < end <= self.length:
            raise WireError("invalid row boundaries")
        self.file.seek(self.base + start)
        return decode_row(self.name, self.file.read(end - start))

    def rows(self):
        previous = None
        for index in range(self.count):
            row = self.row(index)
            current = key(self.name, row)
            if previous is not None and current <= previous:
                raise WireError("row keys must be strictly increasing")
            previous = current
            yield row

    def lookup(self, wanted):
        lower, upper = 0, self.count
        examined = 0
        while lower < upper:
            index = (lower + upper) // 2
            row = self.row(index)
            current = key(self.name, row)
            examined += 1
            if current == wanted:
                return row, examined
            if current < wanted:
                lower = index + 1
            else:
                upper = index
        return None, examined
