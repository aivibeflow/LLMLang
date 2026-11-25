def Contains (start size index : Nat) : Prop := start ≤ index ∧ index < start + size

theorem adjacent_or_apart (left count right length index : Nat)
    (separated : left + count ≤ right) :
    ¬ (Contains left count index ∧ Contains right length index) := by
  unfold Contains
  omega

theorem empty_occupies_nothing (start index : Nat) : ¬ Contains start 0 index := by
  unfold Contains
  omega

theorem overlap_has_a_witness (left count right length : Nat)
    (leftFirst : left ≤ right) (rightNonempty : length > 0)
    (beforeEnd : right < left + count) :
    Contains left count right ∧ Contains right length right :=
  ⟨⟨leftFirst, beforeEnd⟩, ⟨Nat.le_refl right, Nat.lt_add_of_pos_right rightNonempty⟩⟩

#print axioms adjacent_or_apart
#print axioms empty_occupies_nothing
#print axioms overlap_has_a_witness
