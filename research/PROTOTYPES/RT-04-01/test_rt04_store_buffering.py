import unittest

from rt04_store_buffering import (
    message_passing_outcomes,
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
        self.assertEqual(
            message_passing_outcomes(synchronized=False),
            {(0, 0), (0, 1), (1, 0), (1, 1)},
        )


if __name__ == "__main__":
    unittest.main()
