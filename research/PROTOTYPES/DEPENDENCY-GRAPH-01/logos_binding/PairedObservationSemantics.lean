import ProgramObservationSemantics

namespace LLMLang.PairedObservationSemantics

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.SymbolicCommandSemantics
open LLMLang.ProgramObservationSemantics

/-- Select a visible, initialized input by stable declaration ID. -/
def resolveInputFactor (scope : SourceScope) (factor : VariableId) : Option Declaration :=
  if scope.WellFormed then
    (lookupDeclaration scope.context factor).filter (fun declaration =>
      decide (declaration.role = .input ∧ scope.Allows .read declaration))
  else none

theorem resolveInputFactor_eq_some {scope : SourceScope} {factor : VariableId}
    {declaration : Declaration} :
    resolveInputFactor scope factor = some declaration ↔
      scope.WellFormed ∧ lookupDeclaration scope.context factor = some declaration ∧
        declaration.role = .input ∧ scope.Allows .read declaration := by
  by_cases valid : scope.WellFormed <;>
    simp [resolveInputFactor, valid, Option.filter_eq_some_iff]

/-- The initialized slots other than the factor carry identical values. -/
def AgreeOnOtherSlots (scope : SourceScope) (factor : VariableId) (left right : Env) : Prop :=
  ∀ declaration ∈ scope.context.entries,
    declaration.id ∈ scope.initialized → declaration.id ≠ factor →
      left declaration.sourceName declaration.sort = right declaration.sourceName declaration.sort

local instance (sort : ExprSort) : DecidableEq (Value sort) := by
  intro left right
  cases left with
  | intValue l =>
    cases right with
    | intValue r => exact decidable_of_iff (l = r) (by simp)
  | boolValue l =>
    cases right with
    | boolValue r => exact decidable_of_iff (l = r) (by simp)

local instance (scope : SourceScope) (factor : VariableId) (left right : Env) :
    Decidable (AgreeOnOtherSlots scope factor left right) := by
  unfold AgreeOnOtherSlots
  exact List.decidableBAll _ _

structure PairedValuations (scope : SourceScope) (factor : VariableId) where
  left : Env
  right : Env
  factorAdmitted : (resolveInputFactor scope factor).isSome = true
  shared : AgreeOnOtherSlots scope factor left right

/-- The factor can take different values. Equality remains admissible here. -/
def PairedValuations.check (scope : SourceScope) (factor : VariableId) (left right : Env) :
    Option (PairedValuations scope factor) :=
  if admitted : (resolveInputFactor scope factor).isSome = true ∧
      AgreeOnOtherSlots scope factor left right then
    some ⟨left, right, admitted.1, admitted.2⟩
  else none

theorem PairedValuations.check_isSome {scope : SourceScope} {factor : VariableId}
    {left right : Env} :
    (PairedValuations.check scope factor left right).isSome = true ↔
      (resolveInputFactor scope factor).isSome = true ∧ AgreeOnOtherSlots scope factor left right := by
  by_cases admitted : (resolveInputFactor scope factor).isSome = true ∧
      AgreeOnOtherSlots scope factor left right <;> simp [PairedValuations.check, admitted]

def PairedValuations.leftInitial {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) : Configuration :=
  (SymbolicState.initial scope).denote pair.left

def PairedValuations.rightInitial {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) : Configuration :=
  (SymbolicState.initial scope).denote pair.right

theorem PairedValuations.factor_values {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) {declaration : Declaration}
    (found : resolveInputFactor scope factor = some declaration) :
    pair.leftInitial.env factor =
      some ⟨declaration.sort, pair.left declaration.sourceName declaration.sort⟩ ∧
    pair.rightInitial.env factor =
      some ⟨declaration.sort, pair.right declaration.sourceName declaration.sort⟩ := by
  obtain ⟨_, bound, _, readable⟩ := resolveInputFactor_eq_some.mp found
  have initialized : factor ∈ scope.initialized := lookupDeclaration_id bound ▸ readable.2
  simp [PairedValuations.leftInitial, PairedValuations.rightInitial,
    SymbolicState.initial_lookup bound, initialized]

theorem PairedValuations.shared_slot {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) {declaration : Declaration}
    (member : declaration ∈ scope.context.entries) (other : declaration.id ≠ factor) :
    pair.leftInitial.env declaration.id = pair.rightInitial.env declaration.id := by
  obtain ⟨_, resolved⟩ := Option.isSome_iff_exists.mp pair.factorAdmitted
  have valid := (resolveInputFactor_eq_some.mp resolved).1
  have found := scope.context.lookupDeclaration_of_mem valid.1 member
  rw [PairedValuations.leftInitial, PairedValuations.rightInitial,
    SymbolicState.initial_lookup found, SymbolicState.initial_lookup found]
  split
  · rename_i initialized
    rw [pair.shared declaration member initialized other]
  · rfl

theorem PairedValuations.shared_state {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) {declaration : Declaration}
    (member : declaration ∈ scope.context.entries) (state : declaration.role = .state) :
    pair.leftInitial.env declaration.id = pair.rightInitial.env declaration.id := by
  apply pair.shared_slot member
  intro sameId
  obtain ⟨selected, resolved⟩ := Option.isSome_iff_exists.mp pair.factorAdmitted
  obtain ⟨valid, selectedFound, role, _⟩ := resolveInputFactor_eq_some.mp resolved
  have found := scope.context.lookupDeclaration_of_mem valid.1 member
  rw [sameId] at found
  have sameDecl := Option.some.inj (found.symm.trans selectedFound)
  rw [sameDecl, role] at state
  cases state

def observeConcretePair {sort : ExprSort} (program : Program sort)
    (contract : ObservationContract) {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) :
    Option (Observation Value sort contract.fields × Observation Value sort contract.fields) := do
  let left ← observeProgram program contract pair.leftInitial
  let right ← observeProgram program contract pair.rightInitial
  pure (left, right)

private def observeActivePath {sort : ExprSort} {fields : List StateField}
    (paths : List (ObservationPath sort fields)) (valuation : Env) :
    Option (Observation Value sort fields) :=
  match (paths.filter (·.active valuation)).map (fun path => path.terms.denote valuation) with
  | [observation] => some observation
  | _ => none

def observeSymbolicPair {sort : ExprSort} {fields : List StateField}
    (paths : List (ObservationPath sort fields)) {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) :
    Option (Observation Value sort fields × Observation Value sort fields) := do
  let left ← observeActivePath paths pair.left
  let right ← observeActivePath paths pair.right
  pure (left, right)

/-- SC-5 lifts single-run observation preservation to arbitrary related valuations. -/
theorem pairedObservations_preserved {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {paths : List (ObservationPath sort contract.fields)}
    (compiled : translateProgramObservations program contract scope = some paths)
    (pair : PairedValuations scope factor) :
    ∃ left right,
      observeConcretePair program contract pair = some (left, right) ∧
      observeSymbolicPair paths pair = some (left, right) := by
  obtain ⟨left, sourceLeft, symbolicLeft⟩ :=
    translateProgramObservations_preserves compiled pair.left
  obtain ⟨right, sourceRight, symbolicRight⟩ :=
    translateProgramObservations_preserves compiled pair.right
  refine ⟨left, right, ?_, ?_⟩
  · simp [observeConcretePair, PairedValuations.leftInitial, PairedValuations.rightInitial,
      sourceLeft, sourceRight]
  · simp [observeSymbolicPair, observeActivePath, symbolicLeft, symbolicRight]

end LLMLang.PairedObservationSemantics
