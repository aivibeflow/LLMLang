"""Compare storage envelopes for one exact acyclic typed SPG profile."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.persistence import dumps_graph, loads_graph
from src.semantic_graph import RelationStore, canonical_bytes
from src.spg_admission import validate
from src.spg_representation import Graph


PROFILES = ("snapshot", "value", "expression")


@dataclass(frozen=True)
class Archive:
    root: str
    blobs: dict[str, bytes]


def child_start(expression):
    match expression[0]:
        case "literal" | "argument":
            return len(expression)
        case "add" | "sub" | "eq" | "if":
            return 1
        case "emit" | "pin" | "op":
            return 2
        case _:
            raise ValueError("Unsupported expression form")


def emit_expression(expression, put):
    split = child_start(expression)
    return put({"head": expression[:split], "children": [
        emit_expression(child, put) for child in expression[split:]
    ]})


def read_expression(root, read):
    row = read(root)
    return row["head"] + [read_expression(child, read) for child in row["children"]]


def encode_graph(graph, profile):
    if profile not in PROFILES:
        raise ValueError("Unknown archive profile")
    validate(graph)
    if any(graph.store.get(key).kind.startswith("rt05-recursive-") for key in graph.store.hashes()):
        raise ValueError("This archive experiment admits only the acyclic fixture")
    encoded = dumps_graph(graph.store, RelationStore(), [graph.snapshot])
    if profile == "snapshot":
        root = sha256(encoded).hexdigest()
        return Archive(root, {root: encoded})

    blobs = {}

    def put(value):
        data = canonical_bytes(value)
        name = sha256(data).hexdigest()
        blobs[name] = data
        return name

    envelope = json.loads(encoded)
    rows = envelope["payload"].pop("values")
    references = []
    for row in rows:
        if profile == "expression" and row["kind"] == "rt05-definition-v1":
            tokens = row["payload"]
            expression = json.loads(tokens[2]["literal"])
            tokens[2] = {"expression_root": emit_expression(expression, put)}
        references.append(put(row))

    root = put({"profile": profile, "envelope": envelope, "value_rows": references})
    return Archive(root, blobs)


def restore(archive, profile):
    if profile not in PROFILES:
        raise ValueError("Unknown archive profile")

    def read_bytes(name):
        data = archive.blobs[name]
        if sha256(data).hexdigest() != name:
            raise ValueError("Archive object checksum mismatch")
        return data

    def read(name):
        return json.loads(read_bytes(name))

    if profile == "snapshot":
        encoded = read_bytes(archive.root)
    else:
        root = read(archive.root)
        if root["profile"] != profile:
            raise ValueError("Archive profile mismatch")
        envelope = root["envelope"]
        rows = []
        for name in root["value_rows"]:
            row = read(name)
            if profile == "expression" and row["kind"] == "rt05-definition-v1":
                tokens = row["payload"]
                term = read_expression(tokens[2]["expression_root"], read)
                tokens[2] = {"literal": canonical_bytes(term).decode("ascii")}
            rows.append(row)
        envelope["payload"]["values"] = rows
        encoded = canonical_bytes(envelope) + b"\n"

    store, _, snapshots = loads_graph(encoded)
    graph = Graph(store, snapshots[0])
    validate(graph)
    return graph, encoded
