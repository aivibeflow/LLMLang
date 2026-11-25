def IdentityReading (x : Nat) : Nat := x
def OffsetReading (x : Nat) : Nat := x + 7
def AlternatingReading (x : Nat) : Nat := x + if x % 2 = 0 then 12 else 0
def FarReading (x : Nat) : Nat := x + 100
def stableRange (f : Nat → Nat) : Prop := ∀ x, x ≤ f x ∧ f x ≤ x + 32
def monotone (f : Nat → Nat) : Prop := ∀ x y, x ≤ y → f x ≤ f y

theorem identity_range : stableRange IdentityReading := by
  intro x
  simp [IdentityReading]

theorem offset_range : stableRange OffsetReading := by
  intro x
  simp [OffsetReading]

theorem alternating_range : stableRange AlternatingReading := by
  intro x
  unfold AlternatingReading
  split <;> omega

theorem identity_monotone : monotone IdentityReading := by
  intro x y order
  exact order

theorem offset_monotone : monotone OffsetReading := by
  intro x y order
  exact Nat.add_le_add_right order 7

theorem alternating_counterexample : AlternatingReading 1 < AlternatingReading 0 := by decide

theorem far_counterexample : 0 + 32 < FarReading 0 := by decide

#print axioms identity_range
#print axioms offset_range
#print axioms alternating_range
#print axioms identity_monotone
#print axioms offset_monotone
#print axioms alternating_counterexample
#print axioms far_counterexample
