import unittest
from src.coverage_guided import (
    CoverageLedger, Factor, PlanningError, build_plan, coverage_report, schedule,
)

class CoverageGuidedTests(unittest.TestCase):
    def setUp(self):
        self.factors = (
            Factor("tier", ("standard", "gold")),
            Factor("discount", (False, True)),
            Factor("region", ("UK", "EU")),
        )
        self.baseline = {"tier": "standard", "discount": False, "region": "UK"}
        self.plan = build_plan(
            artifact_hash="a1", context_digest="ctx", observation_model_digest="obs",
            factors=self.factors, baseline=self.baseline, max_interaction_order=2,
        )

    def test_plan_contains_single_and_pairwise_interventions(self):
        self.assertTrue(any(len(c.changed_factors) == 1 for c in self.plan.candidates))
        self.assertTrue(any(len(c.changed_factors) == 2 for c in self.plan.candidates))
        self.assertTrue(any(t.startswith("interaction:2:")
                            for c in self.plan.candidates for t in c.targets))

    def test_scheduler_prioritizes_uncovered_targets_and_is_deterministic(self):
        first = schedule(self.plan, CoverageLedger(), 4)
        second = schedule(self.plan, CoverageLedger(), 4)
        self.assertEqual([c.digest for c in first], [c.digest for c in second])
        self.assertEqual(len(first), 4)

    def test_ledger_records_planned_and_runtime_feedback_dimensions(self):
        candidate = schedule(self.plan, CoverageLedger(), 1)[0]
        ledger = CoverageLedger()
        ledger.record(candidate, semantic_partitions=("partition:tax-exempt",),
                      branches=("branch:discount-active",),
                      taint_paths=("taint:rate-to-output",),
                      trace_events=("trace:policy-selected",),
                      outcome_classes=("outcome:tax-changed",))
        self.assertTrue(candidate.targets.issubset(ledger.covered))
        self.assertIn("partition:tax-exempt", ledger.covered)
        self.assertIn("branch:discount-active", ledger.covered)
        self.assertEqual(coverage_report(self.plan, ledger)["executed_candidate_count"], 1)

    def test_scheduler_does_not_repeat_executed_candidates(self):
        ledger = CoverageLedger()
        first = schedule(self.plan, ledger, 1)[0]
        ledger.record(first)
        next_batch = schedule(self.plan, ledger, 1)
        self.assertNotEqual(first.digest, next_batch[0].digest)

    def test_budget_does_not_hide_uncovered_targets(self):
        batch = schedule(self.plan, CoverageLedger(), 1)
        ledger = CoverageLedger()
        ledger.record(batch[0])
        report = coverage_report(self.plan, ledger)
        self.assertGreater(len(report["uncovered_targets"]), 0)
        self.assertLess(report["coverage_ratio"], 1.0)

    def test_context_and_artifact_are_part_of_candidate_identity(self):
        other = build_plan(artifact_hash="a2", context_digest="ctx",
                           observation_model_digest="obs", factors=self.factors,
                           baseline=self.baseline)
        self.assertNotEqual({c.digest for c in self.plan.candidates},
                            {c.digest for c in other.candidates})

    def test_invalid_baseline_and_budget_rejected(self):
        with self.assertRaises(PlanningError):
            build_plan(artifact_hash="a", context_digest="c", observation_model_digest="o",
                       factors=self.factors,
                       baseline={"tier": "invalid", "discount": False, "region": "UK"})
        with self.assertRaises(PlanningError):
            schedule(self.plan, CoverageLedger(), -1)

    def test_pairwise_only_does_not_claim_higher_order_coverage(self):
        three_way = build_plan(artifact_hash="a", context_digest="c",
                               observation_model_digest="o", factors=self.factors,
                               baseline=self.baseline, max_interaction_order=3)
        self.assertTrue(any(t.startswith("interaction:3:")
                            for t in three_way.target_universe))
        self.assertFalse(any(t.startswith("interaction:3:")
                             for t in self.plan.target_universe))

    def test_numeric_domain_extremes_are_explicit_boundary_targets(self):
        numeric = build_plan(artifact_hash="a", context_digest="c",
                             observation_model_digest="o",
                             factors=(Factor("amount", (0, 1, 10)),),
                             baseline={"amount": 1})
        targets = set().union(*(c.targets for c in numeric.candidates))
        self.assertIn("boundary:amount:minimum=0", targets)
        self.assertIn("boundary:amount:maximum=10", targets)

    def test_static_and_taint_guidance_targets_are_attached_to_candidates(self):
        guided = build_plan(artifact_hash="a", context_digest="c",
                            observation_model_digest="o",
                            factors=(Factor("policy", ("default", "special"),
                                            (("special", ("branch:special",
                                                          "taint:policy-to-output")),)),),
                            baseline={"policy": "default"})
        candidate = next(c for c in guided.candidates
                         if dict(c.assignment)["policy"] == "special")
        self.assertIn("branch:special", candidate.targets)
        self.assertIn("taint:policy-to-output", candidate.targets)

    def test_zero_budget_returns_no_candidates(self):
        self.assertEqual(schedule(self.plan, CoverageLedger(), 0), ())

if __name__ == "__main__":
    unittest.main()
