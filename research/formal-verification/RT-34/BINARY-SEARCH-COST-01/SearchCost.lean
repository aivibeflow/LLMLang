import Std.Tactic

namespace SearchCost

def budget (size : Nat) : Nat :=
  if size = 0 then 0 else size.log2 + 1

theorem budget_mono {a b : Nat} (ordered : a ≤ b) : budget a ≤ budget b := by
  by_cases ha : a = 0
  · simp [budget, ha]
  · have hb : b ≠ 0 := by omega
    have logarithm : a.log2 ≤ b.log2 :=
      (Nat.le_log2 hb).2 (Nat.le_trans (Nat.log2_self_le ha) ordered)
    simp only [budget, ite_eq_right ha, ite_eq_right hb]
    omega

theorem budget_step (size : Nat) (nonempty : 0 < size) :
    budget size = budget (size / 2) + 1 := by
  by_cases two : 2 ≤ size
  · have half : size / 2 ≠ 0 := by omega
    have whole : size ≠ 0 := by omega
    simp only [budget, ite_eq_right half, ite_eq_right whole]
    rw [Nat.log2_def size, ite_eq_left two]
  · have one : size = 1 := by omega
    subst size
    decide

theorem remaining_branches (size : Nat) (nonempty : size > 0) :
    size / 2 < size ∧ size - size / 2 - 1 ≤ size / 2 := by
  omega

/-- A probe can stop, or continue at any interval of at most half the size. -/
inductive Probes : Nat → Nat → Prop
  | noProbe (size) : Probes size 0
  | probe (size next count : Nat) (nonempty : size > 0)
      (shrinks : next ≤ size / 2) (rest : Probes next count) :
      Probes size (count + 1)

theorem probes_bounded {size count : Nat} (trace : Probes size count) :
    count ≤ budget size := by
  induction trace with
  | noProbe => exact Nat.zero_le _
  | probe size next count nonempty shrinks rest ih =>
    rw [budget_step size nonempty]
    have step := Nat.le_trans ih (budget_mono shrinks)
    omega

/-- Repeated left misses take the largest permitted next interval. -/
theorem left_misses_attain_bound (size : Nat) : Probes size (budget size) := by
  by_cases empty : size = 0
  · subst size
    exact .noProbe 0
  · have nonempty : size > 0 := by omega
    rw [budget_step size nonempty]
    exact .probe size (size / 2) _ nonempty (Nat.le_refl _) (left_misses_attain_bound (size / 2))
termination_by size
decreasing_by exact (remaining_branches size nonempty).1

theorem linear_budget_sound (size : Nat) : budget size ≤ size := by
  by_cases empty : size = 0
  · simp [budget, empty]
  · have nonempty : size > 0 := by omega
    rw [budget_step size nonempty]
    have half := linear_budget_sound (size / 2)
    have shrink := (remaining_branches size nonempty).1
    omega
termination_by size
decreasing_by exact (remaining_branches size nonempty).1

theorem nonprogress_singleton : 1 > 1 / 2 ∧ ¬ (1 < 1) := by decide

theorem missing_one_underbounds (size : Nat) (nonempty : size > 0) :
    size.log2 < budget size := by
  have positive : size ≠ 0 := by omega
  simp [budget, positive]

#print axioms budget_step
#print axioms remaining_branches
#print axioms probes_bounded
#print axioms left_misses_attain_bound
#print axioms linear_budget_sound
#print axioms nonprogress_singleton
#print axioms missing_one_underbounds

end SearchCost
