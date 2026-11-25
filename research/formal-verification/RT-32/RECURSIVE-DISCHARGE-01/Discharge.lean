namespace ProofDischarge

theorem closeDecreasing (left right : Nat → Prop)
    (baseLeft : left 0) (baseRight : right 0)
    (stepLeft : ∀ n, right n → left (n+1))
    (stepRight : ∀ n, left n → right (n+1)) :
    ∀ n, left n ∧ right n := by
  intro n
  induction n with
  | zero => exact ⟨baseLeft, baseRight⟩
  | succ n previous => exact ⟨stepLeft n previous.2, stepRight n previous.1⟩

theorem closeLeftSame (left right : Nat → Prop)
    (baseLeft : left 0) (baseRight : right 0)
    (stepLeft : ∀ n, right (n+1) → left (n+1))
    (stepRight : ∀ n, left n → right (n+1)) :
    ∀ n, left n ∧ right n := by
  intro n
  induction n with
  | zero => exact ⟨baseLeft, baseRight⟩
  | succ n previous =>
    have atRight := stepRight n previous.1
    exact ⟨stepLeft n atRight, atRight⟩

theorem closeRightSame (left right : Nat → Prop)
    (baseLeft : left 0) (baseRight : right 0)
    (stepLeft : ∀ n, right n → left (n+1))
    (stepRight : ∀ n, left (n+1) → right (n+1)) :
    ∀ n, left n ∧ right n := by
  intro n
  induction n with
  | zero => exact ⟨baseLeft, baseRight⟩
  | succ n previous =>
    have atLeft := stepLeft n previous.2
    exact ⟨atLeft, stepRight n atLeft⟩

theorem missingBaseCountermodel :
    ∃ left right : Nat → Prop,
      (∀ n, right n → left (n+1)) ∧ (∀ n, left n → right (n+1)) ∧
      ¬ (∀ n, left n ∧ right n) := by
  refine ⟨fun _ => False, fun _ => False, ?_, ?_, ?_⟩
  · intro _ p; exact p
  · intro _ p; exact p
  · intro h; exact (h 0).1

theorem noDecreaseCountermodel :
    ∃ left right : Nat → Prop,
      left 0 ∧ right 0 ∧
      (∀ n, right (n+1) → left (n+1)) ∧ (∀ n, left (n+1) → right (n+1)) ∧
      ¬ (∀ n, left n ∧ right n) := by
  refine ⟨fun n => n = 0, fun n => n = 0, rfl, rfl, ?_, ?_, ?_⟩
  · intro _ p; exact p
  · intro _ p; exact p
  · intro h; exact Nat.noConfusion (h 1).1

#print axioms closeDecreasing
#print axioms closeLeftSame
#print axioms closeRightSame
#print axioms missingBaseCountermodel
#print axioms noDecreaseCountermodel

end ProofDischarge
