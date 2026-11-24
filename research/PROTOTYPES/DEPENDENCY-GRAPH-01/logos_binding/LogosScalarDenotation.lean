import SourceQueryEnvelope
import LogosRenderedSorts
import LogosQueryAdapter
import Cpc.SmtTranslate

namespace LLMLang.LogosScalarDenotation

open LLMLang.LogosBinding
open LLMLang.SourceQuerySemantics (Expr Value Env evalExpr translateExpr)
open LLMLang.LogosQueryAdapter (toLogosQueryTerm)
open Smtm (SmtTerm SmtType)

inductive Scalar where
  | int (value : Int)
  | bool (value : Bool)
  deriving Repr, BEq

def Scalar.sort : Scalar → SmtType
  | .int _ => .Int
  | .bool _ => .Bool

def fromSource : {s : QuerySort} → Value s → Scalar
  | .int, .intValue n => .int n
  | .bool, .boolValue b => .bool b

def needInt : Scalar → Except String Int
  | .int value => .ok value
  | _ => .error "integer expected"

def needBool : Scalar → Except String Bool
  | .bool value => .ok value
  | _ => .error "Boolean expected"

abbrev Valuation := List (SmtEval.native_String × Scalar)

/-- Executable semantics for only the translated integer and Boolean constructors. -/
def evalSmt (env : Valuation) : SmtTerm → Except String Scalar
  | .Numeral n => .ok (.int n)
  | .Boolean b => .ok (.bool b)
  | .UConst key sort => do
      let some (_, value) := env.find? (fun entry => entry.1 == key)
        | throw "unbound SMT constant"
      if value.sort == sort then pure value else throw "wrong SMT constant sort"
  | .plus a b => do
      pure (.int ((← needInt (← evalSmt env a)) + (← needInt (← evalSmt env b))))
  | .neg a b => do
      pure (.int ((← needInt (← evalSmt env a)) - (← needInt (← evalSmt env b))))
  | .uneg a => do
      pure (.int (-(← needInt (← evalSmt env a))))
  | .mult a b => do
      pure (.int ((← needInt (← evalSmt env a)) * (← needInt (← evalSmt env b))))
  | .lt a b => do
      pure (.bool (decide ((← needInt (← evalSmt env a)) < (← needInt (← evalSmt env b)))))
  | .leq a b => do
      pure (.bool (decide ((← needInt (← evalSmt env a)) ≤ (← needInt (← evalSmt env b)))))
  | .eq a b => do
      let left ← evalSmt env a
      let right ← evalSmt env b
      if left.sort == right.sort then pure (.bool (left == right)) else throw "mixed equality"
  | .not a => do
      pure (.bool (!(← needBool (← evalSmt env a))))
  | .and a b => do
      let left ← needBool (← evalSmt env a)
      let right ← needBool (← evalSmt env b)
      pure (.bool (left && right))
  | .or a b => do
      let left ← needBool (← evalSmt env a)
      let right ← needBool (← evalSmt env b)
      pure (.bool (left || right))
  | .ite cond yes no => do
      let chosen ← needBool (← evalSmt env cond)
      let left ← evalSmt env yes
      let right ← evalSmt env no
      if left.sort != right.sort then throw "mixed conditional arms"
      pure (if chosen then left else right)
  | _ => .error "unsupported translated SMT constructor"

def keyFor (binding : Eo.Term) : Except String SmtEval.native_String :=
  match __eo_to_smt binding with
  | .UConst key _ => pure key
  | _ => throw "CPC declaration did not translate to an SMT constant"

def liftValuation (bindings : List (String × Eo.Term)) (env : Env) : Except String Valuation := do
  let lifted ← bindings.mapM fun (name, binding) => do
    let key ← keyFor binding
    if hasExpectedSort binding .int then pure (key, .int (SourceQuerySemantics.asInt (env name .int)))
    else if hasExpectedSort binding .bool then pure (key, .bool (SourceQuerySemantics.asBool (env name .bool)))
    else throw "unsupported CPC declaration sort"
  let keys := lifted.map Prod.fst
  if keys.eraseDups.length == keys.length then pure lifted else throw "ambiguous SMT constants"

private def evalRendered (env : Valuation) (term : Eo.Term) : Except String Scalar :=
  evalSmt env (__eo_to_smt term)

private def ints : List Int := [-5, 0, 1, 9]
private def bools : List Bool := [false, true]

private def expressionEnvironment (x y : Int) (p q : Bool) : Env
  | name, .int => .intValue (if name == "x" then x else y)
  | name, .bool => .boolValue (if name == "p" then p else q)

