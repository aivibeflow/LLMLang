import SourceSyntax

namespace LLMLang.CheckedSourceSemantics

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax

/-- Static references include both arms of a conditional. -/
def expressionReads : {s : ExprSort} → Expr s → List Reference
  | _, .intLit _ => []
  | _, .boolLit _ => []
  | _, .intVar name => [⟨name, .int⟩]
  | _, .boolVar name => [⟨name, .bool⟩]
  | _, .neg e => expressionReads e
  | _, .add a b => expressionReads a ++ expressionReads b
  | _, .sub a b => expressionReads a ++ expressionReads b
  | _, .mulConst _ e => expressionReads e
  | _, .not e => expressionReads e
  | _, .eqInt a b => expressionReads a ++ expressionReads b
  | _, .eqBool a b => expressionReads a ++ expressionReads b
  | _, .lt a b => expressionReads a ++ expressionReads b
  | _, .le a b => expressionReads a ++ expressionReads b
  | _, .and a b => expressionReads a ++ expressionReads b
  | _, .or a b => expressionReads a ++ expressionReads b
  | _, .iteInt c a b => expressionReads c ++ expressionReads a ++ expressionReads b
  | _, .iteBool c a b => expressionReads c ++ expressionReads a ++ expressionReads b

def querySymbols : {s : ExprSort} → QueryTerm s → List Reference
  | _, .intLit _ => []
  | _, .boolLit _ => []
  | _, .symbolInt name => [⟨name, .int⟩]
  | _, .symbolBool name => [⟨name, .bool⟩]
  | _, .neg e => querySymbols e
  | _, .add a b => querySymbols a ++ querySymbols b
  | _, .sub a b => querySymbols a ++ querySymbols b
  | _, .mulConst _ e => querySymbols e
  | _, .not e => querySymbols e
  | _, .eqInt a b => querySymbols a ++ querySymbols b
  | _, .eqBool a b => querySymbols a ++ querySymbols b
  | _, .lt a b => querySymbols a ++ querySymbols b
  | _, .le a b => querySymbols a ++ querySymbols b
  | _, .and a b => querySymbols a ++ querySymbols b
  | _, .or a b => querySymbols a ++ querySymbols b
  | _, .iteInt c a b => querySymbols c ++ querySymbols a ++ querySymbols b
  | _, .iteBool c a b => querySymbols c ++ querySymbols a ++ querySymbols b

theorem translateExpr_symbols {s : ExprSort} (expression : Expr s) :
    querySymbols (translateExpr expression) = expressionReads expression := by
  induction expression <;> simp [querySymbols, translateExpr, expressionReads, *]

/-- Operator and result sorts come from the indexed AST. Reads also need resolution. -/
def ExpressionWellTyped {s : ExprSort} (scope : SourceScope) (expression : Expr s) : Prop :=
  ∀ ref ∈ expressionReads expression, (scope.resolveRead ref).isSome = true

instance {s : ExprSort} (scope : SourceScope) (expression : Expr s) :
    Decidable (ExpressionWellTyped scope expression) :=
  List.decidableBAll (fun ref => (scope.resolveRead ref).isSome = true) (expressionReads expression)

def QueryWellTyped {s : ExprSort} (scope : SourceScope) (term : QueryTerm s) : Prop :=
  ∀ ref ∈ querySymbols term, (scope.resolveRead ref).isSome = true

theorem translateExpr_preserves_typing {s : ExprSort} {scope : SourceScope}
    {expression : Expr s} (typed : ExpressionWellTyped scope expression) :
    QueryWellTyped scope (translateExpr expression) := by
  simpa only [QueryWellTyped, translateExpr_symbols, ExpressionWellTyped] using typed

/-- Translate an expression only once its context and static reads are checked. -/
def checkedTranslate {s : ExprSort} (scope : SourceScope) (expression : Expr s) :
    Option (QueryTerm s) :=
  if scope.WellFormed ∧ ExpressionWellTyped scope expression then
    some (translateExpr expression)
  else none

theorem checkedTranslate_eq_some {s : ExprSort} {scope : SourceScope}
    {expression : Expr s} {term : QueryTerm s} :
    checkedTranslate scope expression = some term ↔
      scope.WellFormed ∧ ExpressionWellTyped scope expression ∧
        translateExpr expression = term := by
  by_cases checked : scope.WellFormed ∧ ExpressionWellTyped scope expression
  · simp [checkedTranslate, checked]
  · simp [checkedTranslate, checked, ← and_assoc]

