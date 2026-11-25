inductive Step (State Outcome : Type) where
  | stop (outcome : Outcome)
  | invoke (state : State)

def Admissible (first : Step State Outcome → Prop) (accepts : State → Prop) : Prop :=
  ∀ state, first (.invoke state) → accepts state

def Covered (first : Step State Outcome → Prop) (next : State → Outcome → Prop) : Prop :=
  (∃ step, first step) ∧ ∀ state, first (.invoke state) → ∃ outcome, next state outcome

inductive Composed (first : Step State Outcome → Prop) (next : State → Outcome → Prop) :
    Outcome → Prop where
  | stop : first (.stop outcome) → Composed first next outcome
  | continued : first (.invoke state) → next state outcome → Composed first next outcome

theorem covered_composition_has_outcome {first : Step State Outcome → Prop}
    {next : State → Outcome → Prop} (cover : Covered first next) :
    ∃ outcome, Composed first next outcome := by
  obtain ⟨⟨step, firstStep⟩, handoff⟩ := cover
  cases step with
  | stop outcome => exact ⟨outcome, .stop firstStep⟩
  | invoke state =>
    obtain ⟨outcome, later⟩ := handoff state firstStep
    exact ⟨outcome, .continued firstStep later⟩

theorem admitted_handoff_has_coverage {declared actual : Step State Outcome → Prop}
    {next : State → Outcome → Prop} {accepts : State → Prop}
    (refines : ∀ step, actual step → declared step) (existsStep : ∃ step, actual step)
    (admitted : Admissible declared accepts)
    (bodyCoverage : ∀ state, accepts state → ∃ outcome, next state outcome) :
    Covered actual next :=
  ⟨existsStep, fun state step => bodyCoverage state (admitted state (refines (.invoke state) step))⟩

def bothSteps : Step Unit Unit → Prop := fun _ => True
def absentContinuation : Unit → Unit → Prop := fun _ _ => False

theorem nonempty_composite_can_hide_missing_branch :
    (∃ outcome, Composed bothSteps absentContinuation outcome) ∧
      ¬ Covered bothSteps absentContinuation := by
  refine ⟨⟨(), .stop trivial⟩, ?_⟩
  intro coverage
  obtain ⟨_, impossible⟩ := coverage.2 () trivial
  exact impossible

#print axioms covered_composition_has_outcome
#print axioms admitted_handoff_has_coverage
#print axioms nonempty_composite_can_hide_missing_branch