private def intExpressions : List (Expr .int) :=
  let x := Expr.intVar "x"
  let y := Expr.intVar "y"
  let p := Expr.boolVar "p"
  [
    .intLit (-7), x, y, .neg x, .add x y, .sub x y,
    .mulConst (-3) y, .iteInt p x y,
    .sub (.add x (.intLit 1)) (.mulConst 2 (.neg y)),
    .iteInt (.le x y) (.mulConst 0 x) (.sub x y)
  ]

private def boolExpressions : List (Expr .bool) :=
  let x := Expr.intVar "x"
  let y := Expr.intVar "y"
  let p := Expr.boolVar "p"
  let q := Expr.boolVar "q"
  [
    .boolLit true, .boolLit false, p, q, .not p, .eqInt x y,
    .eqBool p q, .lt x y, .le x y, .and p q, .or p q,
    .iteBool p q (.not q), .and (.or p q) (.lt (.neg x) y),
    .iteBool (.eqInt x y) (.and p q) (.or p q)
  ]

private def checkExpressions : Except String Nat := do
  let (_, _, state) ← parseProofWithState
    "(declare-const x Int) (declare-const y Int) (declare-const p Bool) (declare-const q Bool)"
  let bindings ← bindExpectedDeclarations state [⟨"x", .int⟩, ⟨"y", .int⟩, ⟨"p", .bool⟩, ⟨"q", .bool⟩]
  let render := fun {sort : QuerySort} (source : Expr sort) =>
    renderQueryTerm bindings (toLogosQueryTerm (translateExpr source))
  let integers ← intExpressions.mapM fun expression => do pure (expression, ← render expression)
  let booleans ← boolExpressions.mapM fun expression => do pure (expression, ← render expression)
  let mut count := 0
  for x in ints do
    for y in ints do
      for p in bools do
        for q in bools do
          let sourceEnv := expressionEnvironment x y p q
          let model ← liftValuation bindings sourceEnv
          for (source, rendered) in integers do
            if (← evalRendered model rendered) != fromSource (evalExpr source sourceEnv) then
              throw s!"integer denotation mismatch at {x}, {y}, {p}, {q}"
            count := count + 1
          for (source, rendered) in booleans do
            if (← evalRendered model rendered) != fromSource (evalExpr source sourceEnv) then
              throw s!"Boolean denotation mismatch at {x}, {y}, {p}, {q}"
            count := count + 1
  let testEnv := expressionEnvironment 9 1 true false
  let model ← liftValuation bindings testEnv
  let original ← render (Expr.sub (.intVar "x") (.intVar "y"))
  let reversed ← render (Expr.sub (.intVar "y") (.intVar "x"))
  if Eo.__eo_typeof original != Eo.__eo_typeof reversed ||
      (← evalRendered model original) == (← evalRendered model reversed) then
    throw "sort-only control failed to distinguish reversed subtraction"
  let swappedBindings := bindings.map fun (name, bound) =>
    (name, if name == "x" then (bindings.lookup "y").getD bound
      else if name == "y" then (bindings.lookup "x").getD bound else bound)
  let swapped ← renderQueryTerm swappedBindings (.sub (.intSymbol "x") (.intSymbol "y"))
  if Eo.__eo_typeof swapped != logosSort .int ||
      (← evalRendered model original) == (← evalRendered model swapped) then
    throw "sort-only control failed to distinguish a swapped symbol binding"
  if (evalRendered [] original).isOk then
    throw "missing interpretation unexpectedly admitted"
  if (evalRendered model (.Rational 1)).isOk then
    throw "out-of-profile SMT term unexpectedly admitted"
  if (evalRendered model (apply3 .ite (.Boolean true) (.Numeral 1) (.Rational 1))).isOk then
    throw "out-of-profile SMT term admitted in an inactive branch"
  pure count

open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.SourceQueryEnvelope

private def xDecl : Declaration := ⟨⟨1⟩, "x", .input, .int⟩
private def pDecl : Declaration := ⟨⟨2⟩, "p", .input, .bool⟩
private def stateDecl : Declaration := ⟨⟨3⟩, "cell", .state, .int⟩
private def scope : SourceScope :=
  let ids := [xDecl.id, pDecl.id, stateDecl.id]
  ⟨⟨[xDecl, pDecl, stateDecl]⟩, ids, ids⟩

private def contract : ObservationContract := ⟨[⟨stateDecl.id, .int⟩]⟩

private def writeProgram : Program .int :=
  ⟨.branch (.boolVar "p")
      (.assign (.state stateDecl.id) (.add (.intVar "cell") (.intVar "x")))
      (.assign (.state stateDecl.id) (.neg (.intVar "x"))),
    .intVar "cell"⟩

