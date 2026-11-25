def asRefinement (x : Fin bound) : {n : Nat // n < bound} :=
  ⟨x.val, x.isLt⟩

def fromRefinement (x : {n : Nat // n < bound}) : Fin bound :=
  ⟨x.val, x.property⟩

theorem exact_conversion (x : Fin bound) : fromRefinement (asRefinement x) = x := by
  cases x
  rfl

def advance (delta : Nat) (x : Fin bound) : Fin (bound + delta) :=
  ⟨x.val + delta, Nat.add_lt_add_right x.isLt delta⟩

theorem advance_value (x : Fin bound) (delta : Nat) :
    (advance delta x).val = x.val + delta := rfl

theorem advance_cannot_keep_original_bound (x : Fin bound) (delta : Nat)
    (movesOutside : bound ≤ x.val + delta) :
    ¬ (advance delta x).val < bound := by
  rw [advance_value]
  exact Nat.not_lt_of_ge movesOutside

theorem fixed_machine_bound_matters :
    ∃ (x : Fin 65535) (delta : Nat), 65535 < (advance delta x).val := by
  exact ⟨⟨65534, by decide⟩, 2, by decide⟩

#print axioms exact_conversion
#print axioms advance_value
#print axioms advance_cannot_keep_original_bound
#print axioms fixed_machine_bound_matters
