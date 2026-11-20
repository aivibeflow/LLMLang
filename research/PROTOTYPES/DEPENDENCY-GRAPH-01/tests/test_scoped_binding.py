import unittest
from src.scoped_binding import (
    BindingLayer, BindingPolicy, ScopedBinding, ScopedBindingError,
    resolve_scoped_binding,
)
from src.semantic_graph import ContentStore, Dependency, digest


class ScopedBindingTests(unittest.TestCase):
    def fixture(self):
        store = ContentStore()
        contract = store.put("contract", {"postcondition": "same observable result"})
        impl_project = store.put("implementation", {"body": "project"},
                                 [Dependency("implements", contract, "contract")])
        impl_tenant = store.put("implementation", {"body": "tenant"},
                                [Dependency("implements", contract, "contract")])
        impl_request = store.put("implementation", {"body": "request"},
                                 [Dependency("implements", contract, "contract")])
        policy = BindingPolicy.create()
        def layer(scope, scope_id, impl, marker):
            return BindingLayer(scope, digest({"scope": scope, "id": scope_id}),
                                digest({"snapshot": marker}),
                                (ScopedBinding("tax", contract, impl),))
        return store, contract, impl_project, impl_tenant, impl_request, policy, layer

    def test_request_overrides_tenant_and_project(self):
        store, contract, p, t, r, policy, layer = self.fixture()
        result = resolve_scoped_binding(
            store, "tax", contract,
            [layer("project", "p", p, 1), layer("tenant", "t", t, 2),
             layer("request", "r", r, 3)], policy)
        self.assertEqual(result.implementation_hash, r)
        self.assertEqual(result.winning_scope, "request")
        self.assertEqual([x[0] for x in result.consulted_layers],
                         ["project", "tenant", "request"])

    def test_disallowed_override_is_rejected(self):
        store, contract, p, t, _, _, layer = self.fixture()
        policy = BindingPolicy.create(allowed_overrides=(("project", "tenant"),))
        with self.assertRaisesRegex(ScopedBindingError, "not allowed"):
            resolve_scoped_binding(
                store, "tax", contract,
                [layer("project", "p", p, 1), layer("tenant", "t", t, 2),
                 layer("request", "r", t, 3)], policy)

    def test_contract_mismatch_does_not_fall_back(self):
        store, contract, p, t, _, policy, layer = self.fixture()
        other = store.put("contract", {"postcondition": "different"})
        bad_tenant = BindingLayer("tenant", digest("tenant"),
                                  digest("tenant-snapshot"),
                                  (ScopedBinding("tax", other, t),))
        with self.assertRaisesRegex(ScopedBindingError, "refusing fallback"):
            resolve_scoped_binding(
                store, "tax", contract,
                [layer("project", "p", p, 1), bad_tenant], policy)

    def test_tenant_identity_is_part_of_resolution_identity(self):
        store, contract, p, _, _, policy, layer = self.fixture()
        a = resolve_scoped_binding(
            store, "tax", contract,
            [layer("project", "p", p, 1), layer("tenant", "tenant-A", p, 2)],
            policy)
        b = resolve_scoped_binding(
            store, "tax", contract,
            [layer("project", "p", p, 1), layer("tenant", "tenant-B", p, 2)],
            policy)
        self.assertNotEqual(a.root_hash, b.root_hash)

    def test_consulted_layer_revision_changes_resolution_identity(self):
        store, contract, p, _, _, policy, layer = self.fixture()
        a = resolve_scoped_binding(store, "tax", contract,
                                   [layer("project", "p", p, 1)], policy)
        b = resolve_scoped_binding(store, "tax", contract,
                                   [layer("project", "p", p, 2)], policy)
        self.assertNotEqual(a.root_hash, b.root_hash)

    def test_missing_binding_is_an_error(self):
        store, contract, _, _, _, policy, _ = self.fixture()
        empty = BindingLayer("project", digest("p"), digest("empty"), ())
        with self.assertRaisesRegex(ScopedBindingError, "no binding"):
            resolve_scoped_binding(store, "tax", contract, [empty], policy)

    def test_duplicate_scope_is_rejected(self):
        store, contract, p, _, _, policy, layer = self.fixture()
        with self.assertRaisesRegex(ScopedBindingError, "duplicate scope"):
            resolve_scoped_binding(
                store, "tax", contract,
                [layer("project", "p", p, 1), layer("project", "p2", p, 2)],
                policy)

    def test_layer_input_order_does_not_change_resolution(self):
        store, contract, p, t, _, policy, layer = self.fixture()
        project = layer("project", "p", p, 1)
        tenant = layer("tenant", "t", t, 2)
        a = resolve_scoped_binding(store, "tax", contract, [project, tenant], policy)
        b = resolve_scoped_binding(store, "tax", contract, [tenant, project], policy)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
