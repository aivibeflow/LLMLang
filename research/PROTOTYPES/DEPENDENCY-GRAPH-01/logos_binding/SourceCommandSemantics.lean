import CheckedSourceSemantics

namespace LLMLang.SourceCommandSemantics

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics

inductive WriteTarget where
  | local (id : VariableId)
  | state (id : VariableId)

def WriteTarget.id : WriteTarget → VariableId
  | .local id | .state id => id

def WriteTarget.role : WriteTarget → DeclarationRole
  | .local _ => .local
  | .state _ => .state

def WriteTarget.permitted (target : WriteTarget) (scope : SourceScope) (sort : ExprSort) : Bool :=
  decide scope.WellFormed &&
    ((lookupDeclaration scope.context target.id).filter (fun declaration =>
      decide (declaration.role = target.role ∧ declaration.sort = sort ∧
        scope.Allows .write declaration))).isSome

theorem WriteTarget.permitted_eq_true {target : WriteTarget} {scope : SourceScope}
    {sort : ExprSort} :
    target.permitted scope sort = true ↔ scope.WellFormed ∧
      ∃ declaration, lookupDeclaration scope.context target.id = some declaration ∧
        declaration.role = target.role ∧ declaration.sort = sort ∧
        scope.Allows .write declaration := by
  simp only [WriteTarget.permitted, Bool.and_eq_true, decide_eq_true_eq,
    Option.isSome_iff_exists, Option.filter_eq_some_iff]

/-- Assignments carry the RHS sort, and branching requires a Boolean expression. -/
inductive Command where
  | skip
  | assign {sort : ExprSort} (target : WriteTarget) (rhs : Expr sort)
  | seq (first second : Command)
  | branch (condition : Expr .bool) (onTrue onFalse : Command)

/-- The final expression is the only return point. -/
structure Program (sort : ExprSort) where
  body : Command
  result : Expr sort

/-- Compute definite initialization while holding declarations and visibility fixed. -/
def Command.check (scope : SourceScope) : Command → Option (List VariableId)
  | .skip => some scope.initialized
  | .assign (sort := sort) target rhs =>
      if target.permitted scope sort && decide (ExpressionWellTyped scope rhs) then
        some (scope.initialized.insert target.id)
      else none
  | .seq first second => do
      let initialized ← first.check scope
      second.check { scope with initialized }
  | .branch condition onTrue onFalse =>
      if ExpressionWellTyped scope condition then do
        let left ← onTrue.check scope
        let right ← onFalse.check scope
        pure (left.filter (fun id => decide (id ∈ right)))
      else none

def Program.check {sort : ExprSort} (program : Program sort) (entry : SourceScope) :
    Option SourceScope :=
  if entry.WellFormed then do
    let initialized ← program.body.check entry
    let exit := { entry with initialized }
    if ExpressionWellTyped exit program.result then some exit else none
  else none

/-- The runtime scope tracks the actual initializations along the chosen path. -/
structure Configuration where
  scope : SourceScope
  env : RuntimeEnv

def Configuration.Valid (configuration : Configuration) : Prop :=
  configuration.scope.WellFormed ∧ configuration.env.Satisfies configuration.scope

def Configuration.write {sort : ExprSort} (configuration : Configuration)
    (target : WriteTarget) (value : Value sort) : Configuration :=
  { scope := { configuration.scope with
      initialized := configuration.scope.initialized.insert target.id }
    env := fun id => if id = target.id then some ⟨sort, value⟩ else configuration.env id }

theorem Configuration.write_preserves_validity {sort : ExprSort}
    {configuration : Configuration} {target : WriteTarget} (value : Value sort)
    (valid : configuration.Valid) (permitted : target.permitted configuration.scope sort = true) :
    (configuration.write target value).Valid := by
  obtain ⟨_, declaration, found, _, sameSort, writable⟩ :=
    WriteTarget.permitted_eq_true.mp permitted
  have sameId := lookupDeclaration_id found
  have visible : target.id ∈ configuration.scope.visible := sameId ▸ writable.1
  obtain ⟨⟨contextValid, visibleDeclared, initializedVisible, requiredInitialized⟩, satisfies⟩ :=
    valid
  refine ⟨⟨contextValid, visibleDeclared, ?_, ?_⟩, ?_⟩
  · intro id initialized
    rcases List.mem_insert_iff.mp initialized with rfl | previous
    · exact visible
    · exact initializedVisible id previous
  · intro entry member inScope required
    exact List.mem_insert_of_mem (requiredInitialized entry member inScope required)
  · intro entry member
    change ((if entry.id = target.id then some ⟨sort, value⟩ else configuration.env entry.id).map
      Sigma.fst) = if entry.id ∈ configuration.scope.initialized.insert target.id then
        some entry.sort else none
    by_cases same : entry.id = target.id
    · have lookup := configuration.scope.context.lookupDeclaration_of_mem contextValid member
      rw [same] at lookup
      have entryEq : entry = declaration := Option.some.inj (lookup.symm.trans found)
      simp [entryEq, sameId, sameSort]
    · simpa [same] using satisfies entry member

