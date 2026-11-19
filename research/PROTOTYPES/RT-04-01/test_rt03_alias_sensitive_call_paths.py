import unittest

from rt03_alias_sensitive_call_paths import (
    incorrectly_assume_no_alias,
    routes_for_alias_targets,
    routes_for_summary,
)


class AliasSensitiveCallPathTests(unittest.TestCase):
    def test_exact_field_alias_produces_toggle_routes(self):
        self.assertEqual(
            routes_for_summary("exact_flag"),
            frozenset({(False, True), (True, False)}),
        )

    def test_exact_nonpredicate_field_alias_preserves_flag(self):
        self.assertEqual(
            routes_for_summary("exact_other"),
            frozenset({(False, False), (True, True)}),
        )

    def test_may_alias_summary_unions_both_transition_relations(self):
        expected = frozenset({
            (False, False), (False, True), (True, False), (True, True),
        })
        self.assertEqual(routes_for_summary("may_alias_either"), expected)
        self.assertEqual(routes_for_summary("unknown_aliases"), expected)

    def test_forgetting_a_possible_alias_drops_reachable_routes(self):
        possible = routes_for_summary("may_alias_either")
        assumed_no_alias = incorrectly_assume_no_alias()
        self.assertEqual(possible - assumed_no_alias, {(False, True), (True, False)})

    def test_alias_target_set_must_be_nonempty_and_within_the_modeled_region(self):
        for targets in (frozenset(), frozenset({"unmodeled"})):
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                routes_for_alias_targets(targets)


if __name__ == "__main__":
    unittest.main()
