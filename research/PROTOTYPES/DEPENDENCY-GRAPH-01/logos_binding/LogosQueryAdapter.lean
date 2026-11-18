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

/-- Evaluate the Logos AST using the mathematical semantics corresponding to its constructors. -/
mutual
  def evalLogosQuerySigma :
      (query : Σ s : ExprSort, LLMLang.LogosBinding.QueryTerm s) →
      SourceQuerySemantics.Env →
      SourceQuerySemantics.Value query.1
    | ⟨.int, .intLit n⟩, _ => .intValue n
    | ⟨.bool, .boolLit b⟩, _ => .boolValue b
    | ⟨.int, .intSymbol name⟩, env => env name .int
    | ⟨.bool, .boolSymbol name⟩, env => env name .bool
    | ⟨.int, .neg e⟩, env => .intValue (-(asInt (evalLogosQuerySigma ⟨.int, e⟩ env)))
    | ⟨.int, .add a b⟩, env =>
        .intValue (asInt (evalLogosQuerySigma ⟨.int, a⟩ env) +
          asInt (evalLogosQuerySigma ⟨.int, b⟩ env))
    | ⟨.int, .sub a b⟩, env =>
        .intValue (asInt (evalLogosQuerySigma ⟨.int, a⟩ env) -
          asInt (evalLogosQuerySigma ⟨.int, b⟩ env))
    | ⟨.int, .mul a b⟩, env =>
        .intValue (asInt (evalLogosQuerySigma ⟨.int, a⟩ env) *
          asInt (evalLogosQuerySigma ⟨.int, b⟩ env))
    | ⟨.bool, .not e⟩, env =>
        .boolValue (!(asBool (evalLogosQuerySigma ⟨.bool, e⟩ env)))
    | ⟨.bool, .eqInt a b⟩, env =>
        .boolValue (decide (asInt (evalLogosQuerySigma ⟨.int, a⟩ env) =
          asInt (evalLogosQuerySigma ⟨.int, b⟩ env)))
    | ⟨.bool, .eqBool a b⟩, env =>
        .boolValue (decide (asBool (evalLogosQuerySigma ⟨.bool, a⟩ env) =
          asBool (evalLogosQuerySigma ⟨.bool, b⟩ env)))
    | ⟨.bool, .lt a b⟩, env =>
        .boolValue (decide (asInt (evalLogosQuerySigma ⟨.int, a⟩ env) <
          asInt (evalLogosQuerySigma ⟨.int, b⟩ env)))
    | ⟨.bool, .le a b⟩, env =>
        .boolValue (decide (asInt (evalLogosQuerySigma ⟨.int, a⟩ env) <=
          asInt (evalLogosQuerySigma ⟨.int, b⟩ env)))
    | ⟨.bool, .and terms⟩, env =>
        .boolValue (evalLogosBoolTerms true terms env)
    | ⟨.bool, .or terms⟩, env =>
        .boolValue (evalLogosBoolTerms false terms env)
    | ⟨.int, .iteInt c a b⟩, env =>
        if asBool (evalLogosQuerySigma ⟨.bool, c⟩ env)
        then evalLogosQuerySigma ⟨.int, a⟩ env else evalLogosQuerySigma ⟨.int, b⟩ env
    | ⟨.bool, .iteBool c a b⟩, env =>
        if asBool (evalLogosQuerySigma ⟨.bool, c⟩ env)
        then evalLogosQuerySigma ⟨.bool, a⟩ env else evalLogosQuerySigma ⟨.bool, b⟩ env

  def evalLogosBoolTerms :
      (conjunction : Bool) → List (LLMLang.LogosBinding.QueryTerm .bool) →
      SourceQuerySemantics.Env → Bool
    | conjunction, [], _ => conjunction
    | conjunction, term :: rest, env =>
        if conjunction then
          asBool (evalLogosQuerySigma ⟨.bool, term⟩ env) &&
            evalLogosBoolTerms conjunction rest env
        else
          asBool (evalLogosQuerySigma ⟨.bool, term⟩ env) ||
            evalLogosBoolTerms conjunction rest env
end
termination_by
  evalLogosQuerySigma query _ => sizeOf query
  evalLogosBoolTerms _ terms _ => sizeOf terms
decreasing_by
  all_goals simp_wf [sizeOf]

/--
The adapter preserves mathematical meaning for every well-typed independent
query term and every environment. This theorem is separate from the semantic
core and is kernel checked together with the adapter.
-/
theorem toLogosQueryTerm_preserves_eval {s : ExprSort}
    (term : SourceQuerySemantics.QueryTerm s)
    (env : SourceQuerySemantics.Env) :
    evalLogosQuerySigma ⟨s, toLogosQueryTerm term⟩ env =
      SourceQuerySemantics.evalQuery term env := by
  induction term <;>
    simp_all [toLogosQueryTerm, evalLogosQuerySigma, evalLogosBoolTerms,
      SourceQuerySemantics.evalQuery, asInt, asBool] <;> rfl

end LLMLang.LogosQueryAdapter