/-- Big-step execution of one finite command tree. -/
inductive Executes : Command → Configuration → Configuration → Prop where
  | skip (initial : Configuration) : Executes .skip initial initial
  | assign {sort : ExprSort} {target : WriteTarget} {rhs : Expr sort}
      {initial : Configuration} {value : Value sort}
      (permitted : target.permitted initial.scope sort = true)
      (evaluated : Evaluates initial.scope initial.env rhs value) :
      Executes (.assign target rhs) initial (initial.write target value)
  | seq {first second : Command} {initial middle final : Configuration}
      (firstRun : Executes first initial middle) (secondRun : Executes second middle final) :
      Executes (.seq first second) initial final
  | branchTrue {condition : Expr .bool} {onTrue onFalse : Command}
      {initial final : Configuration}
      (tested : Evaluates initial.scope initial.env condition (.boolValue true))
      (selected : Executes onTrue initial final) :
      Executes (.branch condition onTrue onFalse) initial final
  | branchFalse {condition : Expr .bool} {onTrue onFalse : Command}
      {initial final : Configuration}
      (tested : Evaluates initial.scope initial.env condition (.boolValue false))
      (selected : Executes onFalse initial final) :
      Executes (.branch condition onTrue onFalse) initial final

def Command.execute : Command → Configuration → Option Configuration
  | .skip, initial => some initial
  | .assign (sort := sort) target rhs, initial => do
      if !target.permitted initial.scope sort then none else
        let value ← evaluateChecked initial.scope initial.env rhs
        pure (initial.write target value)
  | .seq first second, initial => do
      let middle ← first.execute initial
      second.execute middle
  | .branch condition onTrue onFalse, initial => do
      let value ← evaluateChecked initial.scope initial.env condition
      if asBool value then onTrue.execute initial else onFalse.execute initial

theorem Executes.computes {command : Command} {initial final : Configuration}
    (run : Executes command initial final) : command.execute initial = some final := by
  induction run <;> simp_all [Command.execute, ← evaluateChecked_eq_some, asBool]

theorem Command.execute_sound {command : Command} {initial final : Configuration}
    (computed : command.execute initial = some final) : Executes command initial final := by
  induction command generalizing initial final with
  | skip =>
    simp only [Command.execute, Option.some.injEq] at computed
    subst final
    exact .skip initial
  | assign target rhs =>
    simp only [Command.execute] at computed
    split at computed
    · contradiction
    · rename_i notRejected
      obtain ⟨value, evaluated, result⟩ := Option.bind_eq_some_iff.mp computed
      cases Option.some.inj result
      exact .assign (by simpa using notRejected) (evaluateChecked_eq_some.mp evaluated)
  | seq first second firstIH secondIH =>
    obtain ⟨middle, ranFirst, ranSecond⟩ := Option.bind_eq_some_iff.mp computed
    exact .seq (firstIH ranFirst) (secondIH ranSecond)
  | branch condition onTrue onFalse trueIH falseIH =>
    obtain ⟨value, tested, ran⟩ := Option.bind_eq_some_iff.mp computed
    cases value with
    | boolValue flag =>
      cases flag
      · exact .branchFalse (evaluateChecked_eq_some.mp tested) (falseIH ran)
      · exact .branchTrue (evaluateChecked_eq_some.mp tested) (trueIH ran)

theorem Command.execute_eq_some {command : Command} {initial final : Configuration} :
    command.execute initial = some final ↔ Executes command initial final :=
  ⟨Command.execute_sound, Executes.computes⟩

theorem Executes.preserves_validity {command : Command} {initial final : Configuration}
    (run : Executes command initial final) (valid : initial.Valid) : final.Valid := by
  induction run with
  | skip => exact valid
  | assign permitted _ => exact Configuration.write_preserves_validity _ valid permitted
  | seq _ _ firstIH secondIH => exact secondIH (firstIH valid)
  | branchTrue _ _ ih | branchFalse _ _ ih => exact ih valid

theorem Executes.deterministic {command : Command} {initial left right : Configuration}
    (first : Executes command initial left) (second : Executes command initial right) :
    left = right :=
  Option.some.inj (first.computes.symm.trans second.computes)

def Program.Executes {sort : ExprSort} (program : Program sort) (initial final : Configuration)
    (result : Value sort) : Prop :=
  (program.check initial.scope).isSome = true ∧ initial.env.Satisfies initial.scope ∧
    SourceCommandSemantics.Executes program.body initial final ∧
    Evaluates final.scope final.env program.result result

