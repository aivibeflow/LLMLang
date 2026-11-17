import Cpc.Parser

namespace LLMLang.LogosBinding

inductive ExpectedSort where
  | int
  | bool
  deriving DecidableEq, Repr

structure ExpectedDeclaration where
  name : String
  sort : ExpectedSort
  deriving DecidableEq, Repr

abbrev ParserState := Logos.Parser.State Eo.Term

/--
Run the pinned Logos CPC parser while retaining its final declaration state.
Datatype elaboration is disabled here because this bridge accepts only the
Bool/Int QF_LIA fragment. The ordinary Eo.parseProof result is checked against
the state-preserving path before returning.
-/
def parseProofWithState
    (proof : String) :
    Except String (List Eo.Term × Eo.CCmdList × ParserState) := do
  let sexps ← Logos.Sexp.Parser.manySexps!.run proof
  let cfg : Logos.Parser.Config Eo.Term Eo.CRule Eo.CCmd Eo.CCmdList :=
    { Eo.parserConfig with datatypeTerms := none }
  let initial : ParserState :=
    { Logos.Parser.State.ofOps cfg.ops with macros := .ofList cfg.macros }
  let ((assumptions, commands), finalState) ←
    (Logos.Parser.parseCommands cfg sexps).run initial
  let ordinary ← Eo.parseProof proof
  if assumptions = ordinary.1 then
    pure (assumptions, commands, finalState)
  else
    throw "state-preserving CPC parser disagrees with Eo.parseProof assumptions"

/-- Check that a parsed declared constant has exactly the expected QF_LIA sort. -/
def hasExpectedSort : Eo.Term → ExpectedSort → Bool
  | Eo.Term.UConst _ Eo.Term.Bool, ExpectedSort.bool => true
  | Eo.Term.UConst _ (Eo.Term.UOp Eo.UserOp.Int), ExpectedSort.int => true
  | _, _ => false

def lookupDeclaration
    (state : ParserState)
    (declaration : ExpectedDeclaration) :
    Except String Eo.Term := do
  match state.terms.getD declaration.name [] with
  | [term@(Eo.Term.UConst _ _)] =>
      if hasExpectedSort term declaration.sort then
        pure term
      else
        throw s!"unexpected sort for CPC declaration: {declaration.name}"
  | [] =>
      throw s!"missing CPC declaration: {declaration.name}"
  | _ =>
      throw s!"ambiguous or repeated CPC declaration: {declaration.name}"

/--
Bind the complete expected declaration set to the exact UConst nodes retained
by the Logos parser. Extra, missing, duplicate, overloaded, or wrong-sort
declarations fail closed.
-/
def bindExpectedDeclarations
    (state : ParserState)
    (expected : List ExpectedDeclaration) :
    Except String (List (String × Eo.Term)) := do
  let names := expected.map ExpectedDeclaration.name
  if names.eraseDups.length != names.length then
    throw "duplicate name in expected CPC declaration set"
  if state.ufCount != expected.length then
    throw "CPC uninterpreted-constant count differs from expected declaration count"
  if state.terms.toList.length != expected.length then
    throw "CPC declaration table contains missing or unexpected names"
  expected.mapM fun declaration => do
    let term ← lookupDeclaration state declaration
    pure (declaration.name, term)

end LLMLang.LogosBinding


namespace LLMLang.LogosBinding

/-- Canonical query sorts accepted by the strict relational QF_LIA profile. -/
inductive QuerySort where
  | int
  | bool
  deriving DecidableEq, Repr

/--
Typed relational query terms. The result sort is part of the type, so malformed
operator/sort combinations cannot be represented by these constructors.
-/
inductive QueryTerm : QuerySort → Type where
  | intLit : Int → QueryTerm .int
  | boolLit : Bool → QueryTerm .bool
  | intSymbol : String → QueryTerm .int
  | boolSymbol : String → QueryTerm .bool
  | not : QueryTerm .bool → QueryTerm .bool
  | neg : QueryTerm .int → QueryTerm .int
  | add : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | sub : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | mul : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | eqInt : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | eqBool : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool
  | lt : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | le : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | and : List (QueryTerm .bool) → QueryTerm .bool
  | or : List (QueryTerm .bool) → QueryTerm .bool
  | iteInt : QueryTerm .bool → QueryTerm .int → QueryTerm .int → QueryTerm .int
  | iteBool : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool → QueryTerm .bool

def QuerySort.expected : QuerySort → ExpectedSort
  | .int => LLMLang.LogosBinding.ExpectedSort.int
  | .bool => LLMLang.LogosBinding.ExpectedSort.bool

