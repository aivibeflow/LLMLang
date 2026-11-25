namespace IncrementalEvidence

def Admitted (lower threshold : Int) (upper : Option Int) (enabled : Bool) (x : Int) : Prop :=
  lower ≤ x ∧ (∀ hi, upper = some hi → x ≤ hi) ∧ (enabled = true → threshold ≤ x)

theorem boundedSat (lower threshold upper : Int) (enabled : Bool) :
    (∃ x, Admitted lower threshold (some upper) enabled x) ↔
      lower ≤ upper ∧ (enabled = true → threshold ≤ upper) := by
  constructor
  · rintro ⟨x, low, high, guard⟩
    have bound := high upper rfl
    exact ⟨Int.le_trans low bound, fun active => Int.le_trans (guard active) bound⟩
  · rintro ⟨low, guard⟩
    refine ⟨upper, low, ?_, guard⟩
    intro hi h
    cases h
    exact Int.le_refl _

theorem unboundedSat (lower threshold : Int) (enabled : Bool) :
    ∃ x, Admitted lower threshold none enabled x := by
  refine ⟨max lower threshold, Int.le_max_left _ _, ?_, fun _ => Int.le_max_right _ _⟩
  intro hi impossible
  cases impossible

#print axioms boundedSat
#print axioms unboundedSat

end IncrementalEvidence
