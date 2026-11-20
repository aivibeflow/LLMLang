import ProgramRelationalQuery
import LogosQueryAdapter

namespace LLMLang.ProgramRelationalQuery

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.LogosQueryAdapter

theorem RelationalQuery.qfLia {scope : SourceScope} {factor : VariableId}
    (query : RelationalQuery scope factor) :
    (toLogosQueryTerm query.formula).isQfLia = true :=
  toLogosQueryTerm_qfLia query.formula

/-- SC-7 gives a QF_LIA formula for each admitted program, contract and factor. -/
theorem compileRelationalQuery_qfLia {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope exit : SourceScope} {factor : VariableId}
    (checked : checkObservedProgram program contract scope = some exit)
    (selected : (resolveInputFactor scope factor).isSome = true) :
    ∃ query, compileRelationalQuery program contract scope factor = some query ∧
      (toLogosQueryTerm query.formula).isQfLia = true := by
  obtain ⟨query, compiled⟩ := compileRelationalQuery_exists checked selected
  exact ⟨query, compiled, query.qfLia⟩

end LLMLang.ProgramRelationalQuery
