import Lean
import Cpc.ApiCorrect
import LogosSourceRefutation

open Lean Elab Command

elab "#verdict_axioms " subject:ident : command => do
  let name ← liftCoreM <| resolveGlobalConstNoOverloadCore subject.getId
  let axioms ← Lean.collectAxioms name
  let names := axioms.toList.map Name.toString |>.mergeSort
  let report := Json.mkObj [("name", toJson name.toString), ("axioms", toJson names)]
  logInfo report.compress

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

/-- Replace the abstract soundness premise by the actual pinned upstream verdict theorem. -/
theorem pinnedVerdict_noDependence_withBase {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query)
    {wire proof : String}
    (certified : CheckedRefutation (decodeSourceEnvelope program contract scope factor wire) proof)
    {initial : Env} {valuation : Valuation}
    (tableValidated : liftValuation certified.bound.bindings initial = .ok valuation)
    (base : SmtModel) (wellFormed : model_wf base)
    (pair : PairedValuations scope factor) :
    ∃ a b : Observation Value sort contract.fields,
      observeConcretePair program contract pair = some (a, b) ∧
      (pair.left query.selected.sourceName query.selected.sort ≠
        pair.right query.selected.sourceName query.selected.sort → a = b) :=
  checkedRefutation_noDependence compiled certified tableValidated base wellFormed
    correct___logos_verdict pair

/-- Use the clean pinned dependency's published model existence proof. -/
theorem pinnedVerdict_noDependence {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query)
    {wire proof : String}
    (certified : CheckedRefutation (decodeSourceEnvelope program contract scope factor wire) proof)
    {initial : Env} {valuation : Valuation}
    (tableValidated : liftValuation certified.bound.bindings initial = .ok valuation)
    (pair : PairedValuations scope factor) :
    ∃ a b : Observation Value sort contract.fields,
      observeConcretePair program contract pair = some (a, b) ∧
      (pair.left query.selected.sourceName query.selected.sort ≠
        pair.right query.selected.sourceName query.selected.sort → a = b) := by
  obtain ⟨base, wellFormed⟩ := model_wf_nonvacuous
  exact pinnedVerdict_noDependence_withBase compiled certified tableValidated base wellFormed pair

#verdict_axioms correct___logos_verdict
#verdict_axioms correct___logos_check_proof
#verdict_axioms model_wf_nonvacuous
#verdict_axioms pinnedVerdict_noDependence_withBase
#verdict_axioms pinnedVerdict_noDependence

end LLMLang.LogosScalarDenotation
