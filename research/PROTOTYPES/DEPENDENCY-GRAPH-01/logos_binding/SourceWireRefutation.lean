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

/-- The accepted source query, exact CPC bindings and verdict of the ordinary parser's commands. -/
structure CheckedRefutation (source : Except String DecodedRelationalQuery) (proof : String) where
  query : DecodedRelationalQuery
  sourceQuery : source = .ok query
  bound : CheckedQueryAssumptions proof query
  verdict : Eo.logos_verdict bound.parsed.assumptions bound.parsed.commands = .correct

private def checkDecodedRefutation
    (source : Except String DecodedRelationalQuery) (proof : String) :
    Except RefutationError (CheckedRefutation source proof) :=
  match source with
  | .error reason => .error (.sourceOrWire reason)
  | .ok query => do
    let bound ← (checkQueryAssumptions proof query).mapError .assumptions
    match verdict : Eo.logos_verdict bound.parsed.assumptions bound.parsed.commands with
    | .correct => pure ⟨query, rfl, bound, verdict⟩
    | .incomplete => throw .incomplete
    | .incorrect => throw .incorrect

def checkWithEvidence {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (wire proof : String) :
    Except RefutationError
      (CheckedRefutation (decodeSourceEnvelope program contract scope factor wire) proof) :=
  checkDecodedRefutation (decodeSourceEnvelope program contract scope factor wire) proof

/-- Require source-owned bytes, exact CPC assumptions, and a complete Logos verdict. -/
def check {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (wire proof : String) : Except RefutationError Unit :=
  (checkWithEvidence program contract scope factor wire proof).map (fun _ => ())

/-- The checked command stream is exactly the stream used by the ordinary Logos entry point. -/
theorem CheckedRefutation.ordinaryVerdict {source : Except String DecodedRelationalQuery}
    {proof : String} (certificate : CheckedRefutation source proof) :
    Eo.logos_check_proof proof = .ok .correct := by
  unfold Eo.logos_check_proof
  rw [certificate.bound.parsed.ordinary]
  change Except.ok (Eo.logos_verdict certificate.bound.parsed.assumptions
    certificate.bound.parsed.commands) = .ok .correct
  rw [certificate.verdict]

/-- A successful public check exposes both the source query and exact assumption-binding witness. -/
theorem check_exact {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {wire proof : String} (accepted : check program contract scope factor wire proof = .ok ()) :
    ∃ (query : DecodedRelationalQuery) (_ : CheckedQueryAssumptions proof query),
      decodeSourceEnvelope program contract scope factor wire = .ok query ∧
      sourceEnvelope program contract scope factor = .ok wire ∧
      Eo.logos_check_proof proof = .ok .correct := by
  unfold check at accepted
  cases h : checkWithEvidence program contract scope factor wire proof with
  | error reason => simp [h, Except.map] at accepted
  | ok certificate =>
      exact ⟨certificate.query, certificate.bound, certificate.sourceQuery,
        decodeSourceEnvelope_matches certificate.sourceQuery, certificate.ordinaryVerdict⟩

end LLMLang.SourceWireRefutation
