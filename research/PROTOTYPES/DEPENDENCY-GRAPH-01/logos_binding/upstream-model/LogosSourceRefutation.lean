import LogosUpstreamProgram
import LogosModelExtension
import LogosWireValuation
import SourceWireRefutation
import Cpc.Spec

namespace LLMLang.LogosScalarDenotation

open LLMLang.LogosBinding (QuerySort)
open LLMLang.SourceQuerySemantics (Env Value)
open LLMLang.SourceSyntax (SourceScope VariableId)
open LLMLang.SourceCommandSemantics (Program)
open LLMLang.ProgramObservationSemantics (ObservationContract Observation)
open LLMLang.PairedObservationSemantics (PairedValuations observeConcretePair)
open LLMLang.ProgramRelationalQuery (RelationalQuery compileRelationalQuery)
open LLMLang.SourceQueryEnvelope (decodeSourceEnvelope)
open LLMLang.SourceWireRefutation (CheckedRefutation)
open Smtm

private theorem twoAssumptions_true (model : SmtModel) {assumptions : List Eo.Term}
    (each : assumptions.map (fun term => __smtx_model_eval model (__eo_to_smt term)) =
      [.Boolean true, .Boolean true]) :
    __smtx_model_eval model (__eo_to_smt (Eo.logos_assumption_term assumptions)) = .Boolean true := by
  cases assumptions with
  | nil => simp at each
  | cons first tail =>
      cases tail with
      | nil => simp at each
      | cons second rest =>
          cases rest with
          | cons _ _ => simp at each
          | nil =>
              simp only [List.map_cons, List.map_nil, List.cons.injEq, and_true] at each
              change __smtx_model_eval_and (__smtx_model_eval model (__eo_to_smt second))
                (__smtx_model_eval_and (__smtx_model_eval model (__eo_to_smt first)) (.Boolean true)) = _
              rw [each.1, each.2]
              rfl

private theorem falseInWellFormedModel (model : SmtModel) (wellFormed : model_wf model)
    {term : Eo.Term} (unsat : eo_satisfiability term false) :
    __smtx_model_eval model (__eo_to_smt term) = .Boolean false := by
  unfold eo_satisfiability at unsat
  cases unsat with
  | intro_false interpretsFalse => exact interpretsFalse model wellFormed

/-- A well-formed base and sound Logos verdict exclude dependence in every admitted source pair. -/
theorem checkedRefutation_noDependence {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query)
    {wire proof : String}
    (certified : CheckedRefutation (decodeSourceEnvelope program contract scope factor wire) proof)
    {initial : Env} {valuation : Valuation}
    (tableValidated : liftValuation certified.bound.bindings initial = .ok valuation)
    (base : SmtModel) (wellFormed : model_wf base)
    (soundVerdict : ∀ assumptions commands,
      Eo.logos_verdict assumptions commands = .correct →
        eo_satisfiability (Eo.logos_assumption_term assumptions) false)
    (pair : PairedValuations scope factor) :
    ∃ a b : Observation Value sort contract.fields,
      observeConcretePair program contract pair = some (a, b) ∧
      (pair.left query.selected.sourceName query.selected.sort ≠
        pair.right query.selected.sourceName query.selected.sort → a = b) := by
  obtain ⟨model, a, b, factorChanged, observationChanged, _, observed, ran, differs⟩ :=
    acceptedAssumptions_forConcretePair compiled certified.sourceQuery certified.bound pair tableValidated
  refine ⟨a, b, observed, fun differentInput => ?_⟩
  apply Classical.byContradiction
  intro differentObservation
  have both : factorChanged = true ∧ observationChanged = true := by
    simpa only [Bool.and_eq_true] using differs.mpr ⟨differentInput, differentObservation⟩
  let upstream := extendModel base model
  have agree := extendModel_agrees base model
  have interpreted := evaluationList_matches_upstream upstream agree ran
  rw [both.1, both.2] at interpreted
  have trueValue := twoAssumptions_true upstream interpreted
  have unsat := soundVerdict _ _ certified.verdict
  have falseValue := falseInWellFormedModel upstream (extendModel_wellFormed base wellFormed model) unsat
  rw [trueValue] at falseValue
  cases falseValue

#print axioms checkedRefutation_noDependence

end LLMLang.LogosScalarDenotation