def apply1 (op : Eo.UserOp) (a : Eo.Term) : Eo.Term :=
  Eo.Term.Apply (Eo.Term.UOp op) a

def apply2 (op : Eo.UserOp) (a b : Eo.Term) : Eo.Term :=
  Eo.Term.Apply (Eo.Term.Apply (Eo.Term.UOp op) a) b

def apply3 (op : Eo.UserOp) (a b c : Eo.Term) : Eo.Term :=
  Eo.Term.Apply (Eo.Term.Apply (Eo.Term.Apply (Eo.Term.UOp op) a) b) c

def applyRightAssocNil (op : Eo.UserOp) (terms : List Eo.Term) : Except String Eo.Term := do
  let seed ← match terms.head? with
    | some value => pure value
    | none => throw "right-associative operator requires at least one operand"
  let nil := Eo.__eo_nil (Eo.Term.UOp op) (Eo.__eo_typeof seed)
  pure <| terms.foldr (fun term acc =>
    Eo.Term.Apply (Eo.Term.Apply (Eo.Term.UOp op) term) acc) nil

/-- Resolve a source symbol only through the parser-state-derived exact binding. -/
def resolveQuerySymbol
    (bindings : List (String × Eo.Term))
    (name : String)
    (sort : QuerySort) :
    Except String Eo.Term := do
  match bindings.filter (fun entry => entry.1 == name) with
  | [( _, term)] =>
      if hasExpectedSort term sort.expected then pure term
      else throw s!"query symbol has wrong bound sort: {name}"
  | [] => throw s!"query symbol is not bound to a CPC declaration: {name}"
  | _ => throw s!"query symbol has ambiguous CPC bindings: {name}"

/-- Independently render the typed query AST into the pinned Logos Eo.Term AST. -/
def renderQueryTerm {sort : QuerySort}
    (bindings : List (String × Eo.Term))
    (term : QueryTerm sort) :
    Except String Eo.Term := do
  match sort, term with
  | .int, .intLit value => pure (.Numeral value)
  | .int, .intSymbol name => resolveQuerySymbol bindings name .int
  | .int, .neg value => apply1 .__eoo_neg_2 <$> renderQueryTerm bindings value
  | .int, .add left right => do
      let leftTerm ← renderQueryTerm bindings left
      let rightTerm ← renderQueryTerm bindings right
      applyRightAssocNil .plus [leftTerm, rightTerm]
  | .int, .sub left right =>
      apply2 .neg <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .int, .mul left right => do
      let leftTerm ← renderQueryTerm bindings left
      let rightTerm ← renderQueryTerm bindings right
      applyRightAssocNil .mult [leftTerm, rightTerm]
  | .int, .iteInt condition yes no =>
      apply3 .ite <$> renderQueryTerm bindings condition
        <*> renderQueryTerm bindings yes <*> renderQueryTerm bindings no
  | .bool, .boolLit value => pure (.Boolean value)
  | .bool, .boolSymbol name => resolveQuerySymbol bindings name .bool
  | .bool, .not value => apply1 .not <$> renderQueryTerm bindings value
  | .bool, .eqInt left right =>
      apply2 .eq <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .bool, .eqBool left right =>
      apply2 .eq <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .bool, .lt left right =>
      apply2 .lt <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .bool, .le left right =>
      apply2 .leq <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .bool, .and terms =>
      if terms.length < 2 then throw "and requires at least two operands"
      else do
        let rendered ← terms.mapM (renderQueryTerm bindings)
        applyRightAssocNil .and rendered
  | .bool, .or terms =>
      if terms.length < 2 then throw "or requires at least two operands"
      else do
        let rendered ← terms.mapM (renderQueryTerm bindings)
        applyRightAssocNil .or rendered
  | .bool, .iteBool condition yes no =>
      apply3 .ite <$> renderQueryTerm bindings condition
        <*> renderQueryTerm bindings yes <*> renderQueryTerm bindings no

/--
Build the exact two top-level assumptions used by the relational query:
the selected input differs, and at least one observation differs.
-/
def renderRelationalAssumptions
    (bindings : List (String × Eo.Term))
    (factorSort : QuerySort)
    (factorLeft factorRight : String)
    (factorDifference observationsDiffer : QueryTerm .bool) :
    Except String (List Eo.Term) := do
  let left ← resolveQuerySymbol bindings factorLeft factorSort
  let right ← resolveQuerySymbol bindings factorRight factorSort
  let factorDiff := apply1 .not (apply2 .eq left right)
  let obsDiff ← renderQueryTerm bindings observationsDiffer
  let factorExpected ← renderQueryTerm bindings factorDifference
  if factorDiff != factorExpected then
    throw "factor-difference query term disagrees with bound factor symbols"
  pure [factorDiff, obsDiff]

