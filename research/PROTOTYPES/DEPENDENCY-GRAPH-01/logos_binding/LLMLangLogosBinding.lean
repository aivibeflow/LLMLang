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
  | symbol : String → QueryTerm sort
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
  match term with
  | .intLit value => pure (.Numeral value)
  | .boolLit value => pure (.Boolean value)
  | .symbol name => resolveQuerySymbol bindings name sort
  | .not value => apply1 .not <$> renderQueryTerm bindings value
  | .neg value => apply1 .__eoo_neg_2 <$> renderQueryTerm bindings value
  | .add left right => do
      let leftTerm ← renderQueryTerm bindings left
      let rightTerm ← renderQueryTerm bindings right
      applyRightAssocNil .plus [leftTerm, rightTerm]
  | .sub left right => apply2 .neg <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .mul left right => do
      let leftTerm ← renderQueryTerm bindings left
      let rightTerm ← renderQueryTerm bindings right
      applyRightAssocNil .mult [leftTerm, rightTerm]
  | .eqInt left right => apply2 .eq <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .eqBool left right => apply2 .eq <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .lt left right => apply2 .lt <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .le left right => apply2 .leq <$> renderQueryTerm bindings left <*> renderQueryTerm bindings right
  | .and terms =>
      if terms.length < 2 then throw "and requires at least two operands"
      else do
        let rendered ← terms.mapM (renderQueryTerm bindings)
        applyRightAssocNil .and rendered
  | .or terms =>
      if terms.length < 2 then throw "or requires at least two operands"
      else do
        let rendered ← terms.mapM (renderQueryTerm bindings)
        applyRightAssocNil .or rendered
  | .iteInt condition yes no =>
      apply3 .ite <$> renderQueryTerm bindings condition
        <*> renderQueryTerm bindings yes <*> renderQueryTerm bindings no
  | .iteBool condition yes no =>
      apply3 .ite <$> renderQueryTerm bindings condition
        <*> renderQueryTerm bindings yes <*> renderQueryTerm bindings no

/--
Build the exact two top-level assumptions used by the relational query:
the selected input differs, and at least one observation differs.
-/
def renderRelationalAssumptions
    (bindings : List (String × Eo.Term))
    (factorLeft factorRight : String)
    (factorDifference observationsDiffer : QueryTerm .bool) :
    Except String (List Eo.Term) := do
  let left ← resolveQuerySymbol bindings factorLeft .int
    <|> resolveQuerySymbol bindings factorLeft .bool
  let right ← resolveQuerySymbol bindings factorRight .int
    <|> resolveQuerySymbol bindings factorRight .bool
  let factorSortMatches :=
    (hasExpectedSort left .int && hasExpectedSort right .int) ||
    (hasExpectedSort left .bool && hasExpectedSort right .bool)
  if !factorSortMatches then throw "relational factor symbols have different sorts"
  let factorDiff := apply1 .not (apply2 .eq left right)
  let obsDiff ← renderQueryTerm bindings observationsDiffer
  let factorExpected ← renderQueryTerm bindings factorDifference
  if factorDiff != factorExpected then
    throw "factor-difference query term disagrees with bound factor symbols"
  pure [factorDiff, obsDiff]
