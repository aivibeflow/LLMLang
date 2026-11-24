import SolverRelationalQuery
import LLMLangLogosBinding
import QuerySymbolRenaming
import TypedQueryEquality

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

private def wireNames (bindings : List SymbolBinding) (name : String) : String :=
  ((bindings.find? (fun binding => binding.name == name)).map wireName).getD name

def wireTerm (bindings : List SymbolBinding) {sort : QuerySort} (term : QueryTerm sort) :
    QueryTerm sort :=
  QuerySymbolRenaming.rename (wireNames bindings) term

/-- Relate the typed wire term to the internal term under the same name map. -/
theorem wireTerm_preserves {sort : QuerySort} (bindings : List SymbolBinding)
    (term : QueryTerm sort) (env : SourceQuerySemantics.Env) :
    LogosQueryAdapter.evalLogosQuery (wireTerm bindings term) env =
      LogosQueryAdapter.evalLogosQuery term
        (QuerySymbolRenaming.pullback (wireNames bindings) env) :=
  QuerySymbolRenaming.eval_rename (wireNames bindings) env term

private def requireCoverage {sort : QuerySort} (bindings : List SymbolBinding)
    (term : QueryTerm sort) : Except String Unit := do
  for ref in term.symbols do
    unless bindings.any (fun binding => decide (binding.reference = ref)) do
      throw s!"missing exact source binding for {ref.name}"

mutual
  private def encode : {sort : QuerySort} → QueryTerm sort → Json
    | _, .intLit n => node .int "int" [] (toJson n)
    | _, .boolLit b => node .bool "bool" [] (toJson b)
    | _, .intSymbol name => node .int "symbol" [] (toJson name)
    | _, .boolSymbol name => node .bool "symbol" [] (toJson name)
    | _, .neg x => node .int "neg" [encode x]
    | _, .not x => node .bool "not" [encode x]
    | _, .add a b => node .int "add" [encode a, encode b]
    | _, .sub a b => node .int "sub" [encode a, encode b]
    | _, .mul a b => node .int "mul" [encode a, encode b]
    | _, .eqInt a b => node .bool "eq" [encode a, encode b]
    | _, .eqBool a b => node .bool "eq" [encode a, encode b]
    | _, .lt a b => node .bool "lt" [encode a, encode b]
    | _, .le a b => node .bool "le" [encode a, encode b]
    | _, .and terms => node .bool "and" (encodeList terms)
    | _, .or terms => node .bool "or" (encodeList terms)
    | _, .iteInt c a b => node .int "ite" [encode c, encode a, encode b]
    | _, .iteBool c a b => node .bool "ite" [encode c, encode a, encode b]

  private def encodeList : List (QueryTerm .bool) → List Json
    | [] => []
    | term :: tail => encode term :: encodeList tail
end

private def declarationJson (declaration : WireDeclaration) : Json :=
  Json.mkObj [("name", toJson declaration.name), ("sort", toJson (sortName declaration.sort))]

private def contractName (sort : QuerySort) (contract : ObservationContract) : String :=
  (Json.mkObj [("returned", toJson (sortName sort)), ("state", toJson (contract.fields.map
    (fun field => Json.mkObj [("id", toJson field.id.value), ("sort", toJson (sortName field.sort))])))]).compress

/-- Construct the source-owned typed content before rendering it as JSON. -/
def sourceTypedEnvelope {sort : QuerySort} (program : Program sort) (contract : ObservationContract)
    (scope : SourceScope) (factor : VariableId) : Except String DecodedRelationalQuery := do
  let some query := compileRelationalQuery program contract scope factor
    | throw "source program, contract or factor is not admitted"
  let lowered := query.lower
  let .and [factorTerm, observationTerm] := lowered.formula
    | throw "source formula must contain two ordered assumptions"
  requireCoverage lowered.bindings lowered.formula
  let wireSymbols := lowered.bindings.map wireName
  if wireSymbols.eraseDups.length != wireSymbols.length then
    throw "wire symbol names are ambiguous"
  pure {
    factor := "f_" ++ Nat.repr factor.value
    factorLeft := wireName (bindingOnSide query.selected factor .left)
    factorRight := wireName (bindingOnSide query.selected factor .right)
    declarations := lowered.bindings.map fun binding =>
      ⟨wireName binding, binding.declaration.sort⟩
    factorDifference := wireTerm lowered.bindings factorTerm
    observationsDiffer := wireTerm lowered.bindings observationTerm
    observationContract := contractName sort contract
  }

