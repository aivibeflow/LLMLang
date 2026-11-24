import hashlib
import io
import os
import tempfile
import unittest

from package_archive import verify_archive
from package_identity import logical_index_hash, package_content_root, parse_manifest
from package_index import normalize
from package_provider import build_archive_from_snapshot


class LargeSnapshot:
    def __init__(self, size, shape):
        self.snapshot_id = f"stress-{shape}-{size}"
        self.payloads = [f"stress-object-{i}".encode() for i in range(size)]
        self.hashes = ["sha256:" + hashlib.sha256(value).hexdigest()
                       for value in self.payloads]
        self.payload_by_hash = dict(zip(self.hashes, self.payloads))
        self.objects = {
            h: {"hash": h, "kind": "function", "size": len(payload)}
            for h, payload in zip(self.hashes, self.payloads)
        }
        self.edges = {h: [] for h in self.hashes}
        if shape == "chain":
            for i in range(size - 1):
                self.edges[self.hashes[i]].append({
                    "edge_id": "next", "kind": "required",
                    "target_hash": self.hashes[i + 1],
                })
        elif shape == "fanout":
            self.edges[self.hashes[0]] = [
                {"edge_id": f"edge-{i}", "kind": "required",
                 "target_hash": self.hashes[i]}
                for i in range(1, size)
            ]
        else:
            raise ValueError(shape)

    def get_object(self, content_hash):
        return self.objects[content_hash]

    def get_dependencies(self, source_hash):
        return self.edges[source_hash]

    def open_object(self, content_hash):
        return io.BytesIO(self.payload_by_hash[content_hash])


def make_manifest(snapshot):
    index = normalize({
        "objects": list(snapshot.objects.values()),
        "dependencies": [
            {"source_hash": source, "edge_id": edge["edge_id"],
             "kind": edge["kind"], "target_hash": edge["target_hash"],
             "included": True}
            for source, edges in snapshot.edges.items() for edge in edges
        ],
        "exports": [], "modules": [],
    })
    raw = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "provider-stress"

[content]
roots = ["{snapshot.hashes[0]}"]
dependency_policy = "closure"
content_root = "sha256:{"0" * 64}"

[index]
path = "index"
format_version = 1
logical_hash = "{logical_index_hash(index)}"
'''.encode()
    root = package_content_root(parse_manifest(raw), index)
    return raw.replace(("sha256:" + "0" * 64).encode(), root.encode())


class ProviderStressTests(unittest.TestCase):
    def test_large_chain_and_high_fanout_closures(self):
        for shape in ("chain", "fanout"):
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as directory:
                snapshot = LargeSnapshot(1200, shape)
                output = os.path.join(directory, f"{shape}.llpkg")
                build_archive_from_snapshot(
                    [snapshot.hashes[0]], snapshot, make_manifest(snapshot), output,
                    policy="closure", max_records_in_memory=64, sqlite_cache_kib=64,
                )
                self.assertTrue(verify_archive(output, max_records_in_memory=64))


if __name__ == "__main__":
    unittest.main(verbosity=2)
