import unittest
from src.multifactor_analysis import (
    CellSide, FactorialCellRun, MultiFactorError, MultiFactorRun,
    MultiFactorStatus, analyze_joint_intervention, analyze_pairwise_interaction, assignment,
)

class MultiFactorAnalysisTests(unittest.TestCase):
    def joint_rows(self, base_value, treatment_value, base_trace="t0", treatment_trace="t1",
                   treatment=("gold", True), baseline=("standard", False), count=2):
        rows=[]; base=assignment({"tier":baseline[0],"discount":baseline[1]})
        treat=assignment({"tier":treatment[0],"discount":treatment[1]})
        for i in range(count):
            for side,value,trace,digest in (
                (CellSide.BASELINE,base_value,base_trace,"in-base"),
                (CellSide.TREATMENT,treatment_value,treatment_trace,"in-treat")):
                rows.append(MultiFactorRun("artifact","ctx","obs",base,treat,side,i,digest,value,trace,f"run-{i}-{side}"))
        return base,treat,rows
    def test_joint_multi_factor_effect_is_detected(self):
        b,t,rows=self.joint_rows(100,80); r=analyze_joint_intervention("artifact","ctx","obs",dict(b),dict(t),rows)
        self.assertEqual(r.status,MultiFactorStatus.OBSERVED_BEHAVIORAL_INFLUENCE); self.assertEqual(r.changed_factors,("discount","tier"))
    def test_joint_no_observed_difference_is_scoped(self):
        b,t,rows=self.joint_rows(100,100,"same","same"); r=analyze_joint_intervention("artifact","ctx","obs",dict(b),dict(t),rows)
        self.assertEqual(r.status,MultiFactorStatus.NO_OBSERVED_DIFFERENCE)
    def test_joint_trace_only_change_is_not_behavioral_influence(self):
        b,t,rows=self.joint_rows(100,100,"path-A","path-B"); r=analyze_joint_intervention("artifact","ctx","obs",dict(b),dict(t),rows)
        self.assertEqual(r.status,MultiFactorStatus.INTERNAL_PATH_CHANGE_ONLY)
    def test_joint_rejects_incomplete_pairs(self):
        b,t,rows=self.joint_rows(1,2); self.assertEqual(analyze_joint_intervention("artifact","ctx","obs",dict(b),dict(t),rows[:-1]).status,MultiFactorStatus.INCONCLUSIVE)
    def test_joint_rejects_context_mismatch(self):
        b,t,rows=self.joint_rows(1,2); rows[0]=MultiFactorRun("artifact","other","obs",b,t,CellSide.BASELINE,0,"i",1,"t","r")
        self.assertEqual(analyze_joint_intervention("artifact","ctx","obs",dict(b),dict(t),rows).status,MultiFactorStatus.INCONCLUSIVE)
    def test_joint_rejects_duplicate_pair_side(self):
        b,t,rows=self.joint_rows(1,2); rows.append(rows[0])
        self.assertEqual(analyze_joint_intervention("artifact","ctx","obs",dict(b),dict(t),rows).status,MultiFactorStatus.INCONCLUSIVE)
    def factorial(self,outcomes,count=2):
        rows=[]
        for p in range(count):
            for i,j in ((0,0),(1,0),(0,1),(1,1)):
                rows.append(FactorialCellRun("artifact","ctx","obs","tier","discount",
                    ("standard","gold")[i],(False,True)[j],assignment({"region":"UK"}),p,
                    f"input-{i}-{j}",outcomes[(i,j)],f"trace-{i}-{j}",f"run-{p}-{i}-{j}"))
        return rows
    def analyze(self,outcomes,rows=None):
        return analyze_pairwise_interaction("artifact","ctx","obs","tier",("standard","gold"),
            "discount",(False,True),{"region":"UK"},rows if rows is not None else self.factorial(outcomes))
    def test_hidden_conditional_interaction_when_neither_factor_acts_alone(self):
        r=self.analyze({(0,0):100,(1,0):100,(0,1):100,(1,1):80})
        self.assertEqual(r.status,MultiFactorStatus.OBSERVED_INTERACTION); self.assertFalse(r.simple_effect_a_when_b0)
        self.assertTrue(r.simple_effect_a_when_b1); self.assertEqual(r.numeric_interaction_contrast,"-20")
    def test_additive_numeric_effects_have_zero_interaction_contrast(self):
        r=self.analyze({(0,0):0,(1,0):5,(0,1):7,(1,1):12})
        self.assertEqual(r.status,MultiFactorStatus.NO_INTERACTION_OBSERVED); self.assertEqual(r.numeric_interaction_contrast,"0")
    def test_numeric_interaction_detected_with_main_effects(self):
        r=self.analyze({(0,0):0,(1,0):5,(0,1):7,(1,1):20})
        self.assertEqual(r.status,MultiFactorStatus.OBSERVED_INTERACTION); self.assertEqual(r.numeric_interaction_contrast,"8")
    def test_categorical_conditional_effect_detected(self):
        r=self.analyze({(0,0):"base",(1,0):"base",(0,1):"base",(1,1):"changed"})
        self.assertEqual(r.status,MultiFactorStatus.OBSERVED_INTERACTION)
    def test_factorial_requires_all_four_cells(self):
        rows=self.factorial({(0,0):0,(1,0):1,(0,1):1,(1,1):2})[:-1]
        self.assertEqual(self.analyze({},rows).status,MultiFactorStatus.INCONCLUSIVE)
    def test_factorial_rejects_context_drift(self):
        rows=self.factorial({(0,0):0,(1,0):1,(0,1):1,(1,1):3}); x=rows[-1]
        rows[-1]=FactorialCellRun(x.artifact_hash,"other",x.observation_model_digest,x.factor_a,x.factor_b,
            x.level_a,x.level_b,x.context_assignment,x.pair_index,x.input_digest,x.observable_value,x.trace_digest,x.run_digest)
        self.assertEqual(self.analyze({},rows).status,MultiFactorStatus.INCONCLUSIVE)
    def test_factorial_rejects_unstable_cell_outcome(self):
        rows=self.factorial({(0,0):0,(1,0):1,(0,1):1,(1,1):3}); x=rows[-1]
        rows[-1]=FactorialCellRun(x.artifact_hash,x.context_digest,x.observation_model_digest,x.factor_a,x.factor_b,
            x.level_a,x.level_b,x.context_assignment,x.pair_index,x.input_digest,999,x.trace_digest,x.run_digest)
        self.assertEqual(self.analyze({},rows).status,MultiFactorStatus.INCONCLUSIVE)
    def test_factorial_rejects_duplicate_cell(self):
        rows=self.factorial({(0,0):0,(1,0):1,(0,1):1,(1,1):3}); rows.append(rows[0])
        self.assertEqual(self.analyze({},rows).status,MultiFactorStatus.INCONCLUSIVE)
    def test_categorical_all_equal_outcomes_have_no_observed_effect(self):
        r=self.analyze({(0,0):"same",(1,0):"same",(0,1):"same",(1,1):"same"})
        self.assertEqual(r.status,MultiFactorStatus.NO_INTERACTION_OBSERVED)
    def test_categorical_all_distinct_outcomes_are_inconclusive(self):
        r=self.analyze({(0,0):"a",(1,0):"b",(0,1):"c",(1,1):"d"})
        self.assertEqual(r.status,MultiFactorStatus.INCONCLUSIVE)
    def test_evidence_digest_binds_observable_values(self):
        a=self.analyze({(0,0):0,(1,0):1,(0,1):1,(1,1):3}); b=self.analyze({(0,0):0,(1,0):1,(0,1):1,(1,1):4})
        self.assertNotEqual(a.evidence_digest,b.evidence_digest)
    def test_assignment_rejects_unsorted_and_empty_names(self):
        with self.assertRaises(MultiFactorError): assignment({"":1})
        with self.assertRaises(MultiFactorError):
            MultiFactorRun("a","c","o",(("b",0),("a",0)),(("a",1),("b",1)),CellSide.BASELINE,0,"i",1,"t","r")
if __name__=="__main__": unittest.main()
