import unittest
from src.counterfactual_analysis import (
    ExperimentRun, ExperimentStatus, RunSide, analyze_counterfactual,
)

class CounterfactualAnalysisTests(unittest.TestCase):
    def pair(self,index,side,outcome="same",trace="same-trace",
             context="ctx-1",artifact="program-1",model="obs-1",
             factor="tax_rate",changed=("tax_rate",),input_digest=None):
        is_base=side is RunSide.BASELINE
        return ExperimentRun(artifact,context,model,factor,changed,side,index,
            input_digest or ("input-0" if is_base else "input-1"),
            outcome,trace,f"run-{index}-{side.value}")

    def analyze(self,runs,min_pairs=2):
        return analyze_counterfactual("program-1","ctx-1","obs-1","tax_rate",runs,min_pairs)

    def complete_pairs(self,base_outcome="same",treatment_outcome="same",
                       base_trace="same-trace",treatment_trace="same-trace"):
        rows=[]
        for i in range(2):
            rows.append(self.pair(i,RunSide.BASELINE,base_outcome,base_trace))
            rows.append(self.pair(i,RunSide.TREATMENT,treatment_outcome,treatment_trace))
        return rows

    def test_reproducible_observable_difference_is_positive_evidence(self):
        r=self.analyze(self.complete_pairs("tax-1500","tax-1200"))
        self.assertEqual(r.status,ExperimentStatus.OBSERVED_BEHAVIORAL_INFLUENCE)
        self.assertEqual(r.pair_count,2)

    def test_equal_outcomes_and_traces_means_no_observed_difference(self):
        self.assertEqual(self.analyze(self.complete_pairs()).status,
                         ExperimentStatus.NO_OBSERVED_DIFFERENCE)

    def test_trace_only_difference_is_not_semantic_influence(self):
        r=self.analyze(self.complete_pairs("same","same","path-A","path-B"))
        self.assertEqual(r.status,ExperimentStatus.INTERNAL_PATH_CHANGE_ONLY)

    def test_context_mismatch_is_inconclusive(self):
        rows=self.complete_pairs()
        rows[-1]=self.pair(1,RunSide.TREATMENT,context="other-context")
        self.assertEqual(self.analyze(rows).status,ExperimentStatus.INCONCLUSIVE)

    def test_multiple_changed_factors_are_rejected(self):
        rows=self.complete_pairs()
        rows[0]=self.pair(0,RunSide.BASELINE,changed=("tax_rate","region"))
        self.assertEqual(self.analyze(rows).status,ExperimentStatus.INCONCLUSIVE)

    def test_identical_input_digests_are_rejected(self):
        rows=self.complete_pairs()
        rows[1]=self.pair(0,RunSide.TREATMENT,input_digest="input-0")
        self.assertEqual(self.analyze(rows).status,ExperimentStatus.INCONCLUSIVE)

    def test_unstable_baseline_outcome_is_inconclusive(self):
        rows=self.complete_pairs()
        rows[2]=self.pair(1,RunSide.BASELINE,outcome="noise")
        self.assertEqual(self.analyze(rows).status,ExperimentStatus.INCONCLUSIVE)

    def test_missing_pair_side_is_inconclusive(self):
        self.assertEqual(self.analyze(self.complete_pairs()[:-1]).status,
                         ExperimentStatus.INCONCLUSIVE)

    def test_too_few_pairs_is_inconclusive(self):
        rows=[self.pair(0,RunSide.BASELINE),self.pair(0,RunSide.TREATMENT)]
        self.assertEqual(self.analyze(rows,min_pairs=2).status,ExperimentStatus.INCONCLUSIVE)

    def test_empty_runs_are_inconclusive(self):
        self.assertEqual(self.analyze([]).status,ExperimentStatus.INCONCLUSIVE)

    def test_duplicate_side_in_pair_is_inconclusive(self):
        rows=self.complete_pairs()
        rows.append(self.pair(0,RunSide.BASELINE))
        self.assertEqual(self.analyze(rows).status,ExperimentStatus.INCONCLUSIVE)

    def test_observation_model_mismatch_is_inconclusive(self):
        rows=self.complete_pairs()
        rows[-1]=self.pair(1,RunSide.TREATMENT,model="other-model")
        self.assertEqual(self.analyze(rows).status,ExperimentStatus.INCONCLUSIVE)

    def test_evidence_digest_changes_when_outcome_changes(self):
        a=self.analyze(self.complete_pairs())
        b=self.analyze(self.complete_pairs("base","different"))
        self.assertNotEqual(a.evidence_digest,b.evidence_digest)

if __name__=="__main__":
    unittest.main()
