import Std.Tactic

namespace MergeCost

/-- First component counts output writes, second bounds comparisons. -/
def work (n : Nat) : Nat × Nat :=
  if h : n < 2 then (0, 0) else
    let a := work (n / 2)
    let b := work (n - n / 2)
    (n + a.1 + b.1, n - 1 + a.2 + b.2)
termination_by n
decreasing_by all_goals omega

theorem split_progress (n : Nat) (nontrivial : 2 ≤ n) :
    0 < n / 2 ∧ n / 2 < n ∧ 0 < n - n / 2 ∧ n - n / 2 < n := by omega

theorem writes_minus_comparisons (n : Nat) (nonempty : n > 0) :
    (work n).2 + (n - 1) = (work n).1 := by
  by_cases small : n < 2
  · have one : n = 1 := by omega
    subst n
    simp [work]
  · rw [work, dite_eq_right small]
    have a := writes_minus_comparisons (n / 2) (by omega)
    have b := writes_minus_comparisons (n - n / 2) (by omega)
    dsimp only
    omega
termination_by n
decreasing_by all_goals omega

theorem powers_write_count (k : Nat) :
    (work (2 ^ k)).1 = 2 ^ k * k := by
  induction k with
  | zero => simp [work]
  | succ k ih =>
    have positive := Nat.two_pow_pos k
    have power : 2 ^ (k + 1) = 2 * (2 ^ k) := by rw [Nat.pow_succ, Nat.mul_comm]
    have leftSplit : (2 * 2 ^ k) / 2 = 2 ^ k := by omega
    have rightSplit : 2 * 2 ^ k - 2 ^ k = 2 ^ k := by omega
    rw [power, work, dite_eq_right (by omega), leftSplit, rightSplit]
    dsimp only
    rw [ih, Nat.mul_succ, Nat.mul_assoc]
    omega

theorem powers_comparison_count (k : Nat) :
    (work (2 ^ k)).2 + (2 ^ k - 1) = 2 ^ k * k := by
  rw [writes_minus_comparisons _ (Nat.two_pow_pos k), powers_write_count]

inductive MergeSteps : Nat → Nat → Nat → Prop
  | leftEmpty (right) : MergeSteps 0 right 0
  | rightEmpty (left) : MergeSteps left 0 0
  | takeLeft (left right count : Nat) :
      MergeSteps left (right + 1) count → MergeSteps (left + 1) (right + 1) (count + 1)
  | takeRight (left right count : Nat) :
      MergeSteps (left + 1) right count → MergeSteps (left + 1) (right + 1) (count + 1)

theorem individual_comparisons_bound {left right count : Nat} (steps : MergeSteps left right count) :
    count ≤ left + right - 1 := by
  induction steps with
  | leftEmpty => exact Nat.zero_le _
  | rightEmpty => exact Nat.zero_le _
  | takeLeft left right count steps ih => omega
  | takeRight left right count steps ih => omega

inductive ComparisonTree : Nat → Nat → Prop
  | leaf (size : Nat) (small : size < 2) : ComparisonTree size 0
  | node (size lc rc mc : Nat) (nontrivial : 2 ≤ size) :
      ComparisonTree (size / 2) lc → ComparisonTree (size - size / 2) rc →
      MergeSteps (size / 2) (size - size / 2) mc →
      ComparisonTree size (lc + rc + mc)

theorem recursion_comparisons_bound {size count : Nat} (steps : ComparisonTree size count) :
    count ≤ (work size).2 := by
  induction steps with
  | leaf size small => exact Nat.zero_le _
  | node size lc rc mc nontrivial lhs rhs merge leftBound rightBound =>
    have localBound := individual_comparisons_bound merge
    rw [work, dite_eq_right (by omega)]
    dsimp only
    omega

theorem one_on_right (left : Nat) : MergeSteps left 1 left := by
  induction left with
  | zero => exact .leftEmpty 1
  | succ left ih => exact .takeLeft left 0 left ih

theorem merge_attainment (left right : Nat) :
    MergeSteps (left + 1) (right + 1) (left + 1 + right) := by
  induction right with
  | zero => exact one_on_right (left + 1)
  | succ right ih => exact .takeRight left (right + 1) (left + 1 + right) ih

theorem recursion_comparisons_attain (n : Nat) : ComparisonTree n (work n).2 := by
  by_cases small : n < 2
  · rw [work, dite_eq_left small]
    exact .leaf n small
  · rw [work, dite_eq_right small]
    have required := split_progress n (by omega)
    obtain ⟨l, lh⟩ := Nat.exists_eq_succ_of_ne_zero (by omega : n / 2 ≠ 0)
    obtain ⟨r, rh⟩ := Nat.exists_eq_succ_of_ne_zero (by omega : n - n / 2 ≠ 0)
    have count : n - 1 = l + 1 + r := by omega
    have merge : MergeSteps (n / 2) (n - n / 2) (n - 1) := by
      rw [rh, lh, count]
      exact merge_attainment l r
    have steps := ComparisonTree.node n (work (n / 2)).2 (work (n - n / 2)).2
      (n - 1) (by omega) (recursion_comparisons_attain (n / 2))
      (recursion_comparisons_attain (n - n / 2)) merge
    dsimp only
    have ordered : n - 1 + (work (n / 2)).2 + (work (n - n / 2)).2 =
        (work (n / 2)).2 + (work (n - n / 2)).2 + (n - 1) := by omega
    rw [ordered]
    exact steps
termination_by n
decreasing_by all_goals omega

#print axioms split_progress
#print axioms writes_minus_comparisons
#print axioms powers_write_count
#print axioms powers_comparison_count
#print axioms individual_comparisons_bound
#print axioms recursion_comparisons_bound
#print axioms recursion_comparisons_attain

end MergeCost
