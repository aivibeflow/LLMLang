import SourceQueryEnvelope
import Cpc.Api

namespace LLMLang.SourceWireRefutation

open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.SourceQueryEnvelope
open LLMLang.LogosBinding

inductive RefutationError where
  | sourceOrWire (reason : String)
  | assumptions (reason : String)
  | checker (reason : String)
  | incomplete
  | incorrect
  deriving Repr

/-- Require source-owned bytes, exact CPC assumptions, and a complete Logos verdict. -/
def check {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (wire proof : String) : Except RefutationError Unit := do
  let _ ← (decodeSourceEnvelope program contract scope factor wire).mapError .sourceOrWire
  (checkCanonicalQueryAssumptions proof wire).mapError .assumptions
  let verdict ← (Eo.logos_check_proof proof).mapError .checker
  match verdict with
  | .correct => pure ()
  | .incomplete => throw .incomplete
  | .incorrect => throw .incorrect

end LLMLang.SourceWireRefutation