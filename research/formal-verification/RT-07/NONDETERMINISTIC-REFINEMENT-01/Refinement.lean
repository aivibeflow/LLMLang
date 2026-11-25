namespace NondeterministicRefinement

def Refines (replacement original : α → Prop) : Prop :=
  ∀ result, replacement result → original result

def Must (observed property : α → Prop) : Prop :=
  ∀ result, observed result → property result

def May (observed property : α → Prop) : Prop :=
  ∃ result, observed result ∧ property result

theorem refinementExactlyPreservesMust (replacement original : α → Prop) :
    Refines replacement original ↔ ∀ property, Must original property → Must replacement property := by
  constructor
  · intro refinement property originalMust result observed
    exact originalMust result (refinement result observed)
  · intro preserves result observed
    exact preserves original (fun _ membership => membership) result observed

theorem refinementExactlyRestrictsMay (replacement original : α → Prop) :
    Refines replacement original ↔ ∀ property, May replacement property → May original property := by
  constructor
  · intro refinement property witnessed
    obtain ⟨result, observed, holds⟩ := witnessed
    exact ⟨result, refinement result observed, holds⟩
  · intro preserves result observed
    obtain ⟨same, originalObservation, equality⟩ :=
      preserves (fun value => value = result) ⟨result, observed, rfl⟩
    exact equality ▸ originalObservation

inductive Outcome
  | returned | raised | deadlocked | diverged
  deriving DecidableEq

def terminal : Outcome → Prop
  | .returned | .raised => True
  | .deadlocked | .diverged => False

def forgetNontermination (all : Outcome → Prop) : Outcome → Prop :=
  fun event => all event ∧ terminal event

def good : Outcome → Prop := fun event => event = .returned
def looping : Outcome → Prop := fun event => event = .diverged

theorem terminalProjectionAcceptsLoop :
    Refines (forgetNontermination looping) (forgetNontermination good) := by
  intro result membership
  obtain ⟨loop, terminating⟩ := membership
  change result = Outcome.diverged at loop
  subst result
  exact False.elim terminating

theorem explicitOutcomeRejectsLoop : ¬ Refines looping good := by
  intro admitted
  exact Outcome.noConfusion (admitted .diverged rfl)

#print axioms refinementExactlyPreservesMust
#print axioms refinementExactlyRestrictsMay
#print axioms terminalProjectionAcceptsLoop
#print axioms explicitOutcomeRejectsLoop

end NondeterministicRefinement
