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
  /--
  Evaluate a Logos query term. The mutually recursive list evaluator makes
  Logos' n-ary Boolean operands explicit structural subterms: evaluating an
  operator descends to its operand list, and evaluating the list descends to
  each term and its tail. This avoids a non-structural recursive call hidden
  inside List.all/List.any.
  -/
  def evalLogosQuery : {s : ExprSort} →
      LLMLang.LogosBinding.QueryTerm s →
      SourceQuerySemantics.Env →
      SourceQuerySemantics.Value s
    | .int, .intLit n, _ => .intValue n
    | .bool, .boolLit b, _ => .boolValue b
    | .int, .intSymbol name, env => env name .int
    | .bool, .boolSymbol name, env => env name .bool
    | .int, .neg e, env =>
        .intValue (-(asInt (evalLogosQuery e env)))
    | .int, .add a b, env =>
        .intValue (asInt (evalLogosQuery a env) + asInt (evalLogosQuery b env))
    | .int, .sub a b, env =>
        .intValue (asInt (evalLogosQuery a env) - asInt (evalLogosQuery b env))
    | .int, .mul a b, env =>
        .intValue (asInt (evalLogosQuery a env) * asInt (evalLogosQuery b env))
    | .bool, .not e, env =>
        .boolValue (!(asBool (evalLogosQuery e env)))
    | .bool, .eqInt a b, env =>
        .boolValue (decide (asInt (evalLogosQuery a env) = asInt (evalLogosQuery b env)))
    | .bool, .eqBool a b, env =>
        .boolValue (decide (asBool (evalLogosQuery a env) = asBool (evalLogosQuery b env)))
    | .bool, .lt a b, env =>
        .boolValue (decide (asInt (evalLogosQuery a env) < asInt (evalLogosQuery b env)))
    | .bool, .le a b, env =>
        .boolValue (decide (asInt (evalLogosQuery a env) <= asInt (evalLogosQuery b env)))
    | .bool, .and terms, env =>
        .boolValue ((evalLogosQueryList terms env).all id)
    | .bool, .or terms, env =>
        .boolValue ((evalLogosQueryList terms env).any id)
    | .int, .iteInt condition yes no, env =>
        if asBool (evalLogosQuery condition env) then
          evalLogosQuery yes env
        else
          evalLogosQuery no env
    | .bool, .iteBool condition yes no, env =>
        if asBool (evalLogosQuery condition env) then
          evalLogosQuery yes env
        else
          evalLogosQuery no env

  def evalLogosQueryList :
      List (LLMLang.LogosBinding.QueryTerm .bool) →
      SourceQuerySemantics.Env → List Bool
    | [], _ => []
    | term :: rest, env =>
        asBool (evalLogosQuery term env) :: evalLogosQueryList rest env
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
    simp_all [toLogosQueryTerm, evalLogosQuery,
      SourceQuerySemantics.evalQuery, asInt, asBool]

end LLMLang.LogosQueryAdapter
