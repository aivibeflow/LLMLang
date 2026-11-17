import unittest
from src.coverage_guided import Factor
from src.multifactor_analysis import MultiFactorStatus
from src.adaptive_discovery import (
    AdaptiveError, AdaptiveLedger, EvidenceStatus, ExperimentKind,
    adaptive_report, build_adaptive_plan, plan_next_batch,
)


class AdaptiveDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.factors = (
            Factor("tier", ("standard", "gold")),
            Factor("discount", (False, True)),
            Factor("region", ("UK", "EU")),
        )
        self.baseline = {"tier": "standard", "discount": False, "region": "UK"}
        self.plan = build_adaptive_plan(
            artifact_hash="artifact", context_digest="ctx", observation_model_digest="obs",
            factors=self.factors, baseline=self.baseline,
        )

    def complete_singles(self, ledger, status=EvidenceStatus.NO_OBSERVED_DIFFERENCE):
        for candidate in self.plan.singles:
            ledger.record(candidate, status)

    def test_starts_with_single_factor_interventions_only(self):
        batch = plan_next_batch(self.plan, AdaptiveLedger(), 100)
        self.assertTrue(batch)
        self.assertTrue(all(c.kind == ExperimentKind.SINGLE_INTERVENTION for c in batch))
        self.assertTrue(all(len(c.cells) == 2 and c.cell_cost == 4 for c in batch))

    def test_single_stage_is_atomic_under_execution_budget(self):
        batch = plan_next_batch(self.plan, AdaptiveLedger(), 7)
        self.assertEqual(sum(c.cell_cost for c in batch), 4)
        self.assertEqual(len(batch), 1)

    def test_pairwise_design_includes_non_baseline_level_pairs(self):
        multi = build_adaptive_plan(
            artifact_hash="a", context_digest="c", observation_model_digest="o",
            factors=(Factor("mode", ("default", "strict", "legacy")),
                     Factor("region", ("UK", "EU", "US"))),
            baseline={"mode": "default", "region": "UK"},
        )
        candidate = next(c for c in multi.pairwise
                         if c.factor_levels == (("strict", "legacy"), ("EU", "US")))
        self.assertEqual(len(candidate.cells), 4)
        self.assertEqual({dict(cell)["mode"] for cell in candidate.cells}, {"strict", "legacy"})
        self.assertEqual({dict(cell)["region"] for cell in candidate.cells}, {"EU", "US"})

    def test_pairwise_blocks_wait_until_all_singles_are_recorded(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        batch = plan_next_batch(self.plan, ledger, 100)
        self.assertTrue(batch)
        self.assertTrue(all(c.kind == ExperimentKind.FACTORIAL_BLOCK for c in batch))
        self.assertTrue(all(len(c.factor_scope) == 2 and len(c.cells) == 4 for c in batch))

    def test_related_pair_is_prioritized(self):
        plan = build_adaptive_plan(
            artifact_hash="artifact", context_digest="ctx", observation_model_digest="obs",
            factors=self.factors, baseline=self.baseline, related_pairs=(("tier", "discount"),),
        )
        ledger = AdaptiveLedger()
        for c in plan.singles:
            ledger.record(c, EvidenceStatus.NO_OBSERVED_DIFFERENCE)
        first = plan_next_batch(plan, ledger, 8)
        self.assertEqual(first[0].factor_scope, ("discount", "tier"))

    def test_single_positive_signal_prioritizes_related_pair_scope(self):
        ledger = AdaptiveLedger()
        for c in self.plan.singles:
            status = (EvidenceStatus.OBSERVED_BEHAVIORAL_INFLUENCE
                      if c.factor_scope == ("tier",) else EvidenceStatus.NO_OBSERVED_DIFFERENCE)
            ledger.record(c, status)
        batch = plan_next_batch(self.plan, ledger, 8)
        self.assertIn("tier", batch[0].factor_scope)

    def test_observed_pair_interaction_triggers_three_factor_block(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = next(c for c in self.plan.pairwise
                    if c.factor_scope == ("discount", "tier"))
        ledger.record(pair, EvidenceStatus.OBSERVED_INTERACTION)
        batch = plan_next_batch(self.plan, ledger, 24)
        self.assertTrue(any(len(c.factor_scope) == 3 and set(c.factor_scope) == {
            "discount", "region", "tier"} for c in batch))
        triple = next(c for c in batch if len(c.factor_scope) == 3)
        self.assertEqual(len(triple.cells), 8)
        self.assertEqual(triple.cell_cost, 16)
        self.assertIn(pair.digest, triple.trigger_digests)

    def test_exploration_reserve_keeps_unrelated_pairs_in_the_batch(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = next(c for c in self.plan.pairwise
                    if c.factor_scope == ("discount", "tier"))
        ledger.record(pair, EvidenceStatus.OBSERVED_INTERACTION)
        batch = plan_next_batch(self.plan, ledger, 24)
        self.assertTrue(any(len(c.factor_scope) == 3 for c in batch))
        self.assertTrue(any(len(c.factor_scope) == 2 and c.digest != pair.digest for c in batch))

    def test_small_budget_does_not_reserve_unusable_exploration_fraction(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = next(c for c in self.plan.pairwise
                    if c.factor_scope == ("discount", "tier"))
        ledger.record(pair, EvidenceStatus.OBSERVED_INTERACTION)
        batch = plan_next_batch(self.plan, ledger, 12)
        self.assertFalse(any(len(c.factor_scope) > 2 for c in batch))
        self.assertLessEqual(sum(c.cell_cost for c in batch), 12)

    def test_no_interaction_result_does_not_trigger_higher_order_escalation(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = next(c for c in self.plan.pairwise
                    if c.factor_scope == ("discount", "tier"))
        ledger.record(pair, EvidenceStatus.NO_INTERACTION_OBSERVED)
        batch = plan_next_batch(self.plan, ledger, 100)
        self.assertFalse(any(len(c.factor_scope) > 2 for c in batch))

    def test_joint_behavioral_influence_is_not_mislabeled_as_interaction(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = next(c for c in self.plan.pairwise
                    if c.factor_scope == ("discount", "tier"))
        ledger.record(pair, EvidenceStatus.OBSERVED_BEHAVIORAL_INFLUENCE)
        batch = plan_next_batch(self.plan, ledger, 100)
        self.assertFalse(any(len(c.factor_scope) > 2 for c in batch))

    def test_inconclusive_experiment_gets_bounded_retry(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = next(c for c in self.plan.pairwise
                    if c.factor_scope == ("discount", "tier"))
        ledger.record(pair, EvidenceStatus.INCONCLUSIVE)
        retry = plan_next_batch(self.plan, ledger, 8)[0]
        self.assertEqual(retry.root_digest, pair.root_digest)
        self.assertEqual(retry.retry_index, 1)
        ledger.record(retry, EvidenceStatus.INCONCLUSIVE)
        batch = plan_next_batch(self.plan, ledger, 100)
        self.assertFalse(any(c.root_digest == pair.root_digest and c.retry_index > 1 for c in batch))

    def test_inconclusive_retry_does_not_mutate_original_candidate_identity(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        pair = self.plan.pairwise[0]
        ledger.record(pair, EvidenceStatus.INCONCLUSIVE)
        retry = next(c for c in plan_next_batch(self.plan, ledger, 8)
                     if c.root_digest == pair.root_digest)
        self.assertNotEqual(retry.digest, pair.digest)
        self.assertEqual(retry.cells, pair.cells)

    def test_budget_never_schedules_partial_factorial_block(self):
        ledger = AdaptiveLedger()
        self.complete_singles(ledger)
        batch = plan_next_batch(self.plan, ledger, 7)
        self.assertEqual(batch, ())

    def test_feedback_is_not_duplicated(self):
        ledger = AdaptiveLedger()
        candidate = self.plan.singles[0]
        ledger.record(candidate, EvidenceStatus.NO_OBSERVED_DIFFERENCE)
        with self.assertRaises(AdaptiveError):
            ledger.record(candidate, EvidenceStatus.NO_OBSERVED_DIFFERENCE)

    def test_guidance_tags_are_preserved_as_observed_feedback(self):
        ledger = AdaptiveLedger()
        candidate = self.plan.singles[0]
        ledger.record(candidate, EvidenceStatus.NO_OBSERVED_DIFFERENCE,
                      guidance_tags=("taint:rate-to-output",),
                      observed_targets=("branch:tax-policy",))
        self.assertIn("branch:tax-policy", ledger.observed_targets)

    def test_accepts_scenario23_status_enum_without_losing_status(self):
        ledger = AdaptiveLedger()
        candidate = self.plan.singles[0]
        ledger.record(candidate, MultiFactorStatus.NO_OBSERVED_DIFFERENCE)
        self.assertEqual(ledger.records[candidate.digest].status,
                         EvidenceStatus.NO_OBSERVED_DIFFERENCE)

    def test_rejects_feedback_from_different_pinned_context(self):
        other = build_adaptive_plan(
            artifact_hash="different-artifact", context_digest="ctx",
            observation_model_digest="obs", factors=self.factors,
            baseline=self.baseline,
        )
        ledger = AdaptiveLedger()
        ledger.record(other.singles[0], EvidenceStatus.NO_OBSERVED_DIFFERENCE)
        with self.assertRaises(AdaptiveError):
            plan_next_batch(self.plan, ledger, 100)

    def test_plan_identity_pins_artifact_context_and_observation_model(self):
        other = build_adaptive_plan(
            artifact_hash="other", context_digest="ctx", observation_model_digest="obs",
            factors=self.factors, baseline=self.baseline,
        )
        self.assertNotEqual(self.plan.plan_digest, other.plan_digest)

    def test_report_keeps_execution_and_observed_coverage_separate(self):
        ledger = AdaptiveLedger()
        c = self.plan.singles[0]
        ledger.record(c, EvidenceStatus.NO_OBSERVED_DIFFERENCE,
                      observed_targets=("trace:event-x",))
        report = adaptive_report(self.plan, ledger)
        self.assertEqual(report["executed_experiment_targets"], sorted(c.targets))
        self.assertEqual(report["observed_feedback_targets"], ["trace:event-x"])
        self.assertFalse(report["semantic_completeness_claim"])

    def test_invalid_related_pair_and_order_are_rejected(self):
        with self.assertRaises(AdaptiveError):
            build_adaptive_plan(
                artifact_hash="a", context_digest="c", observation_model_digest="o",
                factors=self.factors, baseline=self.baseline, related_pairs=(("tier", "missing"),),
            )
        with self.assertRaises(AdaptiveError):
            build_adaptive_plan(
                artifact_hash="a", context_digest="c", observation_model_digest="o",
                factors=self.factors, baseline=self.baseline, max_interaction_order=1,
            )
        with self.assertRaises(AdaptiveError):
            build_adaptive_plan(
                artifact_hash="a", context_digest="c", observation_model_digest="o",
                factors=self.factors, baseline=self.baseline, exploration_fraction=1.1,
            )


if __name__ == "__main__":
    unittest.main()
