"""Physical layouts that reconstruct one existing recursive Content Store group."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, Dependency, canonical_bytes

LAYOUTS = ("whole", "flat", "blocked")
BLOCK_SIZE = 16


def digest(payload):
    return sha256(payload).hexdigest()


@dataclass
class Archive:
    root: str
    blobs: dict[str, bytes]


def encode(group, layout):
    if layout not in LAYOUTS or group.kind != "rt05-recursive-keyed-v1":
        raise ValueError("Expected the existing keyed recursive group layout")
    blobs = {}

    def put(value):
        data = canonical_bytes(value)
        address = digest(data)
        blobs[address] = data
        return address

    rows = group.payload
    index = {"layout": layout, "group": group.value_hash, "kind": group.kind, "count": len(rows),
             "dependencies": [dependency.record() for dependency in group.dependencies]}
    if layout == "whole":
        index["rows"] = rows
    else:
        bodies = [put(row) for row in rows]
        if layout == "flat":
            index["bodies"] = bodies
        else:
            index["blocks"] = [put(bodies[offset:offset+BLOCK_SIZE])
                               for offset in range(0, len(bodies), BLOCK_SIZE)]
    return Archive(put(index), blobs)


@dataclass(frozen=True)
class Admitted:
    archive_root: str
    semantic_group: str


class Reader:
    def __init__(self, archive):
        self.archive = archive
        self.seen = {}
        self.index = self.read(archive.root)

    def read(self, address):
        if address not in self.seen:
            original = self.archive.blobs[address]
            if digest(original) != address:
                raise ValueError("Physical archive digest mismatch")
            self.seen[address] = json.loads(original)
        return self.seen[address]

    def row(self, slot):
        if not 0 <= slot < self.index["count"]:
            raise ValueError("Unknown member position")
        layout = self.index["layout"]
        if layout == "whole":
            return self.index["rows"][slot]
        if layout == "flat":
            return self.read(self.index["bodies"][slot])
        if layout == "blocked":
            block, index = divmod(slot, BLOCK_SIZE)
            paths = self.read(self.index["blocks"][block])
            return self.read(paths[index])
        raise ValueError("Unknown body encoding")

    @property
    def bytes_read(self):
        return sum(len(self.archive.blobs[address]) for address in self.seen)


def admit(archive, store, expected_group):
    reader = Reader(archive)
    index = reader.index
    if index["group"] != expected_group:
        raise ValueError("Archive identifies another semantic group")
    rows = [reader.row(i) for i in range(index["count"])]
    dependencies = [Dependency(**item) for item in index["dependencies"]]
    staged_store = ContentStore()
    for dependency in dependencies:
        leaf = store.get(dependency.target_hash)
        if leaf.dependencies:
            raise ValueError("This fixture admits only leaf external dependencies")
        assert staged_store.put(leaf.kind, leaf.payload) == dependency.target_hash
    rebuilt = staged_store.put(index["kind"], rows, dependencies)
    if rebuilt != expected_group:
        raise ValueError("The archive does not reconstruct the selected semantic group")
    return Admitted(archive.root, expected_group), reader.bytes_read


def execute(archive, admission, store, entry, fuel):
    if archive.root != admission.archive_root:
        raise ValueError("Read requires the exact admitted archive root")
    reader = Reader(archive)
    assert reader.index["group"] == admission.semantic_group
    trace = []
    for _ in range(fuel):
        tokens = reader.row(entry)["body"]
        next_entry = None
        for token in tokens:
            if "literal" in token:
                trace.append(token["literal"])
            elif "external" in token:
                trace.append(store.get(token["external"]).payload["value"])
            elif "local_call" in token and next_entry is None:
                next_entry = token["local_call"]
            else:
                raise ValueError("Unexpected executable group token")
        if next_entry is None:
            raise ValueError("Expected one cyclic successor")
        entry = next_entry
    return trace, reader.bytes_read