end LLMLang.LogosBinding


namespace LLMLang.LogosBinding

/-- Strict wire declaration decoded from the canonical query document. -/
structure WireDeclaration where
  name : String
  sort : QuerySort
  deriving DecidableEq, Repr

/-- A decoded, versioned canonical relational query. -/
structure DecodedRelationalQuery where
  factor : String
  declarations : List WireDeclaration
  factorDifference : QueryTerm .bool
  observationsDiffer : QueryTerm .bool
  observationContract : String
  deriving Repr

private def jsonField (value : Json) (key : String) : Except String Json :=
  value.getObjVal? key

private def jsonStringField (value : Json) (key : String) : Except String String := do
  let field ← jsonField value key
  field.getStr?

private def jsonArrayField (value : Json) (key : String) : Except String (Array Json) := do
  let field ← jsonField value key
  field.getArr?

private def jsonInt (value : Json) : Except String Int :=
  value.getInt?

private def jsonBool (value : Json) : Except String Bool :=
  value.getBool?

/-- Require an object to contain exactly the supplied field names. -/
private def requireExactFields (value : Json) (expected : List String) : Except String Unit := do
  let object ← value.getObj?
  let actual := object.toList.map Prod.fst
  if actual.length != expected.length ||
      expected.any (fun key => !actual.contains key) then
    throw "JSON object has missing or unknown fields"
  pure ()

private def requireNullField (value : Json) (key : String) : Except String Unit := do
  let field ← jsonField value key
  if field != Json.null then throw s!"field must be null: {key}"

/--
Decode the exact version-1 term object shape. The expected result sort is
provided by the caller; every node's explicit sort is checked against it.
Unknown operators, extra fields, wrong arity, and malformed atoms fail closed.
-/
mutual
  partial def decodeIntTerm (value : Json) : Except String (QueryTerm .int) := do
    requireExactFields value ["op", "sort", "args", "atom"]
    let op ← jsonStringField value "op"
    let sort ← jsonStringField value "sort"
    let args ← jsonArrayField value "args"
    let atom ← jsonField value "atom"
    if sort != "Int" then throw "integer query node has non-Int sort"
    match op with
    | "int" =>
        if !args.isEmpty then throw "integer literal must have no arguments"
        .intLit (← jsonInt atom)
    | "symbol" =>
        if !args.isEmpty then throw "symbol must have no arguments"
        .intSymbol (← atom.getStr?)
    | "neg" =>
        requireNullField value "atom"
        if args.size != 1 then throw "neg expects exactly one argument"
        .neg (← decodeIntTerm args[0]!)
    | "add" =>
        requireNullField value "atom"
        if args.size != 2 then throw "add expects exactly two arguments"
        .add (← decodeIntTerm args[0]!) (← decodeIntTerm args[1]!)
    | "sub" =>
        requireNullField value "atom"
        if args.size != 2 then throw "sub expects exactly two arguments"
        .sub (← decodeIntTerm args[0]!) (← decodeIntTerm args[1]!)
    | "mul" =>
        requireNullField value "atom"
        if args.size != 2 then throw "mul expects exactly two arguments"
        let left ← decodeIntTerm args[0]!
        let right ← decodeIntTerm args[1]!
        if !(match left with | .intLit _ => true | _ => false) &&
           !(match right with | .intLit _ => true | _ => false) then
          throw "nonlinear multiplication is outside the strict QF_LIA profile"
        pure (.mul left right)
    | "ite" =>
        requireNullField value "atom"
        if args.size != 3 then throw "ite expects exactly three arguments"
        .iteInt (← decodeBoolTerm args[0]!) (← decodeIntTerm args[1]!) (← decodeIntTerm args[2]!)
    | _ => throw s!"unsupported Int query operator: {op}"

  partial def decodeBoolTerm (value : Json) : Except String (QueryTerm .bool) := do
    requireExactFields value ["op", "sort", "args", "atom"]
    let op ← jsonStringField value "op"
    let sort ← jsonStringField value "sort"
    let args ← jsonArrayField value "args"
    let atom ← jsonField value "atom"
    if sort != "Bool" then throw "Boolean query node has non-Bool sort"
    match op with
    | "bool" =>
        if !args.isEmpty then throw "Boolean literal must have no arguments"
        .boolLit (← jsonBool atom)
    | "symbol" =>
        if !args.isEmpty then throw "symbol must have no arguments"
        .boolSymbol (← atom.getStr?)
    | "not" =>
        requireNullField value "atom"
        if args.size != 1 then throw "not expects exactly one argument"
        .not (← decodeBoolTerm args[0]!)
    | "eq" =>
        requireNullField value "atom"
        if args.size != 2 then throw "eq expects exactly two arguments"
        let leftSort ← jsonStringField args[0]! "sort"
        let rightSort ← jsonStringField args[1]! "sort"
        if leftSort != rightSort then throw "eq operands have different sorts"
        if leftSort == "Int" then
          .eqInt (← decodeIntTerm args[0]!) (← decodeIntTerm args[1]!)
        else if leftSort == "Bool" then
          .eqBool (← decodeBoolTerm args[0]!) (← decodeBoolTerm args[1]!)
        else
          throw "eq supports only Int and Bool operands"
    | "lt" =>
        requireNullField value "atom"
        if args.size != 2 then throw "lt expects exactly two arguments"
        .lt (← decodeIntTerm args[0]!) (← decodeIntTerm args[1]!)
    | "le" =>
        requireNullField value "atom"
        if args.size != 2 then throw "le expects exactly two arguments"
        .le (← decodeIntTerm args[0]!) (← decodeIntTerm args[1]!)
    | "and" =>
        requireNullField value "atom"
        if args.size < 2 then throw "and expects at least two arguments"
        .and (← args.toList.mapM decodeBoolTerm)
    | "or" =>
        requireNullField value "atom"
        if args.size < 2 then throw "or expects at least two arguments"
        .or (← args.toList.mapM decodeBoolTerm)
    | "ite" =>
        requireNullField value "atom"
        if args.size != 3 then throw "ite expects exactly three arguments"
        .iteBool (← decodeBoolTerm args[0]!) (← decodeBoolTerm args[1]!) (← decodeBoolTerm args[2]!)
    | _ => throw s!"unsupported Bool query operator: {op}"
