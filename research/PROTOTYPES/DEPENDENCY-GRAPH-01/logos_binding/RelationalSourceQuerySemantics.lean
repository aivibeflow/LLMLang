import SourceQuerySemantics

namespace LLMLang.RelationalSourceQuerySemantics

open LLMLang.SourceQuerySemantics

/-- Which execution of a paired relational query is being represented. -/
inductive RunSide where
  | left
  | right
  deriving DecidableEq, Repr

/-- The canonical name of a source variable in one product-program execution. -/
def relationalSymbol (side : RunSide) (factor name : String) : String :=
  if name = factor then
    name ++ (match side with | .left => "_L" | .right => "_R")
  else
    name

/-- The QF_LIA sort corresponding to the source expression sort. -/
abbrev querySortOf : ExprSort → ExprSort := id

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
    Expr s → SourceQuerySemantics.QueryTerm (querySortOf s)
  | .int, _, _, .intLit n => .intLit n
  | .bool, _, _, .boolLit b => .boolLit b
  | .int, side, factor, .intVar name =>
      .symbolInt (relationalSymbol side factor name)
  | .bool, side, factor, .boolVar name =>
      .symbolBool (relationalSymbol side factor name)
  | .int, side, factor, .neg e =>
      .neg (translateRelationalExpr side factor e)
  | .int, side, factor, .add a b =>
      .add (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .int, side, factor, .sub a b =>
      .sub (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .int, side, factor, .mulConst k e =>
      .mulConst k (translateRelationalExpr side factor e)
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
      .and (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .or a b =>
      .or (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .int, side, factor, .iteInt c a b =>
      .iteInt (translateRelationalExpr side factor c)
        (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)
  | .bool, side, factor, .iteBool c a b =>
      .iteBool (translateRelationalExpr side factor c)
        (translateRelationalExpr side factor a) (translateRelationalExpr side factor b)

/-- Convert the canonical query sort back to the corresponding source value sort. -/
abbrev querySortToExprSort : ExprSort → ExprSort := id

/-- Interpret the independent query IR using its own evaluator. -/
def evalCanonicalQuerySigma :
    (query : Σ s : ExprSort, SourceQuerySemantics.QueryTerm s) →
    SourceQuerySemantics.Env →
    SourceQuerySemantics.Value (querySortToExprSort query.1)
  | ⟨sort, term⟩, env => SourceQuerySemantics.evalQuery term env

/-- Evaluate a typed independent query term in the source/query environment. -/
def evalCanonicalQuery {s : ExprSort}
    (term : SourceQuerySemantics.QueryTerm s)
    (env : SourceQuerySemantics.Env) :
    SourceQuerySemantics.Value (querySortToExprSort s) :=
  SourceQuerySemantics.evalQuery term env

/--
The independent query-IR translation preserves the source expression
value for each side of the product program and every query environment.
This theorem is kernel-checked.
-/
theorem translateRelationalExpr_correct
    {s : ExprSort} (side : RunSide) (factor : String)
    (e : Expr s) (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuerySigma ⟨querySortOf s, translateRelationalExpr side factor e⟩ queryEnv =
      evalExpr e (sideEnvironment queryEnv side factor) := by
  induction e <;>
    simp_all [translateRelationalExpr, evalCanonicalQuerySigma,
      evalExpr, sideEnvironment, relationalSymbol, querySortOf,
      querySortToExprSort] <;> simp [asInt]

/--
Canonical QF_LIA input naming used by qf_lia_profile.py:
source names are sorted first, then assigned i_0, i_1, ...; only the
selected factor is split into the _L and _R symbols.
-/
def canonicalBaseSymbol (inputNames : List String) (name : String) : String :=
  "i_" ++ toString (inputNames.idxOf name)

def canonicalRelationalSymbol (inputNames : List String)
    (side : RunSide) (factor name : String) : String :=
  let base := canonicalBaseSymbol inputNames name
  if name == factor then
    base ++ (match side with | .left => "_L" | .right => "_R")
  else
    base

/-- Product-program environment indexed by the canonical wire symbols. -/
def canonicalSideEnvironment (queryEnv : SourceQuerySemantics.Env)
    (inputNames : List String) (side : RunSide) (factor : String) :
    SourceQuerySemantics.Env :=
  fun name sort => queryEnv (canonicalRelationalSymbol inputNames side factor name) sort

/-- Translate an expression using the exact indexed names emitted by the Python QF_LIA exporter. -/
def translateCanonicalRelationalExpr :
    {s : ExprSort} → (inputNames : List String) → (side : RunSide) →
    (factor : String) → Expr s → SourceQuerySemantics.QueryTerm (querySortOf s)
  | .int, _, _, _, .intLit n => .intLit n
  | .bool, _, _, _, .boolLit b => .boolLit b
  | .int, inputNames, side, factor, .intVar name =>
      .symbolInt (canonicalRelationalSymbol inputNames side factor name)
  | .bool, inputNames, side, factor, .boolVar name =>
      .symbolBool (canonicalRelationalSymbol inputNames side factor name)
  | .int, inputNames, side, factor, .neg e =>
      .neg (translateCanonicalRelationalExpr inputNames side factor e)
  | .int, inputNames, side, factor, .add a b =>
      .add (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .int, inputNames, side, factor, .sub a b =>
      .sub (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .int, inputNames, side, factor, .mulConst k e =>
      .mulConst k (translateCanonicalRelationalExpr inputNames side factor e)
  | .bool, inputNames, side, factor, .not e =>
      .not (translateCanonicalRelationalExpr inputNames side factor e)
  | .bool, inputNames, side, factor, .eqInt a b =>
      .eqInt (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .bool, inputNames, side, factor, .eqBool a b =>
      .eqBool (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .bool, inputNames, side, factor, .lt a b =>
      .lt (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .bool, inputNames, side, factor, .le a b =>
      .le (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .bool, inputNames, side, factor, .and a b =>
      .and (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .bool, inputNames, side, factor, .or a b =>
      .or (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .int, inputNames, side, factor, .iteInt c a b =>
      .iteInt (translateCanonicalRelationalExpr inputNames side factor c)
        (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)
  | .bool, inputNames, side, factor, .iteBool c a b =>
      .iteBool (translateCanonicalRelationalExpr inputNames side factor c)
        (translateCanonicalRelationalExpr inputNames side factor a)
        (translateCanonicalRelationalExpr inputNames side factor b)

/--
The actual canonical-name translation into the independent query IR preserves
the source expression value for each side and every query environment.
-/
theorem translateCanonicalRelationalExpr_correct
    {s : ExprSort} (inputNames : List String) (side : RunSide)
    (factor : String) (e : Expr s) (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuerySigma
      ⟨querySortOf s, translateCanonicalRelationalExpr inputNames side factor e⟩
      queryEnv =
      evalExpr e (canonicalSideEnvironment queryEnv inputNames side factor) := by
  induction e <;>
    simp_all [translateCanonicalRelationalExpr, evalCanonicalQuerySigma,
      evalExpr, canonicalSideEnvironment, canonicalRelationalSymbol, canonicalBaseSymbol,
      querySortOf, querySortToExprSort] <;> simp [asInt]

/-- Every non-selected input is represented by exactly the same symbol on both sides. -/
theorem nonFactorInputsAreShared
    (queryEnv : SourceQuerySemantics.Env) (factor name : String)
    (sort : ExprSort) (different : name ≠ factor) :
    sideEnvironment queryEnv .left factor name sort =
      sideEnvironment queryEnv .right factor name sort := by
  change queryEnv (relationalSymbol .left factor name) sort =
    queryEnv (relationalSymbol .right factor name) sort
  have leftName : relationalSymbol .left factor name = name := by
    simp [relationalSymbol, different]
  have rightName : relationalSymbol .right factor name = name := by
    simp [relationalSymbol, different]
  rw [leftName, rightName]

/-- The selected input is represented by distinct left/right symbols. -/
theorem selectedFactorLeftBinding
    (queryEnv : SourceQuerySemantics.Env) (factor : String) (sort : ExprSort) :
    sideEnvironment queryEnv .left factor factor sort =
      queryEnv (factor ++ "_L") sort := by
  change queryEnv (relationalSymbol .left factor factor) sort = queryEnv (factor ++ "_L") sort
  simp [relationalSymbol]

theorem selectedFactorRightBinding
    (queryEnv : SourceQuerySemantics.Env) (factor : String) (sort : ExprSort) :
    sideEnvironment queryEnv .right factor factor sort =
      queryEnv (factor ++ "_R") sort := by
  change queryEnv (relationalSymbol .right factor factor) sort = queryEnv (factor ++ "_R") sort
  simp [relationalSymbol]

/-- Boolean result indicating whether two source values of the same sort differ. -/
def sourceValuesDiffer :
    (sort : ExprSort) → Value sort → Value sort → Bool
  | .int, left, right => decide (asInt left ≠ asInt right)
  | .bool, left, right => decide (asBool left ≠ asBool right)

theorem decide_ne_eq_not_decide_eq {α : Type} [DecidableEq α] (left right : α) :
    decide (left ≠ right) = !(decide (left = right)) := by
  cases h : decide (left = right) <;> simp_all

/-- Build the factor-difference assumption from the actual selected-factor symbols. -/
def factorDifference (sort : ExprSort) (factor : String) : SourceQuerySemantics.QueryTerm .bool :=
  match sort with
  | .int =>
      .not (.eqInt (.symbolInt (factor ++ "_L")) (.symbolInt (factor ++ "_R")))
  | .bool =>
      .not (.eqBool (.symbolBool (factor ++ "_L")) (.symbolBool (factor ++ "_R")))

/-- Build the observation-difference assumption from the two translated executions. -/
def observationDifference :
    (sort : ExprSort) →
    SourceQuerySemantics.QueryTerm (querySortOf sort) →
    SourceQuerySemantics.QueryTerm (querySortOf sort) →
    SourceQuerySemantics.QueryTerm .bool
  | .int, left, right => .not (.eqInt left right)
  | .bool, left, right => .not (.eqBool left right)

/-- The factor-difference formula denotes precisely inequality of source inputs. -/
theorem factorDifference_correct
    (sort : ExprSort) (factor : String) (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuerySigma ⟨.bool, factorDifference sort factor⟩ queryEnv =
      .boolValue (sourceValuesDiffer sort
        (sideEnvironment queryEnv .left factor factor sort)
        (sideEnvironment queryEnv .right factor factor sort)) := by
  cases sort <;>
    simp [factorDifference, evalCanonicalQuerySigma, sourceValuesDiffer,
      sideEnvironment, relationalSymbol, querySortToExprSort, asInt, asBool,
      decide_ne_eq_not_decide_eq]

/--
The observation-difference formula denotes precisely inequality of the two
source expression results. This is the core paired-execution correspondence.
-/
theorem observationDifference_correct
    {s : ExprSort} (factor : String) (e : Expr s)
    (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuerySigma ⟨.bool,
      observationDifference s
        (translateRelationalExpr .left factor e)
        (translateRelationalExpr .right factor e)⟩
      queryEnv =
      .boolValue (sourceValuesDiffer s
        (evalExpr e (sideEnvironment queryEnv .left factor))
        (evalExpr e (sideEnvironment queryEnv .right factor))) := by
  cases s with
  | int =>
      unfold observationDifference
      conv =>
        lhs
        rw [evalCanonicalQuerySigma]
      conv =>
        lhs
        arg 1
        arg 1
        arg 1
        rw [evalCanonicalQuerySigma]
      simp only [asBool]
      apply congrArg Value.boolValue
      have hleft :
          evalCanonicalQuerySigma ⟨.int, translateRelationalExpr .left factor e⟩ queryEnv =
            evalExpr e (sideEnvironment queryEnv .left factor) := by
        simpa [querySortOf] using
          (translateRelationalExpr_correct .left factor e queryEnv)
      have hright :
          evalCanonicalQuerySigma ⟨.int, translateRelationalExpr .right factor e⟩ queryEnv =
            evalExpr e (sideEnvironment queryEnv .right factor) := by
        simpa [querySortOf] using
          (translateRelationalExpr_correct .right factor e queryEnv)
      rw [hleft, hright]
      exact (decide_ne_eq_not_decide_eq _ _).symm
  | bool =>
      unfold observationDifference
      conv =>
        lhs
        rw [evalCanonicalQuerySigma]
      conv =>
        lhs
        arg 1
        arg 1
        arg 1
        rw [evalCanonicalQuerySigma]
      simp only [asBool]
      apply congrArg Value.boolValue
      have hleft :
          evalCanonicalQuerySigma ⟨.bool, translateRelationalExpr .left factor e⟩ queryEnv =
            evalExpr e (sideEnvironment queryEnv .left factor) := by
        simpa [querySortOf] using
          (translateRelationalExpr_correct .left factor e queryEnv)
      have hright :
          evalCanonicalQuerySigma ⟨.bool, translateRelationalExpr .right factor e⟩ queryEnv =
            evalExpr e (sideEnvironment queryEnv .right factor) := by
        simpa [querySortOf] using
          (translateRelationalExpr_correct .right factor e queryEnv)
      rw [hleft, hright]
      exact (decide_ne_eq_not_decide_eq _ _).symm

/--
The two assumptions of the expression-level relational query are sound:
the first captures distinct selected inputs, and the second captures distinct
source observations. This is not yet a theorem about command sequences,
mutable program state, the Python encoder, or solver proof artifacts.
-/
def relationalAssumptions {s : ExprSort}
    (factorSort : ExprSort) (factor : String) (e : Expr s) :
    List (SourceQuerySemantics.QueryTerm .bool) :=
  [factorDifference factorSort factor,
   observationDifference s
     (translateRelationalExpr .left factor e)
     (translateRelationalExpr .right factor e)]

theorem relationalAssumptions_correct
    {s : ExprSort} (factorSort : ExprSort) (factor : String) (e : Expr s)
    (queryEnv : SourceQuerySemantics.Env) :
    evalCanonicalQuerySigma ⟨.bool, factorDifference factorSort factor⟩ queryEnv =
      .boolValue (sourceValuesDiffer factorSort
        (sideEnvironment queryEnv .left factor factor factorSort)
        (sideEnvironment queryEnv .right factor factor factorSort)) ∧
    evalCanonicalQuerySigma ⟨.bool,
      observationDifference s
        (translateRelationalExpr .left factor e)
        (translateRelationalExpr .right factor e)⟩
      queryEnv =
      .boolValue (sourceValuesDiffer s
        (evalExpr e (sideEnvironment queryEnv .left factor))
        (evalExpr e (sideEnvironment queryEnv .right factor))) := by
  exact And.intro
    (factorDifference_correct factorSort factor queryEnv)
    (observationDifference_correct factor e queryEnv)

end LLMLang.RelationalSourceQuerySemantics
