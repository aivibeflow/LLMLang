import unittest

from package_closure import ClosureError, resolve_dependency_closure
from package_index import logical_hash

H = lambda n: "sha256:" + format(n, "064x")


class Snapshot:
    def __init__(self, objects, dependencies, snapshot_id="snapshot-1"):
        self.objects = {row['hash']: row for row in objects}
        self.dependencies = dict(dependencies)
        self.snapshot_id = snapshot_id
        self.object_requests = []

    def get_object(self, content_hash):
        self.object_requests.append(content_hash)
        return self.objects[content_hash]

    def get_dependencies(self, source_hash):
        return self.dependencies.get(source_hash, [])


def make_snapshot():
    objects = [{"hash": H(n), "kind": "function", "size": n * 10} for n in range(1, 7)]
    edges = {
        H(1): [
            {"edge_id": "required-a", "kind": "required", "target_hash": H(2)},
            {"edge_id": "optional-a", "kind": "optional", "target_hash": H(3)},
            {"edge_id": "target-a", "kind": "target", "target_hash": H(6)},
            {"edge_id": "evidence-a", "kind": "evidence", "target_hash": H(5)},
        ],
        H(2): [{"edge_id": "required-b", "kind": "required", "target_hash": H(4)}],
        H(3): [{"edge_id": "required-c", "kind": "required", "target_hash": H(4)}],
        H(4): [{"edge_id": "cycle", "kind": "required", "target_hash": H(1)}],
    }
    return Snapshot(objects, edges)


def included(result):
    return {row["hash"] for row in result["index"]["objects"]}


class DependencyClosureTests(unittest.TestCase):
    def test_required_transitive_chain_and_cycle(self):
        result = resolve_dependency_closure([H(1)], make_snapshot())
        self.assertEqual(included(result), {H(1), H(2), H(4)})

    def test_optional_edges_are_not_followed_by_closure(self):
        result = resolve_dependency_closure([H(1)], make_snapshot(), policy="closure")
        self.assertNotIn(H(3), included(result))
        edges = {row["edge_id"]: row for row in result["index"]["dependencies"]}
        self.assertFalse(edges["optional-a"]["included"])

    def test_closure_with_optional_includes_optional_transitive_closure(self):
        result = resolve_dependency_closure([H(1)], make_snapshot(), policy="closure_with_optional")
        self.assertEqual(included(result), {H(1), H(2), H(3), H(4)})

    def test_roots_only_preserves_direct_edges_as_external(self):
        result = resolve_dependency_closure([H(1)], make_snapshot(), policy="roots_only")
        self.assertEqual(included(result), {H(1)})
        self.assertEqual({row["source_hash"] for row in result["index"]["dependencies"]}, {H(1)})
        self.assertTrue(all(not row["included"] for row in result["index"]["dependencies"]))

    def test_root_order_does_not_change_output(self):
        first = resolve_dependency_closure([H(1), H(2)], make_snapshot())
        second = resolve_dependency_closure([H(2), H(1)], make_snapshot())
        self.assertEqual(first["index"], second["index"])
        self.assertEqual(logical_hash(first["index"]), logical_hash(second["index"]))

    def test_diamond_graph_deduplicates_shared_dependency(self):
        snapshot = make_snapshot()
        result = resolve_dependency_closure([H(1)], snapshot, policy="closure_with_optional")
        self.assertEqual(sum(row["hash"] == H(4) for row in result["index"]["objects"]), 1)
        self.assertEqual(snapshot.object_requests.count(H(4)), 1)

    def test_missing_required_dependency_fails(self):
        snapshot = make_snapshot()
        snapshot.objects.pop(H(2))
        with self.assertRaisesRegex(ClosureError, "missing exact dependency object"):
            resolve_dependency_closure([H(1)], snapshot)

    def test_exact_hash_mismatch_is_never_substituted(self):
        snapshot = make_snapshot()
        snapshot.objects[H(2)] = {"hash": H(99), "kind": "function", "size": 20}
        with self.assertRaisesRegex(ClosureError, "different hash"):
            resolve_dependency_closure([H(1)], snapshot)

    def test_conditional_dependency_requires_explicit_selection(self):
        snapshot = make_snapshot()
        snapshot.dependencies[H(1)].append({
            "edge_id": "conditional", "kind": "required", "target_hash": H(5),
            "condition": {"feature": "extra"},
        })
        with self.assertRaisesRegex(ClosureError, "explicit boolean selection"):
            resolve_dependency_closure([H(1)], snapshot)

    def test_conditional_dependency_false_is_not_followed(self):
        snapshot = make_snapshot()
        snapshot.dependencies[H(1)].append({
            "edge_id": "conditional", "kind": "required", "target_hash": H(5),
            "condition": {"feature": "extra"},
        })
        result = resolve_dependency_closure(
            [H(1)], snapshot, condition_values={(H(1), "conditional"): False}
        )
        self.assertNotIn(H(5), included(result))

    def test_conditional_dependency_true_is_followed(self):
        snapshot = make_snapshot()
        snapshot.dependencies[H(1)].append({
            "edge_id": "conditional", "kind": "required", "target_hash": H(5),
            "condition": {"feature": "extra"},
        })
        result = resolve_dependency_closure(
            [H(1)], snapshot, condition_values={(H(1), "conditional"): True}
        )
        self.assertIn(H(5), included(result))

    def test_snapshot_change_is_rejected(self):
        class ChangingSnapshot(Snapshot):
            def get_dependencies(self, source_hash):
                result = super().get_dependencies(source_hash)
                self.snapshot_id = "snapshot-2"
                return result
        base = make_snapshot()
        changing = ChangingSnapshot(list(base.objects.values()), base.dependencies)
        with self.assertRaisesRegex(ClosureError, "snapshot changed"):
            resolve_dependency_closure([H(1)], changing)


    def test_malformed_dependency_kind_fails_closed(self):
        snapshot = make_snapshot()
        snapshot.dependencies[H(1)].append({
            "edge_id": "bad-kind", "kind": [], "target_hash": H(5),
        })
        with self.assertRaisesRegex(ClosureError, "unsupported dependency kind"):
            resolve_dependency_closure([H(1)], snapshot)
\n    def test_roots_must_exist(self):
        with self.assertRaisesRegex(ClosureError, "missing exact dependency object"):
            resolve_dependency_closure([H(99)], make_snapshot())

    def test_duplicate_roots_and_invalid_policy_fail(self):
        with self.assertRaisesRegex(ClosureError, "duplicate package root"):
            resolve_dependency_closure([H(1), H(1)], make_snapshot())
        with self.assertRaisesRegex(ClosureError, "unsupported dependency policy"):
            resolve_dependency_closure([H(1)], make_snapshot(), policy="everything")

    def test_conditional_optional_not_selected_by_required_only_policy(self):
        snapshot = make_snapshot()
        snapshot.dependencies[H(1)].append({
            "edge_id": "conditional-optional", "kind": "optional", "target_hash": H(5),
            "condition": {"feature": "opt"},
        })
        result = resolve_dependency_closure([H(1)], snapshot, policy="closure")
        self.assertNotIn(H(5), included(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
