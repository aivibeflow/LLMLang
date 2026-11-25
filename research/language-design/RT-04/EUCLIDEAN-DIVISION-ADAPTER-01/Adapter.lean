namespace EuclideanDivisionAdapter

def Euclidean (n d q r : Int) : Prop :=
  q * d + r = n ∧ 0 ≤ r ∧ r < d

def Truncated (n d q r : Int) : Prop :=
  q * d + r = n ∧ -d < r ∧ r < d ∧ (if n < 0 then r ≤ 0 else 0 ≤ r)

def adapt (n d q r : Int) : Int × Int :=
  if n < 0 ∧ r ≠ 0 then (q + 1, r - d) else (q, r)

theorem adaptCorrect (n d q r : Int) (positive : 0 < d) (provided : Euclidean n d q r) :
    Truncated n d (adapt n d q r).1 (adapt n d q r).2 := by
  obtain ⟨reconstruction, lower, upper⟩ := provided
  unfold adapt
  by_cases shift : n < 0 ∧ r ≠ 0
  · rw [ite_eq_left shift]
    unfold Truncated
    rw [ite_eq_left shift.1, Int.add_mul, Int.one_mul]
    have nonzero := shift.2
    exact ⟨by omega, by omega, by omega, by omega⟩
  · rw [ite_eq_right shift]
    refine ⟨reconstruction, by omega, upper, ?_⟩
    by_cases negative : n < 0
    · rw [ite_eq_left negative]
      have zero : r = 0 := by
        by_cases equality : r = 0
        · exact equality
        · exact False.elim (shift ⟨negative, equality⟩)
      change r ≤ 0
      omega
    · rw [ite_eq_right negative]
      exact lower

private theorem quotientCannotIncrease (n d q₁ r₁ q₂ r₂ : Int)
    (positive : 0 < d) (left : Truncated n d q₁ r₁) (right : Truncated n d q₂ r₂) :
    ¬ q₁ < q₂ := by
  intro grows
  have step : q₁ + 1 ≤ q₂ := by omega
  have multiplied := Int.mul_le_mul_of_nonneg_right step (Int.le_of_lt positive)
  rw [Int.add_mul, Int.one_mul] at multiplied
  obtain ⟨reconstruct₁, low₁, high₁, sign₁⟩ := left
  obtain ⟨reconstruct₂, low₂, high₂, sign₂⟩ := right
  by_cases negative : n < 0
  · rw [ite_eq_left negative] at sign₁ sign₂
    omega
  · rw [ite_eq_right negative] at sign₁ sign₂
    omega

theorem truncatedUnique (n d q₁ r₁ q₂ r₂ : Int)
    (positive : 0 < d) (left : Truncated n d q₁ r₁) (right : Truncated n d q₂ r₂) :
    q₁ = q₂ ∧ r₁ = r₂ := by
  have first := quotientCannotIncrease n d q₁ r₁ q₂ r₂ positive left right
  have second := quotientCannotIncrease n d q₂ r₂ q₁ r₁ positive right left
  have equal : q₁ = q₂ := by omega
  refine ⟨equal, ?_⟩
  obtain ⟨eq₁, _⟩ := left
  obtain ⟨eq₂, _⟩ := right
  rw [equal] at eq₁
  omega

theorem adjustmentFitsInt32 (n d q r : Int) (negative : n < 0) (positive : 0 < d)
    (divisorBound : d ≤ 2147483647) (quotientBound : -2147483648 ≤ q)
    (provided : Euclidean n d q r) :
    -2147483648 ≤ q + 1 ∧ q + 1 ≤ 2147483647 ∧
      -2147483648 ≤ r - d ∧ r - d ≤ 2147483647 := by
  obtain ⟨reconstruction, lower, upper⟩ := provided
  have quotientNegative : q < 0 := by
    by_cases nonnegative : 0 ≤ q
    · have productNonnegative := Int.mul_nonneg nonnegative (Int.le_of_lt positive)
      omega
    · omega
  omega

#print axioms adaptCorrect
#print axioms truncatedUnique
#print axioms adjustmentFitsInt32

end EuclideanDivisionAdapter