private def encodeEnvelope (query : DecodedRelationalQuery) : String :=
  (Json.mkObj [
    ("schema", toJson "llmlang.qf_lia.relational-query/2"),
    ("factor", toJson query.factor),
    ("factor_left", toJson query.factorLeft), ("factor_right", toJson query.factorRight),
    ("declarations", toJson (query.declarations.map declarationJson)),
    ("factor_difference", encode query.factorDifference),
    ("observations_differ", encode query.observationsDiffer),
    ("observation_contract", toJson query.observationContract)]).compress

/-- Construct the /2 envelope from the checked source program, contract and selected input. -/
def sourceEnvelope {sort : QuerySort} (program : Program sort) (contract : ObservationContract)
    (scope : SourceScope) (factor : VariableId) : Except String String :=
  (sourceTypedEnvelope program contract scope factor).map encodeEnvelope

/-- Compare decoded declarations, observation metadata and ordered typed assumptions. -/
def compareTypedEnvelopes : (actual expected : DecodedRelationalQuery) →
    Option (PLift (actual = expected))
  | ⟨factor, left, right, decls, factorTerm, observationTerm, contract⟩,
    ⟨expectFactor, expectLeft, expectRight, expectDecls, expectFactorTerm,
      expectObservationTerm, expectContract⟩ => do
    if h : (factor, left, right, decls, contract) =
        (expectFactor, expectLeft, expectRight, expectDecls, expectContract) then
      let hf ← factorTerm.exactEq expectFactorTerm
      let ho ← observationTerm.exactEq expectObservationTerm
      pure ⟨by
        simp only [Prod.mk.injEq] at h
        obtain ⟨rfl, rfl, rfl, rfl, rfl⟩ := h
        rw [hf.down, ho.down]⟩
    else
      none

private structure CheckedEnvelope (source : Except String DecodedRelationalQuery) (wire : String) where
  query : DecodedRelationalQuery
  sameSource : source = .ok query
  sameBytes : encodeEnvelope query = wire
  sameDecoded : decodeCanonicalRelationalQuery wire = .ok query

private def checkEnvelope (source : Except String DecodedRelationalQuery) (actual : String) :
    Except String (CheckedEnvelope source actual) :=
  match source with
  | .error reason => .error reason
  | .ok expected =>
    if hb : encodeEnvelope expected = actual then
      match hd : decodeCanonicalRelationalQuery actual with
      | .error reason => .error reason
      | .ok decoded =>
        match compareTypedEnvelopes decoded expected with
        | none => .error "decoded query is structurally different from the source query"
        | some same => .ok ⟨expected, rfl, hb, by simpa only [same.down] using hd⟩
    else
      .error "wire bytes differ from the canonical source envelope"

def decodeSourceEnvelope {sort : QuerySort} (program : Program sort)
    (contract : ObservationContract) (scope : SourceScope) (factor : VariableId)
    (actual : String) : Except String DecodedRelationalQuery :=
  (checkEnvelope (sourceTypedEnvelope program contract scope factor) actual).map (·.query)

/-- An admitted wire query is exactly the source-generated typed content and decoder output. -/
theorem decodeSourceEnvelope_typed {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {actual : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor actual = .ok decoded) :
    sourceTypedEnvelope program contract scope factor = .ok decoded ∧
      decodeCanonicalRelationalQuery actual = .ok decoded := by
  unfold decodeSourceEnvelope at accepted
  cases h : checkEnvelope (sourceTypedEnvelope program contract scope factor) actual with
  | error reason => simp [h, Except.map] at accepted
  | ok checked =>
      simp [h, Except.map] at accepted
      exact ⟨checked.sameSource.trans (congrArg Except.ok accepted),
        checked.sameDecoded.trans (congrArg Except.ok accepted)⟩

/-- Any successful decode consumed exactly the bytes generated from these source inputs. -/
theorem decodeSourceEnvelope_matches {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {actual : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor actual = .ok decoded) :
    sourceEnvelope program contract scope factor = .ok actual := by
  unfold decodeSourceEnvelope at accepted
  cases h : checkEnvelope (sourceTypedEnvelope program contract scope factor) actual with
  | error reason => simp [h, Except.map] at accepted
  | ok checked =>
      simp [sourceEnvelope, checked.sameSource, checked.sameBytes, Except.map]

end LLMLang.SourceQueryEnvelope
