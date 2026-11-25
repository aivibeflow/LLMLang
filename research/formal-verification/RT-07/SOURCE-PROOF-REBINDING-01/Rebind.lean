import SourceWireRefutation

open Lean (Json toJson)
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.SourceQueryEnvelope
open LLMLang.SourceWireRefutation

private def input : Declaration := ⟨⟨1⟩, "input", .input, .int⟩
private def state : Declaration := ⟨⟨2⟩, "state", .state, .int⟩
private def unused : Declaration := ⟨⟨3⟩, "unused", .state, .int⟩
private def scopeFor (entries : List Declaration) : SourceScope :=
  ⟨⟨entries⟩, entries.map Declaration.id, entries.map Declaration.id⟩

private def emptyObservation : ObservationContract := ⟨[]⟩
private def constant : Program .int := ⟨.skip, .intLit 7⟩
private def baseScope : SourceScope := scopeFor [input]

private structure Test where
  label : String
  program : Program .int := constant
  scope : SourceScope := baseScope
  factor : VariableId := input.id
  observation : ObservationContract := emptyObservation

private def tests : List Test := [
  { label := "base" },
  { label := "sequence_of_two_skips", program := ⟨.seq .skip .skip, .intLit 7⟩ },
  { label := "renamed_factor", scope := scopeFor [{ input with sourceName := "renamed" }] },
  { label := "unused_hidden_declaration",
    scope := { baseScope with context := ⟨[input, unused]⟩ } },
  { label := "unused_visible_state", scope := scopeFor [input, state] },
  { label := "observed_state", scope := scopeFor [input, state],
    observation := ⟨[⟨state.id, state.sort⟩]⟩ },
  { label := "different_constant_return", program := ⟨.skip, .intLit 8⟩ },
  { label := "dependent_return", program := ⟨.skip, .intVar "input"⟩ },
  { label := "new_factor_identity", scope := scopeFor [{ input with id := ⟨8⟩ }], factor := ⟨8⟩ },
  { label := "factor_role_changed", scope := scopeFor [{ input with role := .state }] },
  { label := "factor_uninitialized", scope := { baseScope with initialized := [] } },
  { label := "ambiguous_duplicate_name", scope := scopeFor [input, { state with sourceName := "input" }] }
]

private def outcome (result : Except RefutationError Unit) : String :=
  match result with
  | .ok () => "admitted"
  | .error (.sourceOrWire _) => "source-or-wire"
  | .error (.assumptions _) => "assumptions"
  | .error (.checker _) => "checker"
  | .error .incomplete => "incomplete"
  | .error .incorrect => "incorrect"

private def fixtureRebind (label proof : String) : Option String :=
  match label with
  | "different_constant_return" => some (proof.replace " 7 " " 8 ")
  | "new_factor_identity" => some ((proof.replace "i_4_L" "i_25_L").replace "i_5_R" "i_26_R")
  | "unused_visible_state" =>
      some (proof.replace "(declare-const i_5_R Int)\n"
        "(declare-const i_5_R Int)\n(declare-const i_6 Int)\n")
  | _ => none

private def row (baseWire proof : String) (test : Test) : Json :=
  let fresh := sourceEnvelope test.program test.observation test.scope test.factor
  let oldWireCheck := check test.program test.observation test.scope test.factor baseWire proof
  let (newWire, newWireCheck) := match fresh with
    | .error reason => (Json.null, "source-unavailable: " ++ reason)
    | .ok wire => (toJson wire, outcome (check test.program test.observation test.scope test.factor wire proof))
  let reboundCheck := match fresh, fixtureRebind test.label proof with
    | .ok wire, some rebound =>
        toJson (outcome (check test.program test.observation test.scope test.factor wire rebound))
    | _, _ => Json.null
  Json.mkObj [("name", toJson test.label), ("fresh_wire", newWire), ("rebound_proof_check", reboundCheck),
    ("old_wire_check", toJson (outcome oldWireCheck)), ("fresh_wire_check", toJson newWireCheck)]

def main : IO Unit := do
  let proof ← IO.FS.readFile "proof.cpc"
  match sourceEnvelope constant emptyObservation baseScope input.id with
  | .error reason => throw (IO.userError reason)
  | .ok wire => for test in tests do
    IO.println (row wire proof test).compress

#print axioms LLMLang.SourceWireRefutation.check_exact
#print axioms LLMLang.SourceQueryEnvelope.decodeSourceEnvelope_typed
