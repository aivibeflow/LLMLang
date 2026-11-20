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
    Option SourceScope := do
  if !decide entry.WellFormed then none else
    let initialized ← program.body.check entry
    let exit := { entry with initialized }
    if ExpressionWellTyped exit program.result then some exit else none

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

end LLMLang.SourceCommandSemantics
