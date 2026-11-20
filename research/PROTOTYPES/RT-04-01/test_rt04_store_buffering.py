import unittest

from rt04_store_buffering import (
    message_passing_outcomes,
    atomic_counter_outcomes,
    naive_load_then_store_outcomes,
    same_location_atomic_reads,
    independent_atomic_reads,
    per_location_atomic_outcomes,
    sequentially_consistent_outcomes,
)


class StoreBufferingTests(unittest.TestCase):
    def test_sequential_consistency_forbids_both_zero(self):
        outcomes = sequentially_consistent_outcomes()
        self.assertEqual(outcomes, {(0, 1), (1, 0), (1, 1)})

    def test_independent_location_profile_allows_both_zero(self):
        outcomes = per_location_atomic_outcomes()
        self.assertEqual(outcomes, {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_publication_edge_orders_payload_observation(self):
        self.assertEqual(
            message_passing_outcomes(synchronized=True),
            {(0, 0), (0, 1), (1, 1)},
        )

    def test_atomic_rmw_prevents_lost_counter_updates(self):
        self.assertEqual(atomic_counter_outcomes(0, 1, 2), {2})
        self.assertEqual(naive_load_then_store_outcomes(0, 1, 2), {1, 2})
        self.assertEqual(atomic_counter_outcomes(10, 2, 3), {16})

    def test_same_location_read_read_coherence(self):
        monotone = same_location_atomic_reads(0, (1, 2), 2)
        self.assertIn((1, 2), monotone)
        self.assertNotIn((2, 1), monotone)
        self.assertNotIn((1, 0), monotone)
        self.assertIn((2, 1), independent_atomic_reads(0, (1, 2), 2))
        self.assertEqual(
            message_passing_outcomes(synchronized=False),
            {(0, 0), (0, 1), (1, 0), (1, 1)},
        )


if __name__ == "__main__":
    unittest.main()
