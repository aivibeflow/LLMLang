import LogosProgramBridge
import LogosUpstreamScalarModel

namespace LLMLang.LogosScalarDenotation

open LLMLang.LogosBinding (QuerySort DecodedRelationalQuery CheckedQueryAssumptions)
open LLMLang.SourceQuerySemantics (Env Value)
open LLMLang.SourceSyntax (SourceScope VariableId)
open LLMLang.SourceCommandSemantics (Program)
open LLMLang.ProgramObservationSemantics (ObservationContract Observation)
open LLMLang.PairedObservationSemantics (observeConcretePair)
open LLMLang.ProgramRelationalQuery (RelationalQuery compileRelationalQuery)
open LLMLang.SourceQueryEnvelope (decodeSourceEnvelope wireNames)
open Smtm

private theorem evaluateList (upstream : SmtModel) {valuation : Valuation}
    (related : modelAgrees upstream valuation) {terms : List Eo.Term} {values : List Scalar}
    (ran : terms.mapM (fun term => evalSmt valuation (__eo_to_smt term)) = .ok values) :
    terms.map (fun term => __smtx_model_eval upstream (__eo_to_smt term)) = values.map Scalar.embed := by
  induction terms generalizing values with
  | nil =>
      change Except.ok [] = Except.ok values at ran
      cases ran
      rfl
  | cons head tail ih =>
      rw [List.mapM_cons] at ran
      cases first : evalSmt valuation (__eo_to_smt head) with
      | error _ =>
          rw [first] at ran
          cases ran
      | ok value =>
          rw [first] at ran
          cases rest : tail.mapM (fun term => evalSmt valuation (__eo_to_smt term)) with
          | error _ =>
              rw [rest] at ran
              cases ran
          | ok remainder =>
              rw [rest] at ran
              change Except.ok (value :: remainder) = Except.ok values at ran
              cases ran
              rw [List.map_cons, List.map_cons,
                evaluation_matches_upstream upstream valuation related (__eo_to_smt head) first, ih rest]

/-- The pinned upstream model interprets the exact ordered CPC assumptions of an admitted program. -/
theorem acceptedAssumptions_upstreamSourcePair {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {wire proof : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor wire = .ok decoded)
    (bound : CheckedQueryAssumptions proof decoded) (env : Env)
    {valuation : Valuation} (lifted : liftValuation bound.bindings env = .ok valuation)
    (upstream : SmtModel) (related : modelAgrees upstream valuation) :
    ∃ (query : RelationalQuery scope factor) (a b : Observation Value sort contract.fields)
      (factorChanged observationChanged : Bool),
      compileRelationalQuery program contract scope factor = some query ∧
      let pair := query.inputPair (QuerySymbolRenaming.pullback (wireNames query.lower.bindings) env)
      observeConcretePair program contract pair = some (a, b) ∧
      bound.parsed.assumptions.map (fun term => __smtx_model_eval upstream (__eo_to_smt term)) =
        [.Boolean factorChanged, .Boolean observationChanged] ∧
      ((factorChanged && observationChanged) = true ↔
        pair.left query.selected.sourceName query.selected.sort ≠
          pair.right query.selected.sourceName query.selected.sort ∧ a ≠ b) := by
  obtain ⟨query, a, b, factorChanged, observationChanged, compiled, observed, ran, different⟩ :=
    acceptedAssumptions_sourcePair accepted bound env lifted
  exact ⟨query, a, b, factorChanged, observationChanged, compiled, observed,
    evaluateList upstream related ran, different⟩

#print axioms acceptedAssumptions_upstreamSourcePair

end LLMLang.LogosScalarDenotation
