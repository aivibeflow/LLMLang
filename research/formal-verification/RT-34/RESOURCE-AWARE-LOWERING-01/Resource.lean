def budget (n : Nat) : Nat := 2 + 4 * n
def direct (weight n : Nat) : Nat := 2 + n + weight * n
def grouped (weight n : Nat) : Nat := 2 + (n + 1) / 2 + weight * n
def repeated (weight n : Nat) : Nat := 2 + 2 * n + weight * n

theorem direct_fast (n : Nat) : direct 3 n = budget n := by
  unfold direct budget
  omega

theorem grouped_fast (n : Nat) : grouped 3 n ≤ budget n := by
  unfold grouped budget
  omega

theorem grouped_improves (n : Nat) (h : 2 ≤ n) :
    grouped 3 n < direct 3 n := by
  unfold grouped direct
  omega

theorem grouped_slow (n : Nat) (h : 0 < n) : budget n < grouped 7 n := by
  unfold grouped budget
  omega

theorem repeated_fast_fails (n : Nat) (h : 0 < n) : budget n < repeated 3 n := by
  unfold repeated budget
  omega

theorem grouped_units (n : Nat) : 2 * (n / 2) + n % 2 = n := by
  omega

theorem erased_units_fail (n : Nat) (h : 0 < n) : (0 : Nat) ≠ n := by
  omega

#print axioms direct_fast
#print axioms grouped_fast
#print axioms grouped_improves
#print axioms grouped_slow
#print axioms repeated_fast_fails
#print axioms grouped_units
#print axioms erased_units_fail
