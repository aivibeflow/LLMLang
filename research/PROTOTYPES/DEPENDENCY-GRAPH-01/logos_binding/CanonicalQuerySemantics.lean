import LLMLangLogosBinding
import SourceQuerySemantics

namespace LLMLang.CanonicalQuerySemantics

open LLMLang.LogosBinding
namespace S := LLMLang.SourceQuerySemantics

/-- The canonical wire/query sort mapped to the independent source semantics. -/
def semanticSort : QuerySort → S.ExprSort
  | .int => .int
  | .bool => .bool

/-- A direct mathematical interpretation of the actual typed query AST. -/
def evalCanonical {sort : QuerySort} :
    QueryTerm sort → S.Env → S.Value (semanticSort sort)
  | .intLit n, _ => .intValue n
  | .boolLit b, _ => .boolValue b
  | .intSymbol name, env => env name .int
  | .boolSymbol name, env => env name .bool
  | .not term, env => .boolValue (!(S.asBool (evalCanonical term env)))
  | .neg term, env => .intValue (-(S.asInt (evalCanonical term env)))
  | .add left right, env =>
      .intValue (S.asInt (evalCanonical left env) + S.asInt (evalCanonical right env))
  | .sub left right, env =>
      .intValue (S.asInt (evalCanonical left env) - S.asInt (evalCanonical right env))
  | .mul left right, env =>
      .intValue (S.asInt (evalCanonical left env) * S.asInt (evalCanonical right env))
  | .eqInt left right, env =>
      .boolValue (decide (S.asInt (evalCanonical left env) = S.asInt (evalCanonical right env)))
  | .eqBool left right, env =>
      .boolValue (decide (S.asBool (evalCanonical left env) = S.asBool (evalCanonical right env)))
  | .lt left right, env =>
      .boolValue (decide (S.asInt (evalCanonical left env) < S.asInt (evalCanonical right env)))
  | .le left right, env =>
      .boolValue (decide (S.asInt (evalCanonical left env) <= S.asInt (evalCanonical right env)))
  | .and terms, env =>
      .boolValue (terms.all (fun term => S.asBool (evalCanonical term env)))
  | .or terms, env =>
      .boolValue (terms.any (fun term => S.asBool (evalCanonical term env)))
  | .iteInt condition yes no, env =>
      if S.asBool (evalCanonical condition env)
      then evalCanonical yes env else evalCanonical no env
  | .iteBool condition yes no, env =>
      if S.asBool (evalCanonical condition env)
      then evalCanonical yes env else evalCanonical no env

/--
Translate the actual canonical query AST into the independent semantic query
AST. Multiplication is accepted only when one operand is a literal, exactly
matching the strict QF_LIA decoder's linearity restriction.
-/
def toSemanticQueryTerm {sort : QuerySort} :
    QueryTerm sort → Option (S.QueryTerm (semanticSort sort))
  | .intLit n => some (.intLit n)
  | .boolLit b => some (.boolLit b)
  | .intSymbol name => some (.symbolInt name)
  | .boolSymbol name => some (.symbolBool name)
  | .not term => do
      let term ← toSemanticQueryTerm term
      pure (.not term)
  | .neg term => do
      let term ← toSemanticQueryTerm term
      pure (.neg term)
  | .add left right => do
      let left ← toSemanticQueryTerm left
      let right ← toSemanticQueryTerm right
      pure (.add left right)
  | .sub left right => do
      let left ← toSemanticQueryTerm left
      let right ← toSemanticQueryTerm right
      pure (.sub left right)
  | .mul left right =>
      match left with
      | .intLit k => do
          let right ← toSemanticQueryTerm right
          pure (.mulConst k right)
      | _ =>
          match right with
          | .intLit k => do
              let left ← toSemanticQueryTerm left
              pure (.mulConst k left)
          | _ => none
  | .eqInt left right => do
      let left ← toSemanticQueryTerm left
      let right ← toSemanticQueryTerm right
      pure (.eqInt left right)
  | .eqBool left right => do
      let left ← toSemanticQueryTerm left
      let right ← toSemanticQueryTerm right
      pure (.eqBool left right)
  | .lt left right => do
      let left ← toSemanticQueryTerm left
      let right ← toSemanticQueryTerm right
      pure (.lt left right)
  | .le left right => do
      let left ← toSemanticQueryTerm left
      let right ← toSemanticQueryTerm right
      pure (.le left right)
  | .and terms => do
      let terms ← terms.mapM toSemanticQueryTerm
      pure (.and terms)
  | .or terms => do
      let terms ← terms.mapM toSemanticQueryTerm
      pure (.or terms)
  | .iteInt condition yes no => do
      let condition ← toSemanticQueryTerm condition
      let yes ← toSemanticQueryTerm yes
      let no ← toSemanticQueryTerm no
      pure (.iteInt condition yes no)
  | .iteBool condition yes no => do
      let condition ← toSemanticQueryTerm condition
      let yes ← toSemanticQueryTerm yes
      let no ← toSemanticQueryTerm no
      pure (.iteBool condition yes no)

/--
For every canonical typed query term accepted by the linear fragment, its
direct mathematical interpretation agrees with the independent semantic
query obtained by structural translation. This theorem covers every operator
in the Lean canonical query AST; nonlinear multiplication has no translation.
-/
theorem evalCanonical_eq_evalSemantic
    {sort : QuerySort} (term : QueryTerm sort) (env : S.Env)
    {semanticTerm : S.QueryTerm (semanticSort sort)}
    (h : toSemanticQueryTerm term = some semanticTerm) :
    evalCanonical term env = S.evalQuery semanticTerm env := by
  induction term generalizing semanticTerm <;>
    simp_all [toSemanticQueryTerm, evalCanonical, S.evalQuery,
      S.asInt, S.asBool, semanticSort, Int.mul_comm]

end LLMLang.CanonicalQuerySemantics
