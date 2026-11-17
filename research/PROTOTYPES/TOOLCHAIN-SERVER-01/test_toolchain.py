import json
import tempfile
import unittest
from pathlib import Path

from toolchain import (
    Change, Entity, InMemoryToolchain, InvalidSnapshot, NotFound,
    SemanticConflict, StaleObject, StaleRevision, digest,
)


class ToolchainWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tc = InMemoryToolchain()
        self.base = self.tc.create_snapshot([
            Entity("op:hello", "operation", {"name": "hello", "arity": 0}),
        ])

    def test_add_update_accept_export_import_round_trip(self):
        ws = self.tc.open_workspace(self.base)
        add = self.tc.propose(ws.workspace_id, 0, [
            Change("add", "impl:hello", None, "implementation", {"body": {"return": 42}})
        ])
        working = self.tc.apply(add, expected_revision=0)
        self.assertNotEqual(working, self.base)

        entity = self.tc.get_entity(working, "impl:hello")
        update = self.tc.propose(ws.workspace_id, 1, [
            Change("update", "impl:hello", entity.content_hash, "implementation", {"body": {"return": 43}})
        ])
        updated = self.tc.apply(update, expected_revision=1)
        accepted = self.tc.accept(ws.workspace_id, expected_revision=2)

        self.assertEqual(updated, accepted)
        self.assertEqual(self.tc.get_workspace(ws.workspace_id).state, "accepted")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.json"
            file_hash = self.tc.export_snapshot(accepted, path)
            self.assertEqual(file_hash, digest(path.read_bytes()))
            imported = self.tc.import_snapshot(path)
        self.assertEqual(imported, accepted)

    def test_change_set_is_atomic_when_later_precondition_is_stale(self):
        ws = self.tc.open_workspace(self.base)
        original = self.tc.get_entity(self.base, "op:hello")
        changes = [
            Change("add", "op:new", None, "operation", {"name": "new"}),
            Change("update", "op:hello", "sha256:" + "0" * 64, "operation", {"name": "changed"}),
        ]
        proposal = self.tc.propose(ws.workspace_id, 0, changes)
        with self.assertRaises(StaleObject):
            self.tc.apply(proposal, expected_revision=0)
        current = self.tc.get_workspace(ws.workspace_id)
        self.assertEqual(current.revision, 0)
        self.assertEqual(current.working_snapshot, self.base)
        with self.assertRaises(NotFound):
            self.tc.get_entity(self.base, "op:new")
        self.assertEqual(self.tc.get_entity(self.base, "op:hello"), original)

    def test_stale_workspace_revision_is_rejected(self):
        ws = self.tc.open_workspace(self.base)
        proposal = self.tc.propose(ws.workspace_id, 0, [
            Change("add", "op:new", None, "operation", {"name": "new"})
        ])
        self.tc.apply(proposal, expected_revision=0)
        with self.assertRaises(StaleRevision):
            self.tc.apply(proposal, expected_revision=0)

    def test_workspaces_are_isolated(self):
        left = self.tc.open_workspace(self.base)
        right = self.tc.open_workspace(self.base)
        proposal = self.tc.propose(left.workspace_id, 0, [
            Change("add", "op:left", None, "operation", {"name": "left"})
        ])
        left_root = self.tc.apply(proposal, expected_revision=0)
        self.assertNotEqual(left_root, self.base)
        self.assertEqual(self.tc.get_workspace(right.workspace_id).working_snapshot, self.base)
        with self.assertRaises(Exception):
            self.tc.get_entity(right.working_snapshot, "op:left")

    def test_duplicate_target_in_changeset_is_rejected(self):
        ws = self.tc.open_workspace(self.base)
        proposal = self.tc.propose(ws.workspace_id, 0, [
            Change("add", "op:new", None, "operation", {"name": "new"}),
            Change("add", "op:new", None, "operation", {"name": "duplicate"}),
        ])
        with self.assertRaises(SemanticConflict):
            self.tc.apply(proposal, expected_revision=0)
        self.assertEqual(self.tc.get_workspace(ws.workspace_id).working_snapshot, self.base)

    def test_export_refuses_external_file_edits(self):
        ws = self.tc.open_workspace(self.base)
        accepted = self.tc.accept(ws.workspace_id, expected_revision=0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.json"
            first_hash = self.tc.export_snapshot(accepted, path)
            path.write_text('{"external":"edit"}', encoding="utf-8")
            with self.assertRaises(StaleObject):
                self.tc.export_snapshot(accepted, path, expected_file_hash=first_hash)

    def test_export_requires_accepted_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SemanticConflict):
                self.tc.export_snapshot(self.base, Path(directory) / "program.json")

    def test_import_rejects_tampered_entity_hash(self):
        ws = self.tc.open_workspace(self.base)
        accepted = self.tc.accept(ws.workspace_id, expected_revision=0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.json"
            self.tc.export_snapshot(accepted, path)
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["entities"][0]["payload"]["name"] = "tampered"
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(InvalidSnapshot):
                self.tc.import_snapshot(path)


if __name__ == "__main__":
    unittest.main()
