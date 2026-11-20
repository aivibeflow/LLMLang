from dataclasses import replace
from itertools import permutations, product
import unittest

from src.recursive_identity import (
    Call, Definition, External, RecursiveIdentityError, _components, publish_definitions,
)
from src.semantic_graph import ContentStore


class RecursiveIdentityExperiment(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.definitions = {
            "even": Definition(("base", True, Call("odd")), "left"),
            "odd": Definition(("base", False, Call("even")), "right"),
            "entry": Definition((Call("even"),)),
            "independent": Definition((42,)),
        }

    def recursive_root(self, address):
        return self.store.get(address).dependencies[0].target_hash

    def test_acyclic_addresses_agree_and_dag_only_rejects_cycles(self):
        acyclic = {"leaf": Definition((42,)), "caller": Definition((Call("leaf"),))}
        expected = publish_definitions(self.store, acyclic, "dag-only")
        for mode in ("keyed", "structural"):
            self.assertEqual(publish_definitions(self.store, acyclic, mode), expected)
        for cyclic in (self.definitions, {"self": Definition((Call("self"),), "slot")}):
            with self.assertRaisesRegex(RecursiveIdentityError, "unsupported by dag-only"):
                publish_definitions(self.store, cyclic, "dag-only")
            for mode in ("keyed", "structural"):
                self.assertTrue(publish_definitions(self.store, cyclic, mode))

    def test_display_rename_and_reordering_preserve_both_group_schemes(self):
        rename = {"even": "zzz", "odd": "aaa", "entry": "run", "independent": "answer"}
        for mode in ("keyed", "structural"):
            expected = publish_definitions(self.store, self.definitions, mode)
            for order in permutations(self.definitions):
                renamed = {
                    rename[name]: replace(self.definitions[name], body=tuple(
                        Call(rename[token.target]) if isinstance(token, Call) else token
                        for token in self.definitions[name].body
                    ))
                    for name in order
                }
                self.assertEqual(
                    publish_definitions(self.store, renamed, mode),
                    {rename[name]: address for name, address in expected.items()},
                )

    def test_keyed_identity_depends_on_slot_allocation_but_structural_does_not(self):
        revised = {**self.definitions, "even": replace(self.definitions["even"], slot_key="new-key")}
        for mode in ("keyed", "structural"):
            old = publish_definitions(self.store, self.definitions, mode)
            new = publish_definitions(self.store, revised, mode)
            changed = {name for name, address in old.items() if new[name] != address}
            self.assertEqual(changed, {"entry", "even", "odd"} if mode == "keyed" else set())

    def test_symmetric_terms_share_a_structural_address_but_keyed_members_stay_distinct(self):
        symmetric = {"left": Definition((Call("right"),), "a"),
                     "right": Definition((Call("left"),), "b")}
        plain = publish_definitions(self.store, symmetric, "structural")
        scoped = publish_definitions(self.store, symmetric, "keyed")
        self.assertEqual(plain["left"], plain["right"])
        self.assertNotEqual(scoped["left"], scoped["right"])
        self.assertEqual(self.recursive_root(scoped["left"]), self.recursive_root(scoped["right"]))

    def test_edit_and_cycle_split_invalidate_only_the_group_and_its_dependents(self):
        for mode in ("keyed", "structural"):
            original = publish_definitions(self.store, self.definitions, mode)
            root = self.recursive_root(original["odd"])
            self.assertEqual(self.recursive_root(original["even"]), root)
            self.assertEqual(self.store.dependents(root, transitive=True),
                             {original["even"], original["odd"], original["entry"]})
            for body in (("base", True, Call("even")), ("returned", False)):
                candidate = dict(self.definitions, odd=Definition(body, "right"))
                new = publish_definitions(self.store, candidate, mode)
                self.assertEqual({name for name in original if new[name] != original[name]},
                                 {"even", "odd", "entry"})
            self.assertIn(root, self.store)

    def test_external_address_and_body_order_are_hash_relevant(self):
        before = self.store.put("constant", {"value": 1})
        after = self.store.put("constant", {"value": 2})
        for mode in ("keyed", "structural"):
            roots = set()
            for body in (
                (External(before), Call("odd")),
                (External(after), Call("odd")),
                (Call("odd"), External(before)),
            ):
                definitions = dict(self.definitions, even=Definition(body, "left"))
                addresses = publish_definitions(self.store, definitions, mode)
                roots.add(self.recursive_root(addresses["odd"]))
            self.assertEqual(len(roots), 3)

    def test_component_partition_matches_mutual_reachability_on_all_three_node_graphs(self):
        names = ("a", "b", "c")
        edges = tuple(product(names, repeat=2))
        for mask in range(1 << len(edges)):
            graph = {node: set() for node in names}
            for bit, (source, target) in enumerate(edges):
                if mask & (1 << bit):
                    graph[source].add(target)

            def reach(node):
                reached = {node}
                for _ in names:
                    reached |= set().union(*(graph[current] for current in reached))
                return reached

            expected = {frozenset(other for other in reach(node) if node in reach(other)) for node in names}
            self.assertEqual({frozenset(group) for group in _components(graph)}, expected, mask)

    def test_structural_addresses_merge_only_members_related_by_a_body_automorphism(self):
        names = ("a", "b", "c")
        # Every member has two ordered call positions. Exhaust all 3^6 assignments.
        for calls in product(names, repeat=6):
            bodies = {node: calls[index:index + 2] for index, node in zip((0, 2, 4), names)}
            graph = {source: set(targets) for source, targets in bodies.items()}
            if len(_components(graph)) != 1:
                continue
            definitions = {source: Definition(tuple(map(Call, targets))) for source, targets in bodies.items()}
            addresses = publish_definitions(self.store, definitions, "structural")
            orbits = {(node, node) for node in names}
            for order in permutations(names):
                rename = dict(zip(names, order))
                if all(tuple(rename[target] for target in bodies[node]) == bodies[rename[node]] for node in names):
                    orbits.update(rename.items())
            observed = {(left, right) for left, right in product(names, repeat=2)
                        if addresses[left] == addresses[right]}
            self.assertEqual(observed, orbits, bodies)

    def test_unresolved_refs_and_unsupported_group_shapes_stop_before_publication(self):
        over_limit = {
            str(index): Definition((Call(str((index + 1) % 7)),), str(index))
            for index in range(7)
        }
        for graph, mode, diagnostic in (
            ({"bad": Definition((Call("missing"),))}, "structural", "unknown call target"),
            ({"bad": Definition((External("missing"),))}, "keyed", "unknown external dependency"),
            (over_limit, "structural", "search bound"),
            (dict(self.definitions, odd=Definition((Call("even"),), "left")), "keyed", "unique slot key"),
        ):
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(RecursiveIdentityError, diagnostic):
                publish_definitions(self.store, graph, mode)
            self.assertEqual(len(self.store), 0)


if __name__ == "__main__":
    unittest.main()
