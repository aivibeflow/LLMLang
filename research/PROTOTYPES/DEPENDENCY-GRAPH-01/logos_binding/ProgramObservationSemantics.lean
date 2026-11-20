import SymbolicCommandSemantics

namespace LLMLang.ProgramObservationSemantics

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics
open LLMLang.SymbolicCommandSemantics

structure StateField where
  id : VariableId
  sort : ExprSort

/-- The return is always observed. This list fixes the order of the selected state. -/
structure ObservationContract where
  fields : List StateField

def ObservationContract.Valid (contract : ObservationContract) (scope : SourceScope) : Prop :=
  (contract.fields.map StateField.id).Nodup ∧
    ∀ field ∈ contract.fields, scope.permits .observe field.id field.sort = true

instance (contract : ObservationContract) (scope : SourceScope) :
    Decidable (contract.Valid scope) := by
  letI := List.decidableBAll (fun (field : StateField) =>
    scope.permits .observe field.id field.sort = true) contract.fields
  unfold ObservationContract.Valid
  infer_instance

def checkObservedProgram {sort : ExprSort} (program : Program sort)
    (contract : ObservationContract) (entry : SourceScope) : Option SourceScope :=
  (program.check entry).filter (fun exit => decide (contract.Valid exit))

theorem checkObservedProgram_eq_some {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {entry exit : SourceScope} :
    checkObservedProgram program contract entry = some exit ↔
      program.check entry = some exit ∧ contract.Valid exit := by
  simp only [checkObservedProgram, Option.filter_eq_some_iff, decide_eq_true_eq]

/-- State entries carry the sort of their contract slot in the contract's order. -/
inductive StateValues (payload : ExprSort → Type) : List StateField → Type where
  | nil : StateValues payload []
  | cons {field : StateField} {rest : List StateField}
      (value : payload field.sort) (tail : StateValues payload rest) :
      StateValues payload (field :: rest)

structure Observation (payload : ExprSort → Type) (sort : ExprSort) (fields : List StateField) where
  returned : payload sort
  state : StateValues payload fields

private def readFields (env : RuntimeEnv) : (fields : List StateField) →
    Option (StateValues Value fields)
  | [] => some .nil
  | field :: rest => do
    let value ← env.lookup field.id field.sort
    let tail ← readFields env rest
    pure (.cons value tail)

private def lowerFields (state : SymbolicState) : (fields : List StateField) →
    StateValues QueryTerm fields
  | [] => .nil
  | field :: rest => .cons (state.lowerSlot field.id field.sort) (lowerFields state rest)

def StateValues.denote {fields : List StateField} (valuation : Env) :
    StateValues QueryTerm fields → StateValues Value fields
  | .nil => .nil
  | .cons term tail => .cons (evalQuery term valuation) (tail.denote valuation)

def Observation.denote {sort : ExprSort} {fields : List StateField}
    (observation : Observation QueryTerm sort fields) (valuation : Env) :
    Observation Value sort fields :=
  ⟨evalQuery observation.returned valuation, observation.state.denote valuation⟩

def observeProgram {sort : ExprSort} (program : Program sort)
    (contract : ObservationContract) (initial : Configuration) :
    Option (Observation Value sort contract.fields) := do
  let _ ← checkObservedProgram program contract initial.scope
  let (final, returned) ← program.execute initial
  let state ← readFields final.env contract.fields
  pure ⟨returned, state⟩

structure ObservationPath (sort : ExprSort) (fields : List StateField) where
  guards : List Guard
  terms : Observation QueryTerm sort fields

def ObservationPath.active {sort : ExprSort} {fields : List StateField}
    (path : ObservationPath sort fields) (valuation : Env) : Bool :=
  guardsHold path.guards valuation

private def observePath {sort : ExprSort} (program : Program sort)
    (contract : ObservationContract) (path : SymbolicState) :
    ObservationPath sort contract.fields :=
  ⟨path.guards, ⟨path.lower program.result, lowerFields path contract.fields⟩⟩

def translateProgramObservations {sort : ExprSort} (program : Program sort)
    (contract : ObservationContract) (entry : SourceScope) :
    Option (List (ObservationPath sort contract.fields)) := do
  let _ ← checkObservedProgram program contract entry
  let paths ← translateCommands program.body entry
  pure (paths.map (observePath program contract))

/-- Every admitted program and observation contract can be translated. -/
theorem translateProgramObservations_exists {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {entry exit : SourceScope}
    (checked : checkObservedProgram program contract entry = some exit) :
    ∃ paths, translateProgramObservations program contract entry = some paths := by
  have ⟨entryValid, bodyChecked, _⟩ :=
    Program.check_details (checkObservedProgram_eq_some.mp checked).1
  have translated : (translateCommands program.body entry).isSome = true := by
    simp [translateCommands, entryValid, bodyChecked]
  obtain ⟨paths, bodyTranslation⟩ := Option.isSome_iff_exists.mp translated
  exact ⟨paths.map (observePath program contract),
    by simp [translateProgramObservations, checked, bodyTranslation]⟩

private theorem ObservationContract.available {contract : ObservationContract}
    {exit : SourceScope} {final : Configuration} (checked : contract.Valid exit)
    (covers : ScopeCovers final.scope exit) (satisfies : final.env.Satisfies final.scope)
    {field : StateField} (selected : field ∈ contract.fields) :
    ∃ value, final.env.lookup field.id field.sort = some value := by
  obtain ⟨_, declaration, found, sameSort, permitted⟩ :=
    SourceScope.permits_eq_true.mp (checked.2 field selected)
  have member : declaration ∈ exit.context.entries := List.mem_of_find?_eq_some found
  have stored := satisfies declaration (by simpa only [covers.1] using member)
  rw [ite_eq_left (covers.2.2 permitted.2.2), sameSort, lookupDeclaration_id found] at stored
  exact RuntimeEnv.lookup_some_of_sort stored

private theorem readFields_preserved {path : SymbolicState} {valuation : Env}
    (fields : List StateField)
    (available : ∀ field ∈ fields, ∃ value,
      (path.denote valuation).env.lookup field.id field.sort = some value) :
    readFields (path.denote valuation).env fields =
      some ((lowerFields path fields).denote valuation) := by
  induction fields with
  | nil => rfl
  | cons field rest ih =>
    obtain ⟨value, present⟩ := available field (by simp)
    have tail := ih (fun selected presentInTail => available selected (by simp [presentInTail]))
    simp [readFields, lowerFields, StateValues.denote, present, tail,
      SymbolicState.lowerSlot_preserves_lookup present]

private theorem filter_observationPaths {sort : ExprSort} (program : Program sort)
    (contract : ObservationContract) (paths : List SymbolicState) (valuation : Env) :
    (paths.map (observePath program contract)).filter (·.active valuation) =
      (paths.filter (·.active valuation)).map (observePath program contract) := by
  induction paths with
  | nil => rfl
  | cons path rest ih =>
    have same : (observePath program contract path).active valuation = path.active valuation := rfl
    cases active : path.active valuation <;> simp [same, active, ih]

/--
SC-4 for the checked program fragment. The active symbolic observation denotes
the same return value and ordered state tuple as the concrete observer.
-/
theorem translateProgramObservations_preserves {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {entry : SourceScope}
    {translated : List (ObservationPath sort contract.fields)}
    (compiled : translateProgramObservations program contract entry = some translated)
    (valuation : Env) :
    ∃ observation,
      observeProgram program contract ((SymbolicState.initial entry).denote valuation) =
        some observation ∧
      (translated.filter (·.active valuation)).map (fun path => path.terms.denote valuation) =
        [observation] := by
  obtain ⟨exit, checked, rest⟩ := Option.bind_eq_some_iff.mp compiled
  obtain ⟨paths, translatedBody, mapped⟩ := Option.bind_eq_some_iff.mp rest
  cases Option.some.inj mapped
  obtain ⟨checkedProgram, checkedContract⟩ := checkObservedProgram_eq_some.mp checked
  have entryValid := (Program.check_details checkedProgram).1
  obtain ⟨final, returned, ran, covers⟩ := Program.checked_execution_covers checkedProgram
    (SymbolicState.initial_valid entryValid valuation).2
  obtain ⟨concrete, path, commands, selected, denotes⟩ :=
    translateCommands_preserves translatedBody valuation
  have denotesFinal : path.denote valuation = final :=
    denotes.trans (commands.deterministic ran.2.2.1)
  have resultEval := ran.2.2.2
  have returnedTerm : evalQuery (path.lower program.result) valuation = returned := by
    apply SymbolicState.lower_preserves_eval
    change Evaluates (path.denote valuation).scope (path.denote valuation).env program.result returned
    rwa [denotesFinal]
  have stateTerms : readFields final.env contract.fields =
      some ((lowerFields path contract.fields).denote valuation) := by
    rw [← denotesFinal]
    apply readFields_preserved
    intro field member
    rw [denotesFinal]
    exact ObservationContract.available checkedContract covers resultEval.2.2.1 member
  let observation := (observePath program contract path).terms.denote valuation
  refine ⟨observation, ?_, ?_⟩
  · have executed := Program.execute_eq_some.mpr ran
    have admitted : checkObservedProgram program contract
        ((SymbolicState.initial entry).denote valuation).scope = some exit := checked
    simp [observeProgram, admitted, executed, stateTerms, observation, observePath,
      Observation.denote, returnedTerm]
  · simp [filter_observationPaths, selected, observation]

end LLMLang.ProgramObservationSemantics
