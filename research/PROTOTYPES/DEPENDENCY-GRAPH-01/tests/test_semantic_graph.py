import unittest

from src.semantic_graph import (
    ContentStore,
    Dependency,
    RelationStore,
    make_snapshot,
    merge_snapshots,
    run_100_caller_experiment,
    verification_key,
)


class SemanticGraphTests(unittest.TestCase):
    def test_only_three_of_one_hundred_callers_change(self):
        result = run_100_caller_experiment()
        self.assertEqual(result["caller_count"], 100)
        self.assertEqual(result["changed_callers"], ["caller_001", "caller_002", "caller_003"])
        self.assertEqual(result["unchanged_callers"], 97)
        self.assertTrue(result["old_tax_still_stored"])
        self.assertTrue(result["new_tax_stored"])
        self.assertEqual(result["historical_dependents_of_old_tax"], 100)
        self.assertEqual(result["active_dependents_of_old_tax"], 97)
        self.assertEqual(result["active_dependents_of_new_tax"], 3)

    def test_identical_values_deduplicate(self):
        store = ContentStore()
        a = store.put("constant", {"value": 42})
        b = store.put("constant", {"value": 42})
        self.assertEqual(a, b)
        self.assertEqual(len(store), 1)

    def test_non_hash_relevant_provenance_does_not_change_value_hash(self):
        store = ContentStore()
        target = store.put("constant", {"value": 1})
        a = store.put("function", {"body": "x"})
        b = store.put("function", {"body": "x"})
        self.assertEqual(a, b)
        relations = RelationStore()
        relations.add("project-A", a, "implements", "R1")
        relations.add("project-B", b, "implements", "R2")
        self.assertEqual(len(relations.for_scope("project-A")), 1)
        self.assertEqual(len(relations.for_scope("project-B")), 1)
        self.assertIn(target, store)

    def test_stored_payload_cannot_be_mutated_through_read(self):
        store = ContentStore()
        value_hash = store.put("record", {"nested": {"value": 1}})
        exposed = store.get(value_hash).payload
        exposed["nested"]["value"] = 999
        self.assertEqual(store.get(value_hash).payload["nested"]["value"], 1)

    def test_hash_relevant_dependency_changes_dependent_hash(self):
        store = ContentStore()
        d0 = store.put("constant", {"value": 0})
        d1 = store.put("constant", {"value": 1})
        c0 = store.put("function", {"body": "call"}, [Dependency("calls", d0)])
        c1 = store.put("function", {"body": "call"}, [Dependency("calls", d1)])
        self.assertNotEqual(c0, c1)

    def test_rebuilt_dependency_chain_gets_new_hashes(self):
        store = ContentStore()
        leaf0 = store.put("constant", {"v": 0})
        middle0 = store.put("function", {"body": "m"}, [Dependency("uses", leaf0)])
        root0 = store.put("function", {"body": "r"}, [Dependency("uses", middle0)])
        leaf1 = store.put("constant", {"v": 1})
        middle1 = store.put("function", {"body": "m"}, [Dependency("uses", leaf1)])
        root1 = store.put("function", {"body": "r"}, [Dependency("uses", middle1)])
        self.assertNotEqual(leaf0, leaf1)
        self.assertNotEqual(middle0, middle1)
        self.assertNotEqual(root0, root1)

    def test_transitive_reverse_impact(self):
        store = ContentStore()
        leaf = store.put("constant", {"v": 1})
        middle = store.put("function", {"body": "m"}, [Dependency("uses", leaf)])
        root = store.put("function", {"body": "r"}, [Dependency("uses", middle)])
        self.assertEqual(store.dependents(leaf), {middle})
        self.assertEqual(store.dependents(leaf, transitive=True), {middle, root})

    def test_disjoint_snapshot_changes_merge(self):
        base = make_snapshot({"a": "A0", "b": "B0"})
        left = make_snapshot({"a": "A1", "b": "B0"}, (base.root_hash,))
        right = make_snapshot({"a": "A0", "b": "B1"}, (base.root_hash,))
        merged, conflicts = merge_snapshots(base, left, right)
        self.assertFalse(conflicts)
        self.assertEqual(merged.mapping, {"a": "A1", "b": "B1"})
        self.assertEqual(set(merged.parent_roots), {left.root_hash, right.root_hash})

    def test_same_selection_key_conflicts(self):
        base = make_snapshot({"a": "A0"})
        left = make_snapshot({"a": "A1"})
        right = make_snapshot({"a": "A2"})
        merged, conflicts = merge_snapshots(base, left, right)
        self.assertIsNone(merged)
        self.assertEqual(conflicts["a"], ("A1", "A2"))

    def test_verification_key_changes_with_closure_or_verifier(self):
        args = ("value", "closure", "verifier-v1", {"mode": "strict"})
        k1 = verification_key(*args)
        k2 = verification_key("value", "closure-2", "verifier-v1", {"mode": "strict"})
        k3 = verification_key("value", "closure", "verifier-v2", {"mode": "strict"})
        self.assertNotEqual(k1, k2)
        self.assertNotEqual(k1, k3)


if __name__ == "__main__":
    unittest.main()
