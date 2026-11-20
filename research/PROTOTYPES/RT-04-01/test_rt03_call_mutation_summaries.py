import unittest

from rt03_call_mutation_summaries import (
    enumerate_call_summary,
    name_conflated_routes,
)


class CallMutationSummaryTests(unittest.TestCase):
    def test_complete_pure_summary_preserves_the_value(self):
        self.assertEqual(
            enumerate_call_summary("pure"),
            frozenset({(False, False), (True, True)}),
        )

    def test_complete_toggle_summary_produces_only_crossed_routes(self):
        self.assertEqual(
            enumerate_call_summary("toggle"),
            frozenset({(False, True), (True, False)}),
        )

    def test_may_write_or_unknown_summary_havocs_the_post_call_value(self):
        expected = frozenset({
            (False, False), (False, True), (True, False), (True, True),
        })
        self.assertEqual(enumerate_call_summary("may_write"), expected)
        self.assertEqual(enumerate_call_summary("unknown"), expected)

    def test_assuming_stability_for_an_unknown_call_drops_possible_routes(self):
        possible = enumerate_call_summary("unknown")
        conflated = name_conflated_routes()
        self.assertTrue(possible - conflated)
        self.assertEqual(possible - conflated, {(False, True), (True, False)})

    def test_unknown_summary_is_not_silently_treated_as_pure(self):
        self.assertNotEqual(
            enumerate_call_summary("unknown"), enumerate_call_summary("pure")
        )


if __name__ == "__main__":
    unittest.main()
