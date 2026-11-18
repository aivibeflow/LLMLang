import hashlib
import json
import os
import tempfile
import unittest

from content_store import (
    ContentStoreConflict, SQLiteContentStore, SnapshotClosed, content_hash,
)
from package_archive import verify_archive
from package_identity import logical_index_hash, package_content_root, parse_manifest
from package_index import normalize
from package_provider import build_archive_from_snapshot


def make_manifest(root_hash, objects, edges):
    index = normalize({
        "objects": objects,
        "dependencies": [
            {"source_hash": source, "edge_id": edge["edge_id"],
             "kind": edge["kind"], "target_hash": edge["target_hash"],
             "included": True}
            for source, edge in edges
        ],
        "exports": [], "modules": [],
    })
    raw = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "sqlite-content-store-integration"

[content]
roots = ["{root_hash}"]
dependency_policy = "closure"
content_root = "sha256:{"0" * 64}"

[index]
path = "index"
format_version = 1
logical_hash = "{logical_index_hash(index)}"
'''.encode()
    root = package_content_root(parse_manifest(raw), index)
    return raw.replace(("sha256:" + "0" * 64).encode(), root.encode())


class SQLiteContentStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "content.sqlite3")
        self.store = SQLiteContentStore(self.path)

    def test_exact_object_metadata_and_streaming_payload(self):
        payload = b"immutable semantic object payload"
        object_hash = self.store.put_object(payload, "function", [])
        with self.store.open_snapshot() as snapshot:
            self.assertEqual(snapshot.get_object(object_hash), {
                "hash": object_hash, "kind": "function", "size": len(payload),
            })
            stream = snapshot.open_object(object_hash)
            try:
                self.assertEqual(stream.read(7), payload[:7])
                self.assertEqual(stream.read(), payload[7:])
            finally:
                stream.close()
            self.assertEqual(list(snapshot.get_dependencies(object_hash)), [])

    def test_read_transaction_is_pinned_across_concurrent_writer(self):
        root_payload = b"root"
        target_payload = b"target"
        target_hash = content_hash(target_payload)
        root_hash = self.store.put_object(root_payload, "function", [{
            "edge_id": "requires-target", "kind": "required",
            "target_hash": target_hash,
        }])
        old_snapshot = self.store.open_snapshot()
        old_id = old_snapshot.snapshot_id
        self.store.put_object(target_payload, "function", [])
        with self.assertRaises(KeyError):
            old_snapshot.get_object(target_hash)
        with self.store.open_snapshot() as new_snapshot:
            self.assertNotEqual(new_snapshot.snapshot_id, old_id)
            self.assertEqual(new_snapshot.get_object(target_hash)["hash"], target_hash)
        old_snapshot.close()

    def test_dependency_rows_are_typed_and_conditions_round_trip(self):
        target_hash = content_hash(b"target")
        source_hash = self.store.put_object(b"source", "function", [{
            "edge_id": "conditional", "kind": "required",
            "target_hash": target_hash, "condition": {"feature": "x", "enabled": True},
        }])
        with self.store.open_snapshot() as snapshot:
            self.assertEqual(list(snapshot.get_dependencies(source_hash)), [{
                "edge_id": "conditional", "kind": "required",
                "target_hash": target_hash,
                "condition": {"enabled": True, "feature": "x"},
            }])

    def test_repeated_identical_insert_is_idempotent(self):
        first = self.store.put_object(b"same", "function", [])
        with self.store.open_snapshot() as before:
            before_id = before.snapshot_id
        second = self.store.put_object(b"same", "function", [])
        with self.store.open_snapshot() as after:
            self.assertEqual(first, second)
            self.assertEqual(before_id, after.snapshot_id)

    def test_conflicting_kind_or_dependency_set_is_rejected(self):
        object_hash = self.store.put_object(b"same", "function", [])
        with self.assertRaises(ContentStoreConflict):
            self.store.put_object(b"same", "type", [])
        with self.assertRaises(ContentStoreConflict):
            self.store.put_object(b"same", "function", [{
                "edge_id": "new", "kind": "required",
                "target_hash": content_hash(b"target"),
            }])
        self.assertEqual(object_hash, content_hash(b"same"))

    def test_missing_dependency_metadata_and_missing_objects_are_distinct(self):
        source_hash = self.store.put_object(b"source", "function", [])
        with self.store.open_snapshot() as snapshot:
            self.assertEqual(list(snapshot.get_dependencies(source_hash)), [])
            with self.assertRaises(KeyError):
                snapshot.get_object(content_hash(b"missing"))

    def test_closed_snapshot_rejects_new_reads(self):
        object_hash = self.store.put_object(b"object", "function", [])
        snapshot = self.store.open_snapshot()
        snapshot.close()
        with self.assertRaises(SnapshotClosed):
            snapshot.get_object(object_hash)

    def test_package_provider_consumes_pinned_sqlite_snapshot(self):
        target_payload = b"dependency-object"
        target_hash = self.store.put_object(target_payload, "function", [])
        root_payload = b"root-object"
        root_hash = self.store.put_object(root_payload, "function", [{
            "edge_id": "dep", "kind": "required", "target_hash": target_hash,
        }])
        objects = [
            {"hash": root_hash, "kind": "function", "size": len(root_payload)},
            {"hash": target_hash, "kind": "function", "size": len(target_payload)},
        ]
        edges = [(root_hash, {
            "edge_id": "dep", "kind": "required", "target_hash": target_hash,
        })]
        manifest = make_manifest(root_hash, objects, edges)
        with tempfile.TemporaryDirectory() as directory:
            archive = os.path.join(directory, "package.llpkg")
            with self.store.open_snapshot() as snapshot:
                build_archive_from_snapshot(
                    [root_hash], snapshot, manifest, archive, policy="closure",
                    max_records_in_memory=8, sqlite_cache_kib=64,
                )
            self.assertTrue(verify_archive(archive, max_records_in_memory=8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
