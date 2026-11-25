import SourceWireRefutation

open Lean (Json toJson)
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.SourceQueryEnvelope
open LLMLang.SourceWireRefutation

private def input : Declaration := ⟨⟨1⟩, "input", .input, .int⟩
private def scope : SourceScope := ⟨⟨[input]⟩, [input.id], [input.id]⟩

private def outcome (check : Except RefutationError Unit) : String :=
  match check with
  | .ok () => "runtime-cpc-accepted"
  | .error (.sourceOrWire _) => "source-or-wire"
  | .error (.assumptions _) => "assumptions"
  | .error (.checker _) => "checker"
  | .error .incomplete => "incomplete"
  | .error .incorrect => "incorrect"

def main : IO Unit := do
  let seven ← IO.FS.readFile "proof7.cpc"
  let eight ← IO.FS.readFile "proof8.cpc"
  for value in ([7, 8] : List Int) do
    let program : Program .int := ⟨.skip, .intLit value⟩
    let observation : ObservationContract := ⟨[]⟩
    match sourceEnvelope program observation scope input.id with
    | .error reason => throw (IO.userError reason)
    | .ok wire =>
        let checkArtifact := check program observation scope input.id wire
        IO.println (Json.mkObj [("literal", toJson value), ("wire", toJson wire),
          ("seven", toJson (outcome (checkArtifact seven))),
          ("eight", toJson (outcome (checkArtifact eight)))]).compress
