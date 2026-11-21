import SolverRelationalQuery
import LLMLangLogosBinding
import Cpc.Api

namespace LLMLang.SourceCpcRefutation

open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.ProgramRelationalQuery
open LLMLang.CanonicalQuerySymbols
open LLMLang.LogosBinding

/-- Check the complete CPC assumption list against the formula compiled from typed source. -/
def checkSourceAssumptions {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (proof : String) : Except String (List Eo.Term × Eo.CCmdList) := do
  let some query := compileRelationalQuery program contract scope factor
    | throw "source program, observation contract or factor is not admitted"
  let lowered := query.lower
  let .and [differentInput, differentObservations] := lowered.formula
    | throw "source formula must contain two ordered assumptions"
  let (assumptions, commands, parserState) ← parseProofWithState proof
  let bindings ← bindExpectedDeclarations parserState
    (lowered.declarations.map fun decl => ⟨decl.name, decl.sort.expected⟩)
  let expected ← renderRelationalAssumptions bindings query.selected.sort
    (bindingOnSide query.selected factor .left).name
    (bindingOnSide query.selected factor .right).name
    differentInput differentObservations
  if assumptions = expected then
    pure (assumptions, commands)
  else
    throw "CPC assumptions differ from the checked source formula"

/-- Reject an unbound, incorrect, or incomplete CPC result. -/
def checkSourceRefutation {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (proof : String) : Except String Unit := do
  let (assumptions, commands) ← checkSourceAssumptions program contract scope factor proof
  if Eo.logos_verdict assumptions commands != .correct then
    throw "Logos did not accept a complete refutation"

end LLMLang.SourceCpcRefutation
