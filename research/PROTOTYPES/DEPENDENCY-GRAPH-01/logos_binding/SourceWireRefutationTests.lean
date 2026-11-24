import SourceWireRefutation

open Lean (Json toJson)
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.SourceQueryEnvelope
open LLMLang.SourceWireRefutation
open LLMLang.LogosBinding (checkCanonicalQueryAssumptions)

private def inputVar : Declaration := ⟨⟨1⟩, "input", .input, .int⟩
private def scope : SourceScope := ⟨⟨[inputVar]⟩, [inputVar.id], [inputVar.id]⟩
private def contract : ObservationContract := ⟨[]⟩
private def constant : Program .int := ⟨.skip, .intLit 7⟩
private def dependent : Program .int := ⟨.skip, .intVar "input"⟩

private def observations := "(or (not (= (ite true 7 0) (ite true 7 0))) false)"
private def declarations := "(declare-const i_4_L Int)\n(declare-const i_5_R Int)\n"
private def factorAssumption := "(assume @p1 (not (= i_4_L i_5_R)))\n"
private def observationAssumption := s!"(assume @p2 {observations})\n"
private def header := declarations ++ factorAssumption
private def assumptions := header ++ observationAssumption
private def proof := assumptions ++ s!"(step @p3 :rule evaluate :args ({observations}))\n" ++
  "(step @p4 false :rule eq_resolve :premises (@p2 @p3))\n"
private def wrongProof := header ++ "(assume @p2 false)\n" ++
  "(step @p3 (= false false) :rule refl :args (false))\n" ++
  "(step @p4 false :rule eq_resolve :premises (@p2 @p3))\n"

private def changedEnvelope (text : String) : Except String String := do
  let entries ← (← Json.parse text).getObj?
  let constantFalse := Json.mkObj [("op", toJson "bool"), ("sort", toJson "Bool"),
    ("args", .arr #[]), ("atom", toJson false)]
  pure (Json.mkObj (entries.toList.map fun (name, value) =>
    (name, if name == "observations_differ" then constantFalse else value))).compress

private def run : Except String Unit := do
  let wire ← sourceEnvelope constant contract scope inputVar.id
  let checkGate := check constant contract scope inputVar.id
  (checkGate wire proof).mapError (fun error => reprStr error)
  let checked ← (checkWithEvidence constant contract scope inputVar.id wire proof).mapError reprStr
  if checked.bound.parsed.assumptions.length != 2 then
    throw "the checked command stream did not bind both input and observation assumptions"
  for modified in [declarations ++ observationAssumption ++ factorAssumption,
      header, assumptions ++ "(assume @p5 true)\n"] do
    match checkGate wire modified with
    | .error (.assumptions _) => pure ()
    | other => throw s!"expected exact ordered assumption rejection, got {reprStr other}"
  match checkGate wire assumptions with
  | .error .incorrect => pure ()
  | other => throw s!"expected incorrect derivation, got {reprStr other}"

  let fake ← changedEnvelope wire
  checkCanonicalQueryAssumptions wrongProof fake
  let verdict ← Eo.logos_check_proof wrongProof
  if verdict != .correct then
    throw "substitution control must have a valid proof of its own assumptions"
  match checkGate fake wrongProof with
  | .error (.sourceOrWire _) => pure ()
  | other => throw s!"expected source wire rejection, got {reprStr other}"
  match checkGate wire wrongProof with
  | .error (.assumptions _) => pure ()
  | other => throw s!"expected CPC assumption mismatch, got {reprStr other}"
  let changedSource ← sourceEnvelope dependent contract scope inputVar.id
  match check dependent contract scope inputVar.id changedSource proof with
  | .error (.assumptions _) => pure ()
  | other => throw s!"expected proof to fail on changed source formula, got {reprStr other}"

def main : IO Unit :=
  match run with
  | .ok () => IO.println "Source-to-wire-to-Logos refutation controls passed"
  | .error error => throw (IO.userError error)