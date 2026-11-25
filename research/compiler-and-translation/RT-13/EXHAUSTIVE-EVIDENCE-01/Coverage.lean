def Covers (domain : α → Prop) (tests : List α) : Prop :=
  ∀ input, domain input → input ∈ tests

def AgreesOnTests (reference candidate : α → β) (tests : List α) : Prop :=
  ∀ input, input ∈ tests → reference input = candidate input

theorem exact_exhaustive_agreement {domain : α → Prop} {tests : List α}
    {reference candidate : α → β} (coverage : Covers domain tests)
    (agrees : AgreesOnTests reference candidate tests) :
    ∀ input, domain input → reference input = candidate input :=
  fun input admissible => agrees input (coverage input admissible)

theorem projected_agreement_lifts {domain : α → Prop} {tests : List α}
    {reference candidate : α → β} (observe : β → γ)
    (coverage : Covers domain tests)
    (agrees : AgreesOnTests (observe ∘ reference) (observe ∘ candidate) tests)
    (reflects : ∀ input, domain input →
      observe (reference input) = observe (candidate input) → reference input = candidate input) :
    ∀ input, domain input → reference input = candidate input :=
  fun input admissible => reflects input admissible (agrees input (coverage input admissible))

def reference (input : Bool × Bool) : Bool := input.1
def candidate (input : Bool × Bool) : Bool := input.1 && !input.2

theorem passes_every_input_at_one_schedule :
    ∀ input : Bool, reference (input, false) = candidate (input, false) := by
  intro input
  cases input <;> rfl

theorem omitted_schedule_has_mismatch :
    reference (true, true) ≠ candidate (true, true) := by decide

#print axioms exact_exhaustive_agreement
#print axioms projected_agreement_lifts
#print axioms passes_every_input_at_one_schedule
#print axioms omitted_schedule_has_mismatch
