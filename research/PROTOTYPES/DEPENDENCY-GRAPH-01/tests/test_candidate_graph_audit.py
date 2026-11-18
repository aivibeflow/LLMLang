import unittest

from src.candidate_graph_audit import audit_candidate_snapshot_graph
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, Dependency, Snapshot, make_snapshot


def declaration(kind, declaration_id, content=None, references=None, call_sites=None):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration_id,
        "content": content or {},
        "references": references or [],
        "call_sites": call_sites or [],
    }


class CandidateGraphAuditTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.type_hash = publish_declaration(
            self.store, declaration("type", "type:money", {"representation": "i64"})
        )
        self.contract_hash = publish_declaration(
            self.store, declaration(
                "contract", "contract:tax",
                references=[{
                    "reference_id": "amount-type",
                    "relation": "uses_type",
                    "target_hash": self.type_hash,
                    "target_kind": "type",
                    "condition": None,
                }],
            )
        )
        self.function_hash = publish_declaration(
            self.store, declaration(
                "function", "function:tax",
                references=[{
                    "reference_id": "tax-contract",
                    "relation": "uses_contract",
                    "target_hash": self.contract_hash,
                    "target_kind": "contract",
                    "condition": None,
                }],
            )
        )
        self.unrelated_hash = publish_declaration(
            self.store, declaration("effect", "effect:logging")
        )

    def test_audits_transitive_closure_beyond_direct_snapshot_selections(self):
        snapshot = make_snapshot({"entry": self.function_hash})
        result = audit_candidate_snapshot_graph(self.store, snapshot)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(
            set(result.reachable_hashes),
            {self.function_hash, self.contract_hash, self.type_hash},
        )
        self.assertNotIn(self.unrelated_hash, result.reachable_hashes)
        self.assertEqual(len(result.dependency_index.edges), 2)
        self.assertEqual(result.dependency_index.snapshot_root, snapshot.root_hash)

    def test_detects_payload_dependency_missing_from_store_metadata(self):
        broken_hash = self.store.put(
            "function",
            declaration(
                "function", "function:broken",
                references=[{
                    "reference_id": "contract",
                    "relation": "uses_contract",
                    "target_hash": self.contract_hash,
                    "target_kind": "contract",
                    "condition": None,
                }],
            ),
        )
        result = audit_candidate_snapshot_graph(
            self.store, make_snapshot({"broken": broken_hash})
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("payload dependencies missing" in error for error in result.errors))

    def test_detects_undeclared_stored_dependency_metadata(self):
        broken_hash = self.store.put(
            "function",
            declaration("function", "function:extra-edge"),
            [Dependency("calls", self.function_hash, "undeclared-call")],
        )
        result = audit_candidate_snapshot_graph(
            self.store, make_snapshot({"broken": broken_hash})
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("stored metadata has undeclared dependencies" in error
                            for error in result.errors))
        self.assertIn(self.function_hash, result.reachable_hashes)

    def test_detects_missing_transitive_reference_target(self):
        missing_hash = "f" * 64
        broken_hash = self.store.put(
            "function",
            declaration(
                "function", "function:missing-target",
                references=[{
                    "reference_id": "missing-contract",
                    "relation": "uses_contract",
                    "target_hash": missing_hash,
                    "target_kind": "contract",
                    "condition": None,
                }],
            ),
        )
        result = audit_candidate_snapshot_graph(
            self.store, make_snapshot({"broken": broken_hash})
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("missing referenced object" in error for error in result.errors))

    def test_detects_actual_target_kind_mismatch(self):
        wrong_hash = self.store.put(
            "function",
            declaration(
                "function", "function:wrong-kind",
                references=[{
                    "reference_id": "wrong-contract",
                    "relation": "uses_contract",
                    "target_hash": self.function_hash,
                    "target_kind": "contract",
                    "condition": None,
                }],
            ),
        )
        result = audit_candidate_snapshot_graph(
            self.store, make_snapshot({"wrong": wrong_hash})
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("expected target kind contract, found function" in error
                            for error in result.errors))

    def test_snapshot_root_is_recomputed(self):
        valid = make_snapshot({"entry": self.function_hash})
        forged = Snapshot("forged-root", valid.selections, valid.parent_roots)
        result = audit_candidate_snapshot_graph(self.store, forged)
        self.assertFalse(result.valid)
        self.assertTrue(any("Snapshot root does not match" in error for error in result.errors))

    def test_graph_digest_is_deterministic(self):
        snapshot = make_snapshot({"entry": self.function_hash})
        first = audit_candidate_snapshot_graph(self.store, snapshot)
        second = audit_candidate_snapshot_graph(self.store, snapshot)
        self.assertEqual(first.graph_digest, second.graph_digest)
        self.assertEqual(first.edge_set_digest, second.edge_set_digest)


if __name__ == "__main__":
    unittest.main()
