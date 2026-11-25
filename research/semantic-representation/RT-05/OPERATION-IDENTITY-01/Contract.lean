namespace OperationIdentity

inductive Event
  | read | advance | commit
  deriving DecidableEq

inductive Arithmetic
  | wrap | saturate
  deriving DecidableEq

abbrev Observation := Nat × List Event

def next (profile : Arithmetic) (x : Nat) : Nat :=
  match profile with
  | .wrap => (x + 1) % 256
  | .saturate => min (x + 1) 255

def stay (x : Nat) : Observation := (x, [.read, .commit])

def advance (profile : Arithmetic) (x : Nat) : Observation :=
  (next profile x, [.read, .advance, .commit])

def admitted (profile : Arithmetic) (x : Nat) (result : Observation) : Prop :=
  result = stay x ∨ result = advance profile x

def marginal (profile : Arithmetic) (x : Nat) (result : Observation) : Prop :=
  (result.1 = (stay x).1 ∨ result.1 = (advance profile x).1) ∧
    (result.2 = (stay x).2 ∨ result.2 = (advance profile x).2)

def selectProvider (profile : Arithmetic) (chooseAdvance : Bool) (x : Nat) : Observation :=
  if chooseAdvance then advance profile x else stay x

theorem anySelectionSatisfiesContract (profile : Arithmetic) (choice : Bool) (x : Nat) :
    admitted profile x (selectProvider profile choice x) := by
  cases choice with
  | false => exact Or.inl rfl
  | true => exact Or.inr rfl

theorem validChoicesAreDistinguishable :
    admitted .wrap 0 (stay 0) ∧ admitted .wrap 0 (advance .wrap 0) ∧
    stay 0 ≠ advance .wrap 0 := by
  refine ⟨Or.inl rfl, Or.inr rfl, ?_⟩
  decide

theorem marginalRefutation :
    marginal .wrap 0 (0, [.read, .advance, .commit]) ∧
    ¬ admitted .wrap 0 (0, [.read, .advance, .commit]) := by
  constructor
  · exact ⟨Or.inl rfl, Or.inr rfl⟩
  · intro evidence
    cases evidence with
    | inl stayed => cases stayed
    | inr advanced => cases advanced

theorem wrapBoundaryIsOutsideSaturatedContract :
    ¬ admitted .saturate 255 (advance .wrap 255) := by
  intro evidence
  cases evidence with
  | inl stayed => cases stayed
  | inr advanced => cases advanced

#print axioms anySelectionSatisfiesContract
#print axioms validChoicesAreDistinguishable
#print axioms marginalRefutation
#print axioms wrapBoundaryIsOutsideSaturatedContract

end OperationIdentity