end

private def decodeWireDeclaration (value : Json) : Except String WireDeclaration := do
  requireExactFields value ["name", "sort"]
  let name ← jsonStringField value "name"
  let sort ← jsonStringField value "sort"
  if name.isEmpty then throw "query declaration name must not be empty"
  match sort with
  | "Int" => pure ⟨name, .int⟩
  | "Bool" => pure ⟨name, .bool⟩
  | _ => throw "query declaration sort must be Int or Bool"

/--
Decode the canonical JSON envelope. Version 1 uses exact field sets and the
wire schema documented in Scenario 32. No coercion or unknown-field tolerance
is permitted.
-/
def decodeCanonicalRelationalQuery (source : String) : Except String DecodedRelationalQuery := do
  let json ← Json.parse source
  requireExactFields json
    ["schema", "factor", "declarations", "factor_difference", "observations_differ", "observation_contract"]
  let schema ← jsonStringField json "schema"
  if schema != "llmlang.qf_lia.relational-query/1" then
    throw "unsupported canonical query schema version"
  let factor ← jsonStringField json "factor"
  let contract ← jsonStringField json "observation_contract"
  if factor.isEmpty || contract.isEmpty then throw "factor and observation contract are required"
  let rawDeclarations ← jsonArrayField json "declarations"
  let declarations ← rawDeclarations.toList.mapM decodeWireDeclaration
  let names := declarations.map WireDeclaration.name
  if names.eraseDups.length != names.length then throw "duplicate canonical query declaration"
  let factorDifference ← decodeBoolTerm (← jsonField json "factor_difference")
  let observationsDiffer ← decodeBoolTerm (← jsonField json "observations_differ")
  pure ⟨factor, declarations, factorDifference, observationsDiffer, contract⟩

/-- Bind decoded query declarations to the exact CPC parser-state UConst map. -/
def bindDecodedQueryDeclarations
    (state : ParserState)
    (query : DecodedRelationalQuery) :
    Except String (List (String × Eo.Term)) := do
  let expected := query.declarations.map fun declaration =>
    { name := declaration.name, sort := declaration.sort.expected : ExpectedDeclaration }
  bindExpectedDeclarations state expected

/-- Decode, bind, render, and structurally compare the complete CPC assumptions. -/
def checkCanonicalQueryAssumptions
    (proof : String)
    (queryJson : String) :
    Except String Unit := do
  let query ← decodeCanonicalRelationalQuery queryJson
  let (assumptions, _commands, state) ← parseProofWithState proof
  let bindings ← bindDecodedQueryDeclarations state query
  let expectedFactor ← renderQueryTerm bindings query.factorDifference
  let expectedObservations ← renderQueryTerm bindings query.observationsDiffer
  let expected := [expectedFactor, expectedObservations]
  if assumptions != expected then
    throw "complete CPC assumption list differs from canonical query terms"
  pure ()

end LLMLang.LogosBinding