/-- Every accepted query symbol denotes a declaration with the same stable ID and sort. -/
theorem checkedTranslate_binds_symbol {s : ExprSort} {scope : SourceScope}
    {expression : Expr s} {term : QueryTerm s}
    (translated : checkedTranslate scope expression = some term)
    {ref : Reference} (mentioned : ref ∈ querySymbols term) :
    ∃ declaration, scope.context.lookupName ref.name = some declaration ∧
      lookupDeclaration scope.context declaration.id = some declaration ∧
      declaration.sourceName = ref.name ∧ declaration.sort = ref.sort ∧
      scope.Allows .read declaration := by
  obtain ⟨scopeValid, typed, rfl⟩ := checkedTranslate_eq_some.mp translated
  have termTyped := translateExpr_preserves_typing typed
  obtain ⟨declaration, read⟩ := Option.isSome_iff_exists.mp (termTyped ref mentioned)
  obtain ⟨found, sort, allowed⟩ := SourceScope.resolveRead_eq_some.mp read
  exact ⟨declaration, found, scope.context.lookupName_binds_identity scopeValid.1 found,
    scope.context.lookupName_spelling found, sort, allowed⟩

/-- Runtime slots are keyed by stable ID and carry their actual sort with the value. -/
abbrev RuntimeEnv := VariableId → Option (Σ s : ExprSort, Value s)

def RuntimeEnv.lookup (env : RuntimeEnv) (id : VariableId) (sort : ExprSort) :
    Option (Value sort) :=
  match env id with
  | none => none
  | some ⟨actual, value⟩ => if same : actual = sort then some (same ▸ value) else none

theorem RuntimeEnv.lookup_some_of_sort {env : RuntimeEnv} {id : VariableId} {sort : ExprSort}
    (stored : (env id).map Sigma.fst = some sort) :
    ∃ value, env.lookup id sort = some value := by
  cases slot : env id with
  | none => simp [slot] at stored
  | some binding =>
    obtain ⟨actual, value⟩ := binding
    simp [slot] at stored
    subst actual
    exact ⟨value, by simp [RuntimeEnv.lookup, slot]⟩

/-- Initialized declarations have exactly their declared sort. Other declared slots are absent. -/
def RuntimeEnv.Satisfies (env : RuntimeEnv) (scope : SourceScope) : Prop :=
  ∀ declaration ∈ scope.context.entries,
    (env declaration.id).map Sigma.fst =
      if declaration.id ∈ scope.initialized then some declaration.sort else none

instance (env : RuntimeEnv) (scope : SourceScope) : Decidable (env.Satisfies scope) := by
  unfold RuntimeEnv.Satisfies
  exact List.decidableBAll _ _

def RuntimeEnv.read (env : RuntimeEnv) (scope : SourceScope) (ref : Reference) :
    Option (Value ref.sort) := do
  let declaration ← scope.resolveRead ref
  env.lookup declaration.id ref.sort

theorem RuntimeEnv.read_available {s : ExprSort} {scope : SourceScope}
    {expression : Expr s} {env : RuntimeEnv}
    (typed : ExpressionWellTyped scope expression) (satisfies : env.Satisfies scope)
    {ref : Reference} (mentioned : ref ∈ expressionReads expression) :
    ∃ value, env.read scope ref = some value := by
  obtain ⟨declaration, resolved⟩ := Option.isSome_iff_exists.mp (typed ref mentioned)
  obtain ⟨found, sort, allowed⟩ := SourceScope.resolveRead_eq_some.mp resolved
  have stored := satisfies declaration (scope.context.lookupName_mem found)
  rw [ite_eq_left allowed.2, sort] at stored
  obtain ⟨value, lookup⟩ := RuntimeEnv.lookup_some_of_sort stored
  exact ⟨value, by simp [RuntimeEnv.read, resolved, lookup]⟩

/-- The mathematical evaluator only depends on the expression's static read set. -/
theorem evalExpr_agrees_on_reads {s : ExprSort} (expression : Expr s) (left right : Env)
    (agrees : ∀ ref ∈ expressionReads expression, left ref.name ref.sort = right ref.name ref.sort) :
    evalExpr expression left = evalExpr expression right := by
  induction expression <;> simp_all [expressionReads, evalExpr]

/-- Agreement between a total mathematical environment and actual typed reads. -/
def ExtendsReads {s : ExprSort} (scope : SourceScope) (env : RuntimeEnv)
    (expression : Expr s) (extension : Env) : Prop :=
  ∀ ref ∈ expressionReads expression,
    env.read scope ref = some (extension ref.name ref.sort)

/-- Complete the mathematical evaluator's environment outside the checked reads. -/
def extendEnvironment (scope : SourceScope) (env : RuntimeEnv) (fallback : Env) : Env :=
  fun name sort => (env.read scope ⟨name, sort⟩).getD (fallback name sort)

