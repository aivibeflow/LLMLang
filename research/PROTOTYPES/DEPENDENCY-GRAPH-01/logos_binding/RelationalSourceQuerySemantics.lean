import SourceQuerySemantics
import LLMLangLogosBinding

namespace LLMLang.RelationalSourceQuerySemantics

open LLMLang.SourceQuerySemantics
open LLMLang.LogosBinding

/-- Which execution of a paired relational query is being represented. -/
inductive RunSide where
  | left
  | right
  deriving DecidableEq, Repr

/-- The canonical name of a source variable in one product-program execution. -/
def relationalSymbol (side : RunSide) (factor name : String) : String :=
  if name == factor then
    name ++ (if side == .left then "_L" else "_R")
  else
    name

/-- The QF_LIA sort corresponding to the source expression sort. -/
def querySortOf : ExprSort → LogosBinding.QuerySort
  | .int => .int
  | .bool => .bool

/--
A product-program environment is represented by one query environment:
the selected factor is renamed per side; all other names are shared.
-/
def sideEnvironment (queryEnv : SourceQuerySemantics.Env)
    (side : RunSide) (factor : String) : SourceQuerySemantics.Env :=
  fun name sort => queryEnv (relationalSymbol side factor name) sort

/--
Translate the source expression independently for the left or right
product-program execution. The selected input is renamed; all other inputs
retain one shared symbol. Multiplication is restricted to a literal constant.
-/
def translateRelationalExpr :
    {s : ExprSort} → (side : RunSide) → (factor : String) →
    Expr s → LogosBinding.QueryTerm (querySortOf s)
  | .int, _, _, .intLit n => .intLit n
  | .bool, _, _, .boolLit b => .boolLit b
  | .int, side, factor, .intVar name =>
      .intSymbol (relationalSymbol side factor name)
  | .bool, side, factor, .boolVar name =>
      .boolSymbol (relationalSymbol side factor name)
  | .int, side, factor, .neg e =>
      .neg (translateRelationalExpr side factor e)
  | .int, side, factor, .add a b =>
      .add (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .int, side, factor, .sub a b =>
      .sub (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .int, side, factor, .mulConst k e =>
      .mul (.intLit k) (translateRelationalExpr side factor e)
  | .bool, side, factor, .not e =>
      .not (translateRelationalExpr side factor e)
  | .bool, side, factor, .eqInt a b =>
      .eqInt (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .eqBool a b =>
      .eqBool (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .lt a b =>
      .lt (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .le a b =>
      .le (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .and a b =>
      .and [translateRelationalExpr side factor a, translateRelationalExpr side factor b]
  | .bool, side, factor, .or a b =>
      .or [translateRelationalExpr side factor a, translateRelationalExpr side factor b]
  | .int, side, factor, .iteInt c a b =>
      .iteInt (translateRelationalExpr side factor c)
        (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .iteBool c a b =>
      .iteBool (translateRelationalExpr side factor c)
        (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)

/-- Mathematical interpretation of the actual typed query AST used by the Lean CPC bridge. -/
def evalCanonicalQuery :
    {s : LogosBinding.QuerySort} →
    LogosBinding.QueryTerm s → SourceQuerySemantics.Env →
    SourceQuerySemantics.Value (match s with | .int => .int | .bool => .bool)
  | .int, .intLit n, _ => .intValue n
  | .bool, .boolLit b, _ => .boolValue b
  | .int, .intSymbol name, env => env name .int
  | .bool, .boolSymbol name, env => env name .bool
  | .bool, .not e, env => .boolValue (!(asBool (evalCanonicalQuery e env)))
  | .int, .neg e, env => .intValue (-(asInt (evalCanonicalQuery e env)))
  | .int, .add a b, env =>
      .intValue (asInt (evalCanonicalQuery a env) + asInt (evalCanonicalQuery b env))
  | .int, .sub a b, env =>
      .intValue (asInt (evalCanonicalQuery a env) - asInt (evalCanonicalQuery b env))
  | .int, .mul a b, env =>
      .intValue (asInt (evalCanonicalQuery a env) * asInt (evalCanonicalQuery b env))
  | .bool, .eqInt a b, env =>
      .boolValue (decide (asInt (evalCanonicalQuery a env) = asInt (evalCanonicalQuery b env)))
  | .bool, .eqBool a b, env =>
      .boolValue (decide (asBool (evalCanonicalQuery a env) = asBool (evalCanonicalQuery b env)))
  | .bool, .lt a b, env =>
      .boolValue (decide (asInt (evalCanonicalQuery a env) < asInt (evalCanonicalQuery b env)))
  | .bool, .le a b, env =>
      .boolValue (decide (asInt (evalCanonicalQuery a env) <= asInt (evalCanonicalQuery b env)))
  | .bool, .and terms, env =>
      .boolValue (terms.all (fun term => asBool (evalCanonicalQuery term env)))
  | .bool, .or terms, env =>
      .boolValue (terms.any (fun term => asBool (evalCanonicalQuery term env)))
  | .int, .iteInt c a b, env =>
      if asBool (evalCanonicalQuery c env) then evalCanonicalQuery a env else evalCanonicalQuery b env
  | .bool, .iteBool c a b, env =>
      if asBool (evalCanonicalQuery c env) then evalCanonicalQuery a env else evalCanonicalQuery b env
termination_by term => sizeOf term
decreasing_by all_goals simp_wf

/--
The actual LogosBinding.QueryTerm translation preserves the source expression
value for each side of the product program and every query environment.
This theorem is kernel-checked.
-/
theorem translateRelationalExpr_correct
    {s : ExprSort} (side : RunSide) (factor : String)
    (e : Expr s) (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuery (translateRelationalExpr side factor e) queryEnv =
      evalExpr e (sideEnvironment queryEnv side factor) := by
  induction e <;>
    simp [translateRelationalExpr, evalCanonicalQuery, sideEnvironment,
      relationalSymbol, querySortOf, asInt, asBool, *] <;> rfl

/-- Every non-selected input is represented by exactly the same symbol on both sides. -/
theorem nonFactorInputsAreShared
    (queryEnv : SourceQuerySemantics.Env) (factor name : String)
    (sort : ExprSort) (different : name ≠ factor) :
    sideEnvironment queryEnv .left factor name sort =
      sideEnvironment queryEnv .right factor name sort := by
  simp [sideEnvironment, relationalSymbol, different]

/-- The selected input is represented by distinct left/right symbols. -/
theorem selectedFactorLeftBinding
    (queryEnv : SourceQuerySemantics.Env) (factor : String) (sort : ExprSort) :
    sideEnvironment queryEnv .left factor factor sort =
      queryEnv (factor ++ "_L") sort := by
  simp [sideEnvironment, relationalSymbol]

theorem selectedFactorRightBinding
    (queryEnv : SourceQuerySemantics.Env) (factor : String) (sort : ExprSort) :
    sideEnvironment queryEnv .right factor factor sort =
      queryEnv (factor ++ "_R") sort := by
  simp [sideEnvironment, relationalSymbol]

/-- Boolean result indicating whether two source values of the same sort differ. -/
def sourceValuesDiffer :
    (sort : ExprSort) → Value sort → Value sort → Bool
  | .int, .intValue left, .intValue right => decide (left ≠ right)
  | .bool, .boolValue left, .boolValue right => decide (left ≠ right)

/-- Build the factor-difference assumption from the actual selected-factor symbols. -/
def factorDifference (sort : ExprSort) (factor : String) : LogosBinding.QueryTerm .bool :=
  match sort with
  | .int =>
      .not (.eqInt (.intSymbol (factor ++ "_L")) (.intSymbol (factor ++ "_R")))
  | .bool =>
      .not (.eqBool (.boolSymbol (factor ++ "_L")) (.boolSymbol (factor ++ "_R")))

/-- Build the observation-difference assumption from the two translated executions. -/
def observationDifference :
    (sort : ExprSort) →
    LogosBinding.QueryTerm (querySortOf sort) →
    LogosBinding.QueryTerm (querySortOf sort) →
    LogosBinding.QueryTerm .bool
  | .int, left, right => .not (.eqInt left right)
  | .bool, left, right => .not (.eqBool left right)

/-- The factor-difference formula denotes precisely inequality of source inputs. -/
theorem factorDifference_correct
    (sort : ExprSort) (factor : String) (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuery (factorDifference sort factor) queryEnv =
      .boolValue (sourceValuesDiffer sort
        (sideEnvironment queryEnv .left factor factor sort)
        (sideEnvironment queryEnv .right factor factor sort)) := by
  cases sort <;>
    simp [factorDifference, evalCanonicalQuery, sourceValuesDiffer,
      sideEnvironment, relationalSymbol, asInt, asBool]

/--
The observation-difference formula denotes precisely inequality of the two
source expression results. This is the core paired-execution correspondence.
-/
theorem observationDifference_correct
    {s : ExprSort} (factor : String) (e : Expr s)
    (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuery
      (observationDifference s
        (translateRelationalExpr .left factor e)
        (translateRelationalExpr .right factor e))
      queryEnv =
      .boolValue (sourceValuesDiffer s
        (evalExpr e (sideEnvironment queryEnv .left factor))
        (evalExpr e (sideEnvironment queryEnv .right factor))) := by
  rw [translateRelationalExpr_correct, translateRelationalExpr_correct]
  cases s <;>
    simp [observationDifference, evalCanonicalQuery, sourceValuesDiffer,
      asInt, asBool]

/--
The two assumptions of the expression-level relational query are sound:
the first captures distinct selected inputs, and the second captures distinct
source observations. This is not yet a theorem about command sequences,
mutable program state, the Python encoder, or solver proof artifacts.
-/
def relationalAssumptions {s : ExprSort}
    (factor : String) (e : Expr s) : List (LogosBinding.QueryTerm .bool) :=
  [factorDifference s factor,
   observationDifference s
     (translateRelationalExpr .left factor e)
     (translateRelationalExpr .right factor e)]

theorem relationalAssumptions_correct
    {s : ExprSort} (factor : String) (e : Expr s)
    (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuery (factorDifference s factor) queryEnv =
      .boolValue (sourceValuesDiffer s
        (sideEnvironment queryEnv .left factor factor s)
        (sideEnvironment queryEnv .right factor factor s)) ∧
    evalCanonicalQuery
      (observationDifference s
        (translateRelationalExpr .left factor e)
        (translateRelationalExpr .right factor e))
      queryEnv =
      .boolValue (sourceValuesDiffer s
        (evalExpr e (sideEnvironment queryEnv .left factor))
        (evalExpr e (sideEnvironment queryEnv .right factor))) := by
  exact And.intro
    (factorDifference_correct s factor queryEnv)
    (observationDifference_correct factor e queryEnv)

end LLMLang.RelationalSourceQuerySemantics