def Program.execute {sort : ExprSort} (program : Program sort) (initial : Configuration) :
    Option (Configuration × Value sort) := do
  if !(program.check initial.scope).isSome || !decide (initial.env.Satisfies initial.scope) then
    none
  else
    let final ← program.body.execute initial
    let result ← evaluateChecked final.scope final.env program.result
    pure (final, result)

theorem Program.execute_eq_some {sort : ExprSort} {program : Program sort}
    {initial final : Configuration} {value : Value sort} :
    program.execute initial = some (final, value) ↔ program.Executes initial final value := by
  constructor
  · intro computed
    simp only [Program.execute] at computed
    split at computed
    · contradiction
    · rename_i notRejected
      obtain ⟨state, commandRun, returned⟩ := Option.bind_eq_some_iff.mp computed
      obtain ⟨result, evaluated, pair⟩ := Option.bind_eq_some_iff.mp returned
      cases Option.some.inj pair
      have accepted : (program.check initial.scope).isSome = true ∧
          initial.env.Satisfies initial.scope := by
        simpa [Option.isSome_iff_ne_none] using notRejected
      exact ⟨accepted.1, accepted.2, Command.execute_sound commandRun,
        evaluateChecked_eq_some.mp evaluated⟩
  · rintro ⟨checked, satisfies, commands, returned⟩
    simp [Program.execute, checked, satisfies, commands.computes, evaluateChecked_eq_some.mpr returned]

/-- The final configuration and return value are both unique. -/
theorem Program.Executes.deterministic {sort : ExprSort} {program : Program sort}
    {initial left right : Configuration} {leftValue rightValue : Value sort}
    (first : program.Executes initial left leftValue) (second : program.Executes initial right rightValue) :
    left = right ∧ leftValue = rightValue := by
  have state := SourceCommandSemantics.Executes.deterministic first.2.2.1 second.2.2.1
  subst right
  exact ⟨rfl, evaluation_deterministic first.2.2.2 second.2.2.2⟩

/-- Actual initialization may include slots that were initialized on only one arm. -/
def ScopeCovers (actual required : SourceScope) : Prop :=
  actual.context = required.context ∧ actual.visible = required.visible ∧
    required.initialized ⊆ actual.initialized

private theorem typed_of_coverage {sort : ExprSort} {actual required : SourceScope}
    {expression : Expr sort} (covers : ScopeCovers actual required)
    (typed : ExpressionWellTyped required expression) :
    ExpressionWellTyped actual expression := by
  intro ref mentioned
  obtain ⟨declaration, resolved⟩ := Option.isSome_iff_exists.mp (typed ref mentioned)
  obtain ⟨found, sortMatches, readable⟩ := SourceScope.resolveRead_eq_some.mp resolved
  apply Option.isSome_iff_exists.mpr
  refine ⟨declaration, SourceScope.resolveRead_eq_some.mpr
    ⟨by simpa only [covers.1] using found, sortMatches, ?_⟩⟩
  exact ⟨by simpa only [covers.2.1] using readable.1, covers.2.2 readable.2⟩

private theorem WriteTarget.permitted_of_coverage {target : WriteTarget} {sort : ExprSort}
    {actual required : SourceScope} (covers : ScopeCovers actual required)
    (valid : actual.WellFormed) (permitted : target.permitted required sort = true) :
    target.permitted actual sort = true := by
  obtain ⟨_, declaration, found, role, sortMatches, writable⟩ :=
    WriteTarget.permitted_eq_true.mp permitted
  apply WriteTarget.permitted_eq_true.mpr
  refine ⟨valid, declaration, by simpa only [covers.1] using found, role, sortMatches, ?_⟩
  exact ⟨by simpa only [covers.2.1] using writable.1, writable.2⟩