theorem extendEnvironment_agrees {s : ExprSort} {scope : SourceScope}
    {expression : Expr s} {env : RuntimeEnv}
    (typed : ExpressionWellTyped scope expression) (satisfies : env.Satisfies scope)
    (fallback : Env) :
    ExtendsReads scope env expression (extendEnvironment scope env fallback) := by
  intro ref mentioned
  obtain ⟨value, read⟩ := RuntimeEnv.read_available typed satisfies mentioned
  cases ref
  simp [extendEnvironment, read]

/-- Agreement on concrete reads makes the choice of total extension immaterial. -/
theorem evalExpr_eq_of_extensions {s : ExprSort} {scope : SourceScope} {env : RuntimeEnv}
    {expression : Expr s} {left right : Env}
    (leftAgrees : ExtendsReads scope env expression left)
    (rightAgrees : ExtendsReads scope env expression right) :
    evalExpr expression left = evalExpr expression right :=
  evalExpr_agrees_on_reads expression left right (fun ref mentioned =>
    Option.some.inj ((leftAgrees ref mentioned).symm.trans (rightAgrees ref mentioned)))

/-- Evaluation relates a scoped expression to the result of any agreeing completion. -/
def Evaluates {s : ExprSort} (scope : SourceScope) (env : RuntimeEnv)
    (expression : Expr s) (value : Value s) : Prop :=
  scope.WellFormed ∧ ExpressionWellTyped scope expression ∧ env.Satisfies scope ∧
    ∃ extension : Env, ExtendsReads scope env expression extension ∧
      evalExpr expression extension = value

private def zeroEnvironment : Env
  | _, .int => .intValue 0
  | _, .bool => .boolValue false

theorem evaluation_total {s : ExprSort} {scope : SourceScope} {env : RuntimeEnv}
    {expression : Expr s} (valid : scope.WellFormed)
    (typed : ExpressionWellTyped scope expression) (satisfies : env.Satisfies scope) :
    ∃ value, Evaluates scope env expression value := by
  let extension := extendEnvironment scope env zeroEnvironment
  exact ⟨evalExpr expression extension, valid, typed, satisfies, extension,
    extendEnvironment_agrees typed satisfies zeroEnvironment, rfl⟩

theorem evaluation_deterministic {s : ExprSort} {scope : SourceScope} {env : RuntimeEnv}
    {expression : Expr s} {left right : Value s}
    (first : Evaluates scope env expression left) (second : Evaluates scope env expression right) :
    left = right := by
  obtain ⟨_, _, _, leftEnv, leftAgrees, leftResult⟩ := first
  obtain ⟨_, _, _, rightEnv, rightAgrees, rightResult⟩ := second
  exact leftResult.symm.trans
    ((evalExpr_eq_of_extensions leftAgrees rightAgrees).trans rightResult)

/-- Reject invalid contexts, expressions and runtime slots before evaluating. -/
def evaluateChecked {s : ExprSort} (scope : SourceScope) (env : RuntimeEnv)
    (expression : Expr s) : Option (Value s) :=
  if scope.WellFormed ∧ ExpressionWellTyped scope expression ∧ env.Satisfies scope then
    some (evalExpr expression (extendEnvironment scope env zeroEnvironment))
  else none

theorem evaluateChecked_eq_some {s : ExprSort} {scope : SourceScope} {env : RuntimeEnv}
    {expression : Expr s} {value : Value s} :
    evaluateChecked scope env expression = some value ↔ Evaluates scope env expression value := by
  constructor
  · intro result
    unfold evaluateChecked at result
    split at result
    · rename_i checked
      exact ⟨checked.1, checked.2.1, checked.2.2, _,
        extendEnvironment_agrees checked.2.1 checked.2.2 zeroEnvironment, Option.some.inj result⟩
    · contradiction
  · rintro ⟨valid, typed, satisfies, extension, agrees, result⟩
    have same := evalExpr_eq_of_extensions
      (extendEnvironment_agrees typed satisfies zeroEnvironment) agrees
    simp [evaluateChecked, valid, typed, satisfies, same, result]

/-- The query denotes the uniquely defined source result in every agreeing environment. -/
theorem checkedTranslate_preserves_evaluation {s : ExprSort}
    {scope : SourceScope} {env : RuntimeEnv} {expression : Expr s}
    {term : QueryTerm s} {value : Value s} {queryEnv : Env}
    (translated : checkedTranslate scope expression = some term)
    (evaluated : Evaluates scope env expression value)
    (agrees : ExtendsReads scope env expression queryEnv) :
    evalQuery term queryEnv = value := by
  obtain ⟨_, _, rfl⟩ := checkedTranslate_eq_some.mp translated
  obtain ⟨_, _, _, sourceEnv, sourceAgrees, result⟩ := evaluated
  rw [translateExpr_preserves_eval]
  exact (evalExpr_eq_of_extensions agrees sourceAgrees).trans result

end LLMLang.CheckedSourceSemantics
