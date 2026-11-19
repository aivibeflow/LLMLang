import unittest

from rt03_mutable_predicate_identity import (
    concrete_routes,
    independently_versioned_routes,
    name_conflated_routes,
    transition_constrained_routes,
)


class MutablePredicateIdentityTests(unittest.TestCase):
    def test_reusing_one_name_for_mutable_reads_unsoundly_drops_reachable_routes(self):
        concrete = concrete_routes()
        conflated = name_conflated_routes()
        self.assertEqual(concrete, frozenset({(False, True), (True, False)}))
        self.assertTrue(concrete - conflated)
        self.assertNotEqual(concrete, conflated)

    def test_versioning_without_write_relation_is_only_an_overapproximation(self):
        concrete = concrete_routes()
        independent = independently_versioned_routes()
        self.assertTrue(concrete <= independent)
        self.assertEqual(len(independent - concrete), 2)

    def test_versioned_predicates_with_write_relation_match_concrete_routes(self):
        self.assertEqual(transition_constrained_routes(), concrete_routes())


if __name__ == "__main__":
    unittest.main()