/-- The checker guarantees execution from every valid state covering its input scope. -/
theorem Command.check_has_execution {command : Command} {required : SourceScope}
    {initialized : List VariableId} {initial : Configuration}
    (checked : command.check required = some initialized)
    (covers : ScopeCovers initial.scope required) (valid : initial.Valid) :
    ∃ final, Executes command initial final ∧
      ScopeCovers final.scope { required with initialized } := by
  induction command generalizing required initialized initial with
  | skip =>
    have same := Option.some.inj checked
    subst initialized
    exact ⟨initial, .skip initial, covers⟩
  | assign target rhs =>
    simp only [Command.check] at checked
    split at checked
    · rename_i accepted
      simp only [Bool.and_eq_true, decide_eq_true_eq] at accepted
      have permits := WriteTarget.permitted_of_coverage covers valid.1 accepted.1
      have typed := typed_of_coverage covers accepted.2
      obtain ⟨value, evaluated⟩ := evaluation_total valid.1 typed valid.2
      have same := Option.some.inj checked
      subst initialized
      refine ⟨initial.write target value, .assign permits evaluated, covers.1, covers.2.1, ?_⟩
      intro id member
      rcases List.mem_insert_iff.mp member with rfl | previous
      · exact List.mem_insert_self
      · exact List.mem_insert_of_mem (covers.2.2 previous)
    · contradiction
  | seq first second firstIH secondIH =>
    obtain ⟨middleInit, checkedFirst, checkedSecond⟩ := Option.bind_eq_some_iff.mp checked
    obtain ⟨middle, ranFirst, middleCovers⟩ := firstIH checkedFirst covers valid
    obtain ⟨final, ranSecond, finalCovers⟩ :=
      secondIH checkedSecond middleCovers (ranFirst.preserves_validity valid)
    exact ⟨final, .seq ranFirst ranSecond, finalCovers⟩
  | branch condition onTrue onFalse trueIH falseIH =>
    simp only [Command.check] at checked
    split at checked
    · rename_i typedCondition
      obtain ⟨left, checkedLeft, rest⟩ := Option.bind_eq_some_iff.mp checked
      obtain ⟨right, checkedRight, joined⟩ := Option.bind_eq_some_iff.mp rest
      have same := Option.some.inj joined
      subst initialized
      obtain ⟨value, tested⟩ := evaluation_total valid.1
        (typed_of_coverage covers typedCondition) valid.2
      cases value with
      | boolValue selected =>
        cases selected
        · obtain ⟨final, ran, finalCovers⟩ := falseIH checkedRight covers valid
          refine ⟨final, .branchFalse tested ran, finalCovers.1, finalCovers.2.1, ?_⟩
          intro _ member
          exact finalCovers.2.2 (of_decide_eq_true (List.mem_filter.mp member).2)
        · obtain ⟨final, ran, finalCovers⟩ := trueIH checkedLeft covers valid
          refine ⟨final, .branchTrue tested ran, finalCovers.1, finalCovers.2.1, ?_⟩
          intro _ member
          exact finalCovers.2.2 (List.mem_filter.mp member).1
    · contradiction

theorem Program.check_details {sort : ExprSort} {program : Program sort}
    {entry exit : SourceScope} (checked : program.check entry = some exit) :
    entry.WellFormed ∧ program.body.check entry = some exit.initialized ∧
      exit = { entry with initialized := exit.initialized } ∧
      ExpressionWellTyped exit program.result := by
  simp only [Program.check] at checked
  split at checked
  · rename_i scopeValid
    obtain ⟨initialized, checkedBody, checkedReturn⟩ := Option.bind_eq_some_iff.mp checked
    split at checkedReturn
    · rename_i typedReturn
      cases Option.some.inj checkedReturn
      exact ⟨scopeValid, checkedBody, rfl, typedReturn⟩
    · contradiction
  · contradiction

/-- Checked execution covers the scope used to type-check the return. -/
theorem Program.checked_execution_covers {sort : ExprSort} {program : Program sort}
    {initial : Configuration} {exit : SourceScope}
    (checked : program.check initial.scope = some exit)
    (satisfies : initial.env.Satisfies initial.scope) :
    ∃ final result, program.Executes initial final result ∧ ScopeCovers final.scope exit := by
  obtain ⟨scopeValid, checkedBody, exitScope, typedReturn⟩ := Program.check_details checked
  have valid : initial.Valid := ⟨scopeValid, satisfies⟩
  obtain ⟨final, commands, covers⟩ :=
    Command.check_has_execution checkedBody ⟨rfl, rfl, fun _ member => member⟩ valid
  have coversExit : ScopeCovers final.scope exit := by
    simpa only [← exitScope] using covers
  have finalValid := commands.preserves_validity valid
  obtain ⟨result, returned⟩ := evaluation_total finalValid.1
    (typed_of_coverage coversExit typedReturn) finalValid.2
  exact ⟨final, result, ⟨by simp [checked], satisfies, commands, returned⟩, coversExit⟩

/-- With valid input slots, every accepted program reaches its final return. -/
theorem Program.checked_execution_exists {sort : ExprSort} {program : Program sort}
    {initial : Configuration} {exit : SourceScope}
    (checked : program.check initial.scope = some exit)
    (satisfies : initial.env.Satisfies initial.scope) :
    ∃ final result, program.Executes initial final result := by
  obtain ⟨final, result, ran, _⟩ := Program.checked_execution_covers checked satisfies
  exact ⟨final, result, ran⟩

end LLMLang.SourceCommandSemantics
