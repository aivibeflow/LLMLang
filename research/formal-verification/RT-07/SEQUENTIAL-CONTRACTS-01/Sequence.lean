namespace SequentialContracts

structure Observation (State Error Event : Type) where
  failure : Option Error
  state : State
  trace : List Event

abbrev Runs (State Error Event : Type) := State → Observation State Error Event → Prop

structure Contract (State Error Event : Type) where
  admits : State → Prop
  allows : Runs State Error Event

def Satisfies (program : Runs State Error Event) (contract : Contract State Error Event) : Prop :=
  ∀ initial, contract.admits initial → ∀ outcome, program initial outcome → contract.allows initial outcome

def appendTrace (first second : Observation State Error Event) : Observation State Error Event :=
  { second with trace := first.trace ++ second.trace }

def Sequence (first second : Runs State Error Event) : Runs State Error Event :=
  fun initial final => ∃ between, first initial between ∧
    match between.failure with
    | some _ => final = between
    | none => ∃ suffix, second between.state suffix ∧ final = appendTrace between suffix

def Handoff (first second : Contract State Error Event) : Prop :=
  ∀ initial, first.admits initial → ∀ between, first.allows initial between →
    between.failure = none → second.admits between.state

theorem sequenceSatisfies (first second : Runs State Error Event)
    (left right : Contract State Error Event) (goodLeft : Satisfies first left)
    (goodRight : Satisfies second right) (handoff : Handoff left right) :
    Satisfies (Sequence first second) ⟨left.admits, Sequence left.allows right.allows⟩ := by
  intro initial admitted final completed
  obtain ⟨between, leftRun, remainder⟩ := completed
  have leftAllowed := goodLeft initial admitted between leftRun
  refine ⟨between, leftAllowed, ?_⟩
  cases outcome : between.failure with
  | some error =>
    simpa [outcome] using remainder
  | none =>
    simp only [outcome] at remainder ⊢
    obtain ⟨suffix, rightRun, exactTrace⟩ := remainder
    exact ⟨suffix, goodRight between.state
      (handoff initial admitted between leftAllowed outcome) suffix rightRun, exactTrace⟩

theorem prefixFailureIsAnExactSequenceOutcome (first second : Runs State Error Event)
    (initial : State) (between : Observation State Error Event) (error : Error)
    (left : first initial between) (failed : between.failure = some error) :
    Sequence first second initial between := by
  exact ⟨between, left, by simp [failed]⟩

def chooseBoolean : Contract Bool Unit Unit := ⟨fun _ => True, fun _ outcome => outcome.failure = none⟩
def requiresTrue : Contract Bool Unit Unit := ⟨(· = true), fun _ _ => True⟩

theorem oneValidIntermediateDoesNotEstablishHandoff :
    (∃ between, chooseBoolean.allows false between ∧ between.failure = none ∧
      requiresTrue.admits between.state) ∧ ¬ Handoff chooseBoolean requiresTrue := by
  constructor
  · exact ⟨⟨none, true, []⟩, rfl, rfl, rfl⟩
  · intro all
    exact Bool.noConfusion (all false True.intro ⟨none, false, []⟩ rfl rfl)

#print axioms sequenceSatisfies
#print axioms prefixFailureIsAnExactSequenceOutcome
#print axioms oneValidIntermediateDoesNotEstablishHandoff

end SequentialContracts
