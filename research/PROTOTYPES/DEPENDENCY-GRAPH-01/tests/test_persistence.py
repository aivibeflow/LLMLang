import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.persistence import (
    PersistenceError, dumps_graph, load_graph, loads_graph, save_graph,
)
from src.semantic_graph import (
    ContentStore, Dependency, RelationStore, make_snapshot,
)


class PersistenceTests(unittest.TestCase):
    def fixture(self):
        store = ContentStore()
        leaf = store.put("constant", {"value": 7})
        caller = store.put("function", {"body": "use value"},
                           [Dependency("reads", leaf, "input")])
        relations = RelationStore()
        relations.add("project-A", caller, "implements", "REQ-7")
        snapshot = make_snapshot({"leaf": leaf, "caller": caller})
        return store, relations, snapshot

    def test_round_trip_preserves_hashes_relations_and_snapshot_roots(self):
        store, relations, snapshot = self.fixture()
        encoded = dumps_graph(store, relations, [snapshot])
        loaded_store, loaded_relations, snapshots = loads_graph(encoded)
        self.assertEqual(loaded_store.hashes(), store.hashes())
        self.assertEqual(loaded_store.closure_digest(snapshot.mapping["caller"]),
                         store.closure_digest(snapshot.mapping["caller"]))
        self.assertEqual(loaded_relations.for_scope("project-A"),
                         relations.for_scope("project-A"))
        self.assertEqual(snapshots, (snapshot,))
        self.assertEqual(dumps_graph(loaded_store, loaded_relations, snapshots), encoded)

    def test_save_and_load_file(self):
        store, relations, snapshot = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            save_graph(path, store, relations, [snapshot])
            loaded = load_graph(path)
            self.assertEqual(loaded[2], (snapshot,))

    def test_serialization_is_deterministic_regardless_of_insertion_order(self):
        a = ContentStore()
        x = a.put("constant", {"v": 1})
        y = a.put("constant", {"v": 2})
        a.put("function", {"body": "f"}, [Dependency("uses", x)])
        b = ContentStore()
        y2 = b.put("constant", {"v": 2})
        x2 = b.put("constant", {"v": 1})
        b.put("function", {"body": "f"}, [Dependency("uses", x2)])
        self.assertEqual(x, x2)
        self.assertEqual(y, y2)
        self.assertEqual(dumps_graph(a, RelationStore()),
                         dumps_graph(b, RelationStore()))

    def test_checksum_detects_tampering(self):
        store, relations, snapshot = self.fixture()
        envelope = json.loads(dumps_graph(store, relations, [snapshot]))
        envelope["payload"]["values"][0]["payload"]["value"] = 999
        with self.assertRaisesRegex(PersistenceError, "checksum"):
            loads_graph(json.dumps(envelope))

    def test_unsupported_schema_version_is_rejected(self):
        store, relations, snapshot = self.fixture()
        envelope = json.loads(dumps_graph(store, relations, [snapshot]))
        envelope["payload"]["schema_version"] = 999
        envelope["checksum"] = __import__("src.semantic_graph", fromlist=["digest"]).digest(
            envelope["payload"])
        with self.assertRaisesRegex(PersistenceError, "unsupported schema"):
            loads_graph(json.dumps(envelope))

    def test_snapshot_reference_to_missing_value_is_rejected(self):
        store, relations, snapshot = self.fixture()
        envelope = json.loads(dumps_graph(store, relations, [snapshot]))
        envelope["payload"]["snapshots"][0]["selections"][0][1] = "f" * 64
        from src.semantic_graph import digest
        envelope["checksum"] = digest(envelope["payload"])
        with self.assertRaises(PersistenceError):
            loads_graph(json.dumps(envelope))

    def test_cross_process_hashes_are_reproducible(self):
        store, relations, snapshot = self.fixture()
        expected = {
            "hashes": sorted(store.hashes()),
            "root": snapshot.root_hash,
            "closure": store.closure_digest(snapshot.mapping["caller"]),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            save_graph(path, store, relations, [snapshot])
            script = (
                "import json,sys; from src.persistence import load_graph; "
                "s,r,p=load_graph(sys.argv[1]); snap=p[0]; "
                "print(json.dumps({'hashes':sorted(s.hashes()),'root':snap.root_hash,"
                "'closure':s.closure_digest(snap.mapping['caller'])},sort_keys=True))"
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
            output = subprocess.check_output(
                [sys.executable, "-c", script, str(path)], env=env, text=True
            )
        self.assertEqual(json.loads(output), expected)


if __name__ == "__main__":
    unittest.main()
