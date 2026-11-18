import unittest

from src.semantic_graph import ContentStore, make_snapshot
from src.semantic_dependency_index import (
    FORMAT, SCHEMA_VERSION, SemanticObjectError,
    build_dependency_index, build_snapshot_dependency_index, publish_declaration, validate_declaration,
)


def declaration(kind, declaration_id, content=None, **extra):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration_id,
        "content": content or {},
        **extra,
    }


class SemanticDependencyIndexTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.i32 = publish_declaration(self.store, declaration("type", "type:i32", {"name": "i32"}))
        self.tax_contract = publish_declaration(
            self.store, declaration("contract", "contract:tax", {"name": "TaxContract"},
                                    references=[{"reference_id": "input-type", "relation": "uses_type",
                                                 "target_hash": self.i32, "target_kind": "type"}])
        )
        self.effect = publish_declaration(self.store, declaration("effect", "effect:read-clock", {"name": "ReadClock"}))
        self.old_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v1", {"body": "old"})
        )
        self.new_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v2", {"body": "new"})
        )

    def test_call_sites_have_stable_distinct_edge_ids(self):
        caller = publish_declaration(self.store, declaration(
            "function", "fn:invoice:v1", {"body": "invoice"},
            call_sites=[
                {"call_site_id": "call:subtotal-tax", "targets": [
                    {"target_id": "direct", "target_hash": self.old_callee, "condition": None}]},
                {"call_site_id": "call:final-tax", "targets": [
                    {"target_id": "direct", "target_hash": self.new_callee, "condition": None}]},
            ],
        ))
        edges = build_dependency_index(self.store).outgoing(caller)
        self.assertEqual({edge.edge_id for edge in edges},
                         {"call:subtotal-tax/direct", "call:final-tax/direct"})
        self.assertEqual({edge.target_hash for edge in edges},
                         {self.old_callee, self.new_callee})

    def test_conditional_dispatch_preserves_each_exact_target_and_condition(self):
        caller = publish_declaration(self.store, declaration(
            "operation", "op:route-tax", {"body": "dispatch"},
            call_sites=[{"call_site_id": "call:dispatch", "targets": [
                {"target_id": "business", "target_hash": self.old_callee,
                 "condition": "jurisdiction == legacy"},
                {"target_id": "consumer", "target_hash": self.new_callee,
                 "condition": "jurisdiction == current"},
            ]}],
        ))
        edges = build_dependency_index(self.store).outgoing(caller)
        self.assertEqual(len(edges), 2)
        self.assertEqual({edge.condition for edge in edges},
                         {"jurisdiction == legacy", "jurisdiction == current"})

    def test_reverse_index_keeps_call_site_context(self):
        caller = publish_declaration(self.store, declaration(
            "function", "fn:caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:one", "targets": [
                {"target_id": "primary", "target_hash": self.old_callee, "condition": None}]}],
        ))
        incoming = build_dependency_index(self.store).incoming(self.old_callee)
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].source_hash, caller)
        self.assertEqual(incoming[0].edge_id, "call:one/primary")

    def test_snapshot_scoped_reverse_index_excludes_historical_callers(self):
        old_caller = publish_declaration(self.store, declaration(
            "function", "fn:shared:old", {"body": "shared"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None}]}],
        ))
        stale_caller = publish_declaration(self.store, declaration(
            "function", "fn:shared:stale", {"body": "older shared body"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None}]}],
        ))
        new_caller = publish_declaration(self.store, declaration(
            "function", "fn:shared:new", {"body": "shared"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.new_callee, "condition": None}]}],
        ))
        snapshot = make_snapshot({
            "callee": self.new_callee,
            "preserving-consumer": old_caller,
            "migrating-consumer": new_caller,
        })

        index = build_snapshot_dependency_index(self.store, snapshot)

        self.assertEqual(index.snapshot_root, snapshot.root_hash)
        self.assertEqual({edge.source_hash for edge in index.incoming(self.old_callee)}, {old_caller})
        self.assertNotIn(stale_caller, {edge.source_hash for edge in index.incoming(self.old_callee)})
        self.assertEqual({edge.source_hash for edge in index.incoming(self.new_callee)}, {new_caller})
        self.assertNotIn(old_caller, {edge.source_hash for edge in index.incoming(self.new_callee)})

    def test_snapshot_scoped_index_rejects_missing_selected_object(self):
        snapshot = make_snapshot({"missing": "not-in-store"})
        with self.assertRaises(KeyError):
            build_snapshot_dependency_index(self.store, snapshot)

    def test_typed_references_validate_target_kind(self):
        impl = publish_declaration(self.store, declaration(
            "implementation", "impl:tax", {"body": "impl"},
            references=[
                {"reference_id": "contract-binding", "relation": "implements_contract",
                 "target_hash": self.tax_contract, "target_kind": "contract"},
                {"reference_id": "clock-effect", "relation": "uses_effect",
                 "target_hash": self.effect, "target_kind": "effect"},
            ],
        ))
        edges = build_dependency_index(self.store).outgoing(impl)
        self.assertEqual({edge.relation for edge in edges},
                         {"implements_contract", "uses_effect"})

    def test_rejects_unknown_or_ambiguous_schema_fields(self):
        bad = declaration("function", "fn:bad", {"body": "x"}, calls=[self.old_callee])
        with self.assertRaises(SemanticObjectError):
            validate_declaration(bad)

    def test_rejects_duplicate_call_site_and_target_ids(self):
        bad = declaration("function", "fn:bad", {"body": "x"}, call_sites=[
            {"call_site_id": "same", "targets": [
                {"target_id": "x", "target_hash": self.old_callee, "condition": None},
                {"target_id": "x", "target_hash": self.new_callee, "condition": None}]}
        ])
        with self.assertRaises(SemanticObjectError):
            validate_declaration(bad)

    def test_rejects_wrong_target_kind(self):
        bad = declaration("function", "fn:bad", {"body": "x"}, references=[
            {"reference_id": "wrong", "relation": "uses_type",
             "target_hash": self.tax_contract, "target_kind": "contract"}
        ])
        with self.assertRaises(SemanticObjectError):
            publish_declaration(self.store, bad)

    def test_exact_target_revision_is_part_of_caller_hash(self):
        caller_v1 = publish_declaration(self.store, declaration(
            "function", "fn:caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None}]}],
        ))
        caller_v2 = publish_declaration(self.store, declaration(
            "function", "fn:caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.new_callee, "condition": None}]}],
        ))
        self.assertNotEqual(caller_v1, caller_v2)
        self.assertIn(self.old_callee, self.store)
        self.assertIn(self.new_callee, self.store)


if __name__ == "__main__":
    unittest.main()
