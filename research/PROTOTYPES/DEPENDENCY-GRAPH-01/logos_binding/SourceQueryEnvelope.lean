import SolverRelationalQuery
import LLMLangLogosBinding

open Lean

namespace LLMLang.SourceQueryEnvelope

open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.CanonicalQuerySymbols
open LLMLang.ProgramRelationalQuery
open LLMLang.LogosBinding

private def sortName : QuerySort → String
  | .int => "Int"
  | .bool => "Bool"

private def node (sort : QuerySort) (op : String) (args : List Json := [])
    (atom : Json := .null) : Json :=
  Json.mkObj [("op", toJson op), ("sort", toJson (sortName sort)),
    ("args", toJson args), ("atom", atom)]

/-- The pair names satisfy the /2 suffix convention without using source spellings. -/
private def wireName (binding : SymbolBinding) : String :=
  binding.name ++ match binding.role with
    | .shared => ""
    | .left => "_L"
    | .right => "_R"

private def rename (bindings : List SymbolBinding) (name : String) : Except String String :=
  match bindings.find? (fun binding => binding.name == name) with
  | some binding => .ok (wireName binding)
  | none => .error s!"missing source binding for {name}"

mutual
  private def encode (bindings : List SymbolBinding) :
      {sort : QuerySort} → QueryTerm sort → Except String Json
    | _, .intLit n => pure (node .int "int" [] (toJson n))
    | _, .boolLit b => pure (node .bool "bool" [] (toJson b))
    | _, .intSymbol name => do
        pure (node .int "symbol" [] (toJson (← rename bindings name)))
    | _, .boolSymbol name => do
        pure (node .bool "symbol" [] (toJson (← rename bindings name)))
    | _, .neg x => do pure (node .int "neg" [← encode bindings x])
    | _, .not x => do pure (node .bool "not" [← encode bindings x])
    | _, .add a b => do pure (node .int "add" [← encode bindings a, ← encode bindings b])
    | _, .sub a b => do pure (node .int "sub" [← encode bindings a, ← encode bindings b])
    | _, .mul a b => do pure (node .int "mul" [← encode bindings a, ← encode bindings b])
    | _, .eqInt a b => do pure (node .bool "eq" [← encode bindings a, ← encode bindings b])
    | _, .eqBool a b => do pure (node .bool "eq" [← encode bindings a, ← encode bindings b])
    | _, .lt a b => do pure (node .bool "lt" [← encode bindings a, ← encode bindings b])
    | _, .le a b => do pure (node .bool "le" [← encode bindings a, ← encode bindings b])
    | _, .and terms => do pure (node .bool "and" (← encodeList bindings terms))
    | _, .or terms => do pure (node .bool "or" (← encodeList bindings terms))
    | _, .iteInt c a b => do
        pure (node .int "ite" [← encode bindings c, ← encode bindings a, ← encode bindings b])
    | _, .iteBool c a b => do
        pure (node .bool "ite" [← encode bindings c, ← encode bindings a, ← encode bindings b])

  private def encodeList (bindings : List SymbolBinding) :
      List (QueryTerm .bool) → Except String (List Json)
    | [] => pure []
    | term :: tail => do pure ((← encode bindings term) :: (← encodeList bindings tail))
end

private def declarationJson (binding : SymbolBinding) : Json :=
  Json.mkObj [("name", toJson (wireName binding)), ("sort", toJson (sortName binding.declaration.sort))]

private def contractName (sort : QuerySort) (contract : ObservationContract) : String :=
  (Json.mkObj [("returned", toJson (sortName sort)), ("state", toJson (contract.fields.map
    (fun field => Json.mkObj [("id", toJson field.id.value), ("sort", toJson (sortName field.sort))])))]).compress

/-- Construct the /2 envelope from the checked source program, contract and selected input. -/
def sourceEnvelope {sort : QuerySort} (program : Program sort) (contract : ObservationContract)
    (scope : SourceScope) (factor : VariableId) : Except String String := do
  let some query := compileRelationalQuery program contract scope factor
    | throw "source program, contract or factor is not admitted"
  let lowered := query.lower
  let .and [factorTerm, observationTerm] := lowered.formula
    | throw "source formula must contain two ordered assumptions"
  let left := wireName (bindingOnSide query.selected factor .left)
  let right := wireName (bindingOnSide query.selected factor .right)
  pure (Json.mkObj [
    ("schema", toJson "llmlang.qf_lia.relational-query/2"),
    ("factor", toJson ("f_" ++ Nat.repr factor.value)),
    ("factor_left", toJson left), ("factor_right", toJson right),
    ("declarations", toJson (lowered.bindings.map declarationJson)),
    ("factor_difference", ← encode lowered.bindings factorTerm),
    ("observations_differ", ← encode lowered.bindings observationTerm),
    ("observation_contract", toJson (contractName sort contract))]).compress

private def decodeExact (expected : Except String String) (actual : String) :
    Except String DecodedRelationalQuery :=
  match expected with
  | .error reason => .error reason
  | .ok canonical =>
      if canonical = actual then decodeCanonicalRelationalQuery actual
      else .error "wire bytes differ from the canonical source envelope"

def decodeSourceEnvelope {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (actual : String) : Except String DecodedRelationalQuery :=
  decodeExact (sourceEnvelope program contract scope factor) actual

/-- Any successful decode consumed exactly the bytes generated from these source inputs. -/
theorem decodeSourceEnvelope_matches {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {actual : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor actual = .ok decoded) :
    sourceEnvelope program contract scope factor = .ok actual := by
  unfold decodeSourceEnvelope decodeExact at accepted
  split at accepted
  · contradiction
  · rename_i generated canonical equation
    split at accepted
    · rename_i same
      simpa only [same] using equation
    · contradiction

end LLMLang.SourceQueryEnvelope
