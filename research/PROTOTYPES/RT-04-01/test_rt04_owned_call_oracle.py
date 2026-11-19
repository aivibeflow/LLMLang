import unittest
from itertools import product

from rt04_owned_call import execute_owned_call_tree
from rt04_owned_call_oracle import run_oracle


class OwnedCallOracleCrossCheck(unittest.TestCase):
    def test_bounded_tree_space_matches_tree_interpreter(self):
        actions = ["use", "release", "transfer", "propagate_owned", "ignore", "duplicate"]
        leaves = actions + [{"sequence": []}]
        trees = list(leaves)
        trees.extend({"sequence": [left, right]} for left, right in product(leaves, repeat=2))
        trees.extend({"if": [left, right]} for left, right in product(leaves, repeat=2))
        trees.extend({"release_attempt": {"ok": left, "error": right}}
                     for left, right in product(leaves, repeat=2))
        environment_vectors = list(product([False, True], repeat=2))
        comparisons = 0
        for tree, release_results, branch_choices, carries, owned in product(
            trees, environment_vectors, environment_vectors, [False, True], [False, True]
        ):
            expected = run_oracle(
                tree, release_results=list(release_results),
                branch_choices=list(branch_choices),
                output_carries_owned=carries, owned_on_entry=owned,
            )
            actual = execute_owned_call_tree(
                tree, release_results=list(release_results),
                branch_choices=list(branch_choices),
                output_carries_owned=carries, owned_on_entry=owned,
            )
            self.assertEqual(
                (actual.status, actual.events, actual.terminal_owner, actual.findings),
                (expected.status, expected.events, expected.owner, expected.findings),
                msg=f"tree={tree}, releases={release_results}, branches={branch_choices}",
            )
            comparisons += 1
        self.assertEqual(len(trees), 154)
        self.assertEqual(comparisons, 154 * 4 * 4 * 2 * 2)

    def test_oracle_exposes_incomplete_environment_inputs(self):
        result = run_oracle(
            {"release_attempt": {"ok": {"sequence": []}, "error": "release"}},
            release_results=[],
        )
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("MISSING_OR_INVALID_RELEASE_RESULT", result.findings)


if __name__ == "__main__":
    unittest.main()
