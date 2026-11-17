import unittest

from src.business_intent import (
    BusinessRule, ClarificationDecision, FormalCandidate, FormalClause,
    IntentModelError, IntentSource, accept_candidate, calculate_tax,
    candidate_from_rule, run_two_caller_scenario, select_applicable_rate,
)


class BusinessIntentTests(unittest.TestCase):
    def make_rule(self):
        source = IntentSource.create("Preferred customers receive 12% tax.")
        decision = ClarificationDecision.create(
            source, "Which date applies?", ["order_date", "invoice_date"],
            "order_date", "Tax policy owner")
        rule = BusinessRule.create("preferred_order", 1200, "2026-12-01",
                                   "order_date", source, decision)
        return source, decision, rule

    def test_clarification_requires_explicit_selected_alternative_and_authority(self):
        source = IntentSource.create("Use the new rate next month.")
        with self.assertRaises(IntentModelError):
            ClarificationDecision.create(source, "Which date?", ["order", "invoice"],
                                         "processing", "Owner")
        with self.assertRaises(IntentModelError):
            ClarificationDecision.create(source, "Which date?", ["order", "invoice"],
                                         "order", "")

    def test_business_rule_is_caller_scoped_and_date_basis_is_explicit(self):
        source, decision, rule = self.make_rule()
        self.assertEqual(rule.caller, "preferred_order")
        self.assertEqual(rule.date_basis, "order_date")
        with self.assertRaises(IntentModelError):
            BusinessRule.create("preferred_order", 1200, "2026-12-01",
                                "implicit", source, decision)

    def test_candidate_clauses_retain_source_and_decision_provenance(self):
        source, decision, rule = self.make_rule()
        candidate = candidate_from_rule(rule)
        self.assertEqual(len(candidate.clauses), 2)
        for clause in candidate.clauses:
            self.assertIn(source.source_hash, clause.source_refs)
            self.assertIn(decision.decision_hash, clause.decision_refs)
            self.assertEqual(clause.provenance_status, "GROUNDED")

    def test_acceptance_requires_authorized_human(self):
        _, _, rule = self.make_rule()
        candidate = candidate_from_rule(rule)
        with self.assertRaises(IntentModelError):
            accept_candidate(candidate, "", authorized=True)
        with self.assertRaises(IntentModelError):
            accept_candidate(candidate, "LLM", authorized=False)
        accepted = accept_candidate(candidate, "Tax policy owner", authorized=True)
        self.assertEqual(accepted.candidate_hash, candidate.candidate_hash)

    def test_unresolved_or_ungrounded_clause_blocks_acceptance(self):
        _, _, rule = self.make_rule()
        unresolved = FormalClause.create("rate", "rate == 1200", "rate is 12%",
                                         [rule.source_hash], provenance_status="UNRESOLVED")
        candidate = FormalCandidate.create("preferred_order", rule, [unresolved])
        with self.assertRaises(IntentModelError):
            accept_candidate(candidate, "Owner", authorized=True)
        unsupported = FormalClause.create("rate", "rate == 1200", "rate is 12%", [])
        candidate2 = FormalCandidate.create("preferred_order", rule, [unsupported])
        with self.assertRaises(IntentModelError):
            accept_candidate(candidate2, "Owner", authorized=True)

    def test_effective_date_examples_distinguish_order_date_from_invoice_date(self):
        baseline_source = IntentSource.create("15% applies from 2026-01-01.")
        baseline_decision = ClarificationDecision.create(
            baseline_source, "Which date applies?", ["order_date", "invoice_date"],
            "order_date", "Tax policy owner")
        baseline = BusinessRule.create("preferred_order", 1500, "2026-01-01",
                                       "order_date", baseline_source, baseline_decision)
        new_source = IntentSource.create("12% applies from 2026-12-01.")
        new_decision = ClarificationDecision.create(
            new_source, "Which date applies?", ["order_date", "invoice_date"],
            "order_date", "Tax policy owner")
        new_rule = BusinessRule.create("preferred_order", 1200, "2026-12-01",
                                       "order_date", new_source, new_decision)
        invoice_baseline_decision = ClarificationDecision.create(
            baseline_source, "Which date applies?", ["order_date", "invoice_date"],
            "invoice_date", "Tax policy owner")
        invoice_new_decision = ClarificationDecision.create(
            new_source, "Which date applies?", ["order_date", "invoice_date"],
            "invoice_date", "Tax policy owner")
        invoice_baseline = BusinessRule.create(
            "preferred_order", 1500, "2026-01-01", "invoice_date",
            baseline_source, invoice_baseline_decision)
        invoice_new = BusinessRule.create(
            "preferred_order", 1200, "2026-12-01", "invoice_date",
            new_source, invoice_new_decision)
        self.assertEqual(select_applicable_rate(
            [baseline, new_rule], "2026-11-30", "2026-12-05"), 1500)
        self.assertEqual(select_applicable_rate(
            [invoice_baseline, invoice_new], "2026-11-30", "2026-12-05"), 1200)
        self.assertEqual(select_applicable_rate(
            [baseline, new_rule], "2026-12-01", "2026-11-30"), 1200)
        self.assertEqual(select_applicable_rate(
            [invoice_baseline, invoice_new], "2026-12-01", "2026-11-30"), 1500)

    def test_generic_tax_calculation_accepts_explicit_policy_input(self):
        self.assertEqual(calculate_tax(10_000, 1200), 1200)
        self.assertEqual(calculate_tax(10_000, 2000), 2000)
        self.assertEqual(calculate_tax(1, 5000), 1)  # half-up cent rounding

    def test_policy_change_updates_only_preferred_caller(self):
        result = run_two_caller_scenario()
        self.assertEqual(result["changed_selection_keys"], ["caller:preferred_order"])
        self.assertTrue(result["tax_contract_unchanged"])
        self.assertTrue(result["standard_caller_unchanged"])
        self.assertTrue(result["preferred_caller_changed"])
        self.assertEqual(result["old_rate_basis_points"], 1500)
        self.assertEqual(result["new_rate_basis_points"], 1200)
        self.assertEqual(result["standard_rate_basis_points"], 2000)
        self.assertEqual(result["review_examples"]["day_before_effective_date"], 1500)
        self.assertEqual(result["review_examples"]["effective_date_boundary"], 1200)
        self.assertEqual(result["review_examples"]["counterexample_order_before_invoice_after"],
                         {"order_date_interpretation": 1500,
                          "invoice_date_interpretation": 1200})

    def test_snapshot_hash_changes_but_callee_contract_hash_does_not(self):
        result = run_two_caller_scenario()
        self.assertNotEqual(result["old_snapshot"], result["new_snapshot"])
        self.assertEqual(result["old_tax_contract_hash"],
                         result["new_tax_contract_hash"])
        self.assertGreater(result["semantic_values_stored"], 10)


if __name__ == "__main__":
    unittest.main()
