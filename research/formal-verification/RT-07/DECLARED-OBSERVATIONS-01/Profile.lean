namespace DeclaredObservations

def Agree (left right : Field → Option Value) (field : Field) : Prop :=
  ∃ value, left field = some value ∧ right field = some value

def Matches (required : List Field) (left right : Field → Option Value) : Prop :=
  ∀ field ∈ required, Agree left right field

theorem respectsNarrowing {larger smaller : List Field} {left right : Field → Option Value}
    (contained : ∀ field ∈ smaller, field ∈ larger) (matchLarger : Matches larger left right) :
    Matches smaller left right :=
  fun field selected => matchLarger field (contained field selected)

theorem unavailableRefuses {field : Field} {required : List Field}
    {left right : Field → Option Value} (selected : field ∈ required) (missing : left field = none) :
    ¬ Matches required left right := by
  intro agrees
  obtain ⟨value, present, _⟩ := agrees field selected
  rw [missing] at present
  cases present

theorem matchingTransitive {required : List Field} {left middle right : Field → Option Value}
    (first : Matches required left middle) (second : Matches required middle right) :
    Matches required left right := by
  intro field selected
  obtain ⟨a, sameLeft, sameMiddle⟩ := first field selected
  obtain ⟨b, otherMiddle, sameRight⟩ := second field selected
  have equal : a = b := Option.some.inj (sameMiddle.symm.trans otherMiddle)
  exact ⟨a, sameLeft, sameRight.trans (congrArg some equal.symm)⟩

#print axioms respectsNarrowing
#print axioms unavailableRefuses
#print axioms matchingTransitive

end DeclaredObservations