private def observeStateProgram : Program .bool :=
  ⟨.branch (.boolVar "p")
      (.assign (.state stateDecl.id) (.intVar "x"))
      (.assign (.state stateDecl.id) (.intVar "cell")),
    .boolLit true⟩

private def concreteEnv (x : Int) (p : Bool) (cell : Int) : Env
  | name, .int => .intValue (if name == "x" then x else cell)
  | _, .bool => .boolValue p

private def stateValues : {fields : List StateField} → StateValues Value fields → List Scalar
  | _, .nil => []
  | _, .cons head tail => fromSource head :: stateValues tail

private def checkPrograms {sort : QuerySort} (program : Program sort) (factor : Declaration)
    (expectedScope : List (String × QuerySort))
    (valuations : List (Env × Env × Env)) : Except String (Nat × Nat) := do
  let wire ← sourceEnvelope program contract scope factor.id
  let decoded ← decodeSourceEnvelope program contract scope factor.id wire
  if decoded.declarations.map (fun declaration => (declaration.name, declaration.sort)) != expectedScope then
    throw "unexpected wire declaration layout for source pair"
  let declarations := String.join <| decoded.declarations.map fun declaration =>
    let name := if declaration.sort == .int then "Int" else "Bool"
    s!"(declare-const {declaration.name} {name})\n"
  let (_, _, state) ← parseProofWithState declarations
  let bindings ← bindDecodedQueryDeclarations state decoded
  let assumptions ← renderRelationalAssumptions bindings factor.sort decoded.factorLeft decoded.factorRight
    decoded.factorDifference decoded.observationsDiffer
  let [inputDiff, observationDiff] := assumptions | throw "expected two assumptions"
  let mut dependent := 0
  for (left, right, wireEnv) in valuations do
    let some pair := PairedValuations.check scope factor.id left right
      | throw "fixture selected incompatible concrete inputs"
    let some (a, b) := observeConcretePair program contract pair
      | throw "concrete pair had no observations"
    let inputChanged := fromSource (left factor.sourceName factor.sort) !=
      fromSource (right factor.sourceName factor.sort)
    let observableChange := fromSource a.returned != fromSource b.returned ||
      stateValues a.state != stateValues b.state
    let model ← liftValuation bindings wireEnv
    if (← evalRendered model inputDiff) != .bool inputChanged ||
        (← evalRendered model observationDiff) != .bool observableChange then
      throw "source pair differs from translated SMT assumptions"
    if inputChanged && observableChange then
      dependent := dependent + 1
  pure (valuations.length, dependent)

private def intPairs : List (Env × Env × Env) :=
  ints.flatMap fun x => ints.flatMap fun y => bools.flatMap fun p =>
    [(-2 : Int), 2].map fun cell =>
      let wire : Env := fun name sort =>
        match sort with
        | .int => .intValue (if name == "i_4_L" then x else if name == "i_5_R" then y else cell)
        | .bool => .boolValue p
      (concreteEnv x p cell, concreteEnv y p cell, wire)

private def boolPairs : List (Env × Env × Env) :=
  bools.flatMap fun a => bools.flatMap fun b => ints.flatMap fun x =>
    [(-2 : Int), 2].map fun cell =>
      let wire : Env := fun name sort =>
        match sort with
        | .int => .intValue (if name == "i_3" then x else cell)
        | .bool => .boolValue (if name == "i_7_L" then a else b)
      (concreteEnv x a cell, concreteEnv x b cell, wire)

def run : Except String (Nat × (Nat × Nat) × (Nat × Nat)) := do
  let expressions ← checkExpressions
  let integerPairs ← checkPrograms writeProgram xDecl
    [("i_4_L", .int), ("i_5_R", .int), ("i_6", .bool), ("i_9", .int)] intPairs
  let booleanPairs ← checkPrograms observeStateProgram pDecl
    [("i_3", .int), ("i_7_L", .bool), ("i_8_R", .bool), ("i_9", .int)] boolPairs
  pure (expressions, integerPairs, booleanPairs)

end LLMLang.LogosScalarDenotation

def main : IO Unit :=
  match LLMLang.LogosScalarDenotation.run with
  | .ok (expressions, (ints, intDiff), (bools, boolDiff)) => do
      IO.println s!"Expression evaluations compared: {expressions}"
      IO.println s!"Int-factor source pairs: {ints}, observable differences: {intDiff}"
      IO.println s!"Bool-factor source pairs: {bools}, observable differences: {boolDiff}"
      IO.println "Two same-sort mutations and three invalid interpretations detected"
  | .error message => throw (IO.userError message)
