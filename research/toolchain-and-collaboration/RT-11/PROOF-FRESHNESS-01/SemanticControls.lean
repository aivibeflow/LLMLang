namespace ProofFreshness

def baseline (x : Nat) := x + 1
def reordered (x : Nat) := 1 + x
def changed (x : Nat) := x + 2

theorem refactorPreservesEveryResult (x : Nat) : reordered x = baseline x :=
  Nat.add_comm 1 x

theorem changedAtZero : changed 0 ≠ baseline 0 := by
  decide

theorem identityRefutesStrictIncrease : ¬ 0 < (fun x : Nat => x) 0 :=
  Nat.lt_irrefl 0

#print axioms refactorPreservesEveryResult
#print axioms changedAtZero
#print axioms identityRefutesStrictIncrease

end ProofFreshness
