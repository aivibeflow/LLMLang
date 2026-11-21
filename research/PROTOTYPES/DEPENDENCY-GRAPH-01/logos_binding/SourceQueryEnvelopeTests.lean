import SourceQueryEnvelope

open Lean (Json toJson)
open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.SourceQueryEnvelope
open LLMLang.LogosBinding (decodeCanonicalRelationalQuery)

private def x : Declaration := ⟨⟨1⟩, "i_6", .input, .int⟩
private def shared : Declaration := ⟨⟨2⟩, "other", .input, .int⟩
private def flag : Declaration := ⟨⟨3⟩, "flag", .input, .bool⟩
private def counter : Declaration := ⟨⟨4⟩, "counter", .state, .int⟩

private def scope : SourceScope :=
  ⟨⟨[x, shared, flag, counter]⟩, [x.id, shared.id, flag.id, counter.id],
    [x.id, shared.id, flag.id, counter.id]⟩

private def intProgram : Program .int :=
  ⟨.branch (.boolVar "flag")
      (.assign (.state counter.id) (.mulConst (-3) (.intVar "i_6")))
      (.assign (.state counter.id) (.neg (.intVar "other"))),
    .intVar "counter"⟩

private def boolProgram : Program .bool :=
  ⟨.assign (.state counter.id) (.intVar "i_6"), .boolVar "flag"⟩

private def contract : ObservationContract := ⟨[⟨counter.id, .int⟩]⟩

private def replaceField (text key : String) (value : Json) : Except String String := do
  let entries ← (← Json.parse text).getObj?
  pure (Json.mkObj (entries.toList.map fun (name, old) =>
    (name, if name == key then value else old))).compress

private def check : Except String Unit := do
  let intEnvelope ← sourceEnvelope intProgram contract scope x.id
  let intQuery ← decodeSourceEnvelope intProgram contract scope x.id intEnvelope
  if intQuery.factorLeft != "i_4_L" || intQuery.factorRight != "i_5_R" ||
      intQuery.declarations.map (·.name) != ["i_4_L", "i_5_R", "i_6", "i_9", "i_12"] then
    throw "selected pair or shared declarations not preserved"
  let boolEnvelope ← sourceEnvelope boolProgram contract scope flag.id
  let boolQuery ← decodeSourceEnvelope boolProgram contract scope flag.id boolEnvelope
  if boolQuery.factorLeft != "i_10_L" || boolQuery.factorRight != "i_11_R" then
    throw "selected Bool pair not preserved"
  for (field, replacement) in [
      ("observations_differ", Json.mkObj [("op", toJson "bool"), ("sort", toJson "Bool"),
        ("args", .arr #[]), ("atom", toJson false)]),
      ("factor_left", toJson "i_6_L"),
      ("observation_contract", toJson "other_contract")] do
    let modified ← replaceField intEnvelope field replacement
    let _ ← decodeCanonicalRelationalQuery modified
    if (decodeSourceEnvelope intProgram contract scope x.id modified).isOk then
      throw s!"a changed {field} unexpectedly passed"
  if (decodeSourceEnvelope intProgram contract scope x.id (intEnvelope ++ "\n")).isOk then
    throw "noncanonical whitespace unexpectedly passed"
  if (decodeSourceEnvelope intProgram ⟨[]⟩ scope x.id intEnvelope).isOk then
    throw "envelope replayed under a different contract"
  if (decodeSourceEnvelope intProgram contract scope shared.id intEnvelope).isOk then
    throw "envelope replayed for a different factor"
  if (sourceEnvelope intProgram contract scope counter.id).isOk then
    throw "a state slot selected as a factor unexpectedly passed"
  pure ()

def main : IO Unit :=
  match check with
  | .ok () => IO.println "Source query envelope controls passed"
  | .error reason => throw (IO.userError reason)
