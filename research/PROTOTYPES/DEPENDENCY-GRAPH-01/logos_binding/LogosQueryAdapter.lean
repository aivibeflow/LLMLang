import SourceQuerySemantics
import LLMLangLogosBinding

namespace LLMLang.LogosQueryAdapter

open LLMLang.SourceQuerySemantics

/--
Translate the Logos-independent semantic query IR into the pinned Logos
query-term AST. This module is the only layer that knows both ASTs.
-/
def toLogosQueryTerm : {s : ExprSort} →
    SourceQuerySemantics.QueryTerm s → LLMLang.LogosBinding.QueryTerm s
  | .int, .intLit n => .intLit n
  | .bool, .boolLit b => .boolLit b
  | .int, .symbolInt name => .intSymbol name
  | .bool, .symbolBool name => .boolSymbol name
  | .int, .neg e => .neg (toLogosQueryTerm e)
  | .int, .add a b => .add (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .int, .sub a b => .sub (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .int, .mulConst k e => .mul (.intLit k) (toLogosQueryTerm e)
  | .bool, .not e => .not (toLogosQueryTerm e)
  | .bool, .eqInt a b => .eqInt (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .bool, .eqBool a b => .eqBool (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .bool, .lt a b => .lt (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .bool, .le a b => .le (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .bool, .and a b => .and [toLogosQueryTerm a, toLogosQueryTerm b]
  | .bool, .or a b => .or [toLogosQueryTerm a, toLogosQueryTerm b]
  | .int, .iteInt c a b =>
      .iteInt (toLogosQueryTerm c) (toLogosQueryTerm a) (toLogosQueryTerm b)
  | .bool, .iteBool c a b =>
      .iteBool (toLogosQueryTerm c) (toLogosQueryTerm a) (toLogosQueryTerm b)

mutual
  /-- Evaluate one Logos query term in the mathematical query environment. -/
  def evalLogosQuery {s : ExprSort}
      (term : LLMLang.LogosBinding.QueryTerm s)
      (env : SourceQuerySemantics.Env) :
      SourceQuerySemantics.Value s :=
    match term with
    | .intLit n => .intValue n
    | .boolLit b => .boolValue b
    | .intSymbol name => env name .int
    | .boolSymbol name => env name .bool
    | .neg e => .intValue (-(asInt (evalLogosQuery e env)))
    | .add a b =>
        .intValue (asInt (evalLogosQuery a env) + asInt (evalLogosQuery b env))
    | .sub a b =>
        .intValue (asInt (evalLogosQuery a env) - asInt (evalLogosQuery b env))
    | .mul a b =>
        .intValue (asInt (evalLogosQuery a env) * asInt (evalLogosQuery b env))
    | .not e => .boolValue (!(asBool (evalLogosQuery e env)))
    | .eqInt a b =>
        .boolValue (decide (asInt (evalLogosQuery a env) = asInt (evalLogosQuery b env)))
    | .eqBool a b =>
        .boolValue (decide (asBool (evalLogosQuery a env) = asBool (evalLogosQuery b env)))
    | .lt a b =>
        .boolValue (decide (asInt (evalLogosQuery a env) < asInt (evalLogosQuery b env)))
    | .le a b =>
        .boolValue (decide (asInt (evalLogosQuery a env) <= asInt (evalLogosQuery b env)))
    | .and terms => .boolValue (evalLogosBoolTerms true terms env)
    | .or terms => .boolValue (evalLogosBoolTerms false terms env)
    | .iteInt c a b =>
        if asBool (evalLogosQuery c env) then evalLogosQuery a env
        else evalLogosQuery b env
    | .iteBool c a b =>
        if asBool (evalLogosQuery c env) then evalLogosQuery a env
        else evalLogosQuery b env

  /-- Evaluate the n-ary Boolean operators with their standard identities. -/
  def evalLogosBoolTerms
      (conjunction : Bool)
      (terms : List (LLMLang.LogosBinding.QueryTerm .bool))
      (env : SourceQuerySemantics.Env) : Bool :=
    match terms with
    | [] => conjunction
    | term :: rest =>
        if conjunction then
          asBool (evalLogosQuery term env) && evalLogosBoolTerms conjunction rest env
        else
          asBool (evalLogosQuery term env) || evalLogosBoolTerms conjunction rest env
  termination_by
    evalLogosQuery term env => sizeOf term
    evalLogosBoolTerms conjunction terms env => sizeOf terms
  decreasing_by
    all_goals simp_wf [sizeOf]
end

/-- Evaluate a dependent pair of a sort and a Logos query term. -/
def evalLogosQuerySigma
    (query : Σ s : ExprSort, LLMLang.LogosBinding.QueryTerm s)
    (env : SourceQuerySemantics.Env) :
    SourceQuerySemantics.Value query.1 :=
  evalLogosQuery query.2 env

/--
The adapter preserves mathematical meaning for every well-typed independent
query term and every environment. This theorem is separate from the semantic
core and is kernel checked together with the adapter.
-/
theorem toLogosQueryTerm_preserves_eval {s : ExprSort}
    (term : SourceQuerySemantics.QueryTerm s)
    (env : SourceQuerySemantics.Env) :
    evalLogosQuery (toLogosQueryTerm term) env =
      SourceQuerySemantics.evalQuery term env := by
  induction term <;>
    simp_all [toLogosQueryTerm, evalLogosQuery, evalLogosBoolTerms,
      SourceQuerySemantics.evalQuery, asInt, asBool]

end LLMLang.LogosQueryAdapter
