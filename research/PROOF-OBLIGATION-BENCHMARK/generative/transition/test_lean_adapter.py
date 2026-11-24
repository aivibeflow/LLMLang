import json
import unittest

from lean_adapter import audits_claims, compare_smt, experiment


class LeanAdapterTests(unittest.TestCase):
    def test_experiment_has_one_theorem_per_case_and_two_controls(self):
        source, records = experiment()
        self.assertEqual(len(records), 798)
        self.assertEqual(source.count("#print axioms"), len(records) + 2)
        self.assertIn("theorem controlAll : observe [0] controlActions ≠ [[0], [0]]", source)
        self.assertIn("getLast? = some [0]", source)

    def test_audit_rejects_missing_claim_and_extra_axioms(self):
        report = "'first' does not depend on any axioms\n"
        self.assertTrue(audits_claims(report, ["first"]))
        self.assertFalse(audits_claims(report, ["first", "second"]))
        self.assertFalse(audits_claims("'first' depends on axioms: [sorryAx]", ["first"]))

    def test_smt_comparison_rejects_changes_in_scope_and_outcome(self):
        _, records = experiment()
        record = records[0]
        observation = {**record, "solver": "unsat", "outcome": "bounded-agreement"}
        controls = [
            {"control": "all-boundaries", "solver": "sat", "outcome": "replayed-counterexample"},
            {"control": "final-only", "solver": "unsat", "outcome": "translation-or-solver-conflict"},
        ]

        def compare(row):
            return compare_smt("\n".join(map(json.dumps, [row, *controls])), [record])

        self.assertTrue(compare(observation))
        self.assertFalse(compare({**observation, "trace": ["transfer"]}))
        self.assertFalse(compare({**observation, "model_sha256": "changed"}))
        self.assertFalse(compare({**observation, "solver": "unknown"}))


if __name__ == "__main__":
    unittest.main()
