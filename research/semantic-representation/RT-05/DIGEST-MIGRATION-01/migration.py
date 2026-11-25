"""Closed-fixture comparison of typed address migration policies."""

from hashlib import sha256, sha512
import json

from src.semantic_graph import canonical_bytes


class StoreError(ValueError):
    pass


def address(blob, suite):
    functions = {"sha256": sha256, "sha512": sha512}
    if suite == "fixture-collision":
        return "fixture-collision:" + "0" * 64
    return f"{suite}:{functions[suite](blob).hexdigest()}"


def envelope(kind, payload, dependencies=(), *, version=1):
    return canonical_bytes({
        "domain": "rt05-migration-fixture", "kind": kind, "version": version,
        "payload": payload, "dependencies": list(dependencies),
    })


class Store:
    def __init__(self):
        self.blobs = {}
        self.quarantined = set()

    def put(self, blob, suite):
        name = address(blob, suite)
        if name in self.quarantined:
            raise StoreError("quarantined")
        saved = self.blobs.setdefault(name, blob)
        if saved != blob:
            self.quarantined.add(name)
            raise StoreError("collision")
        return name

    def read(self, name, suites):
        suite = name.partition(":")[0]
        if suite not in suites:
            raise StoreError("unsupported suite")
        if name in self.quarantined:
            raise StoreError("quarantined")
        blob = self.blobs.get(name)
        if blob is None:
            raise StoreError("missing address")
        if address(blob, suite) != name:
            raise StoreError("digest mismatch")
        return blob


def structure(store, root, suites):
    """Inspect the fixture's reachable typed structure without locator spelling."""
    records = {}

    def visit(name):
        if name not in records:
            node = json.loads(store.read(name, suites))
            node["dependencies"] = [[role, visit(dep)] for role, dep in node["dependencies"]]
            records[name] = node
        return records[name]

    return visit(root), set(records)


def check_alias(store, old, new):
    if old.partition(":")[0] != "sha256" or new.partition(":")[0] != "sha512":
        raise StoreError("unsupported alias direction")
    if store.read(old, {"sha256"}) != store.read(new, {"sha512"}):
        raise StoreError("alias payload differs")


def rewrite(store, root):
    new_addresses = {}

    def visit(old):
        if old not in new_addresses:
            node = json.loads(store.read(old, {"sha256"}))
            dependencies = [(role, visit(dep)) for role, dep in node["dependencies"]]
            rewritten = envelope(node["kind"], node["payload"], dependencies, version=node["version"])
            new_addresses[old] = store.put(rewritten, "sha512")
        return new_addresses[old]

    return visit(root), new_addresses
