def checkedAdd (lo hi a b : Int) : Option Int :=
  if lo ≤ a + b ∧ a + b ≤ hi then some (a + b) else none

def leftObserved (lo hi a b c : Int) : Option Int × List Nat :=
  match checkedAdd lo hi a b with
  | none => (none, [0, 1])
  | some partialSum => (checkedAdd lo hi partialSum c, [0, 1, 2])

def rightObserved (lo hi a b c : Int) : Option Int × List Nat :=
  match checkedAdd lo hi b c with
  | none => (none, [0, 1, 2])
  | some partialSum => (checkedAdd lo hi a partialSum, [0, 1, 2])

theorem guardedReassociation (lo hi a b c : Int)
    (leftPartial : lo ≤ a + b ∧ a + b ≤ hi)
    (rightPartial : lo ≤ b + c ∧ b + c ≤ hi) :
    leftObserved lo hi a b c = rightObserved lo hi a b c := by
  simp [leftObserved, rightObserved, checkedAdd, leftPartial, rightPartial, Int.add_assoc]

theorem resultCounterexample :
    (leftObserved (-8) 7 7 1 (-1)).1 ≠ (rightObserved (-8) 7 7 1 (-1)).1 := by
  decide

theorem sameFailureDifferentTrace :
    (leftObserved (-8) 7 7 1 1).1 = (rightObserved (-8) 7 7 1 1).1 ∧
    (leftObserved (-8) 7 7 1 1).2 ≠ (rightObserved (-8) 7 7 1 1).2 := by
  decide

theorem exactObservedCondition (lo hi a b c : Int) :
    leftObserved lo hi a b c = rightObserved lo hi a b c ↔
      (lo ≤ a + b ∧ a + b ≤ hi) ∧
        ((lo ≤ b + c ∧ b + c ≤ hi) ∨ ¬ (lo ≤ a + (b + c) ∧ a + (b + c) ≤ hi)) := by
  by_cases hl : lo ≤ a + b ∧ a + b ≤ hi <;>
    by_cases hr : lo ≤ b + c ∧ b + c ≤ hi <;>
    by_cases ht : lo ≤ a + (b + c) ∧ a + (b + c) ≤ hi <;>
    simp [leftObserved, rightObserved, checkedAdd, hl, hr, ht, Int.add_assoc]

theorem exactValueCondition (lo hi a b c : Int) :
    (leftObserved lo hi a b c).1 = (rightObserved lo hi a b c).1 ↔
      (¬ (lo ≤ a + (b + c) ∧ a + (b + c) ≤ hi) ∨
        ((lo ≤ a + b ∧ a + b ≤ hi) ↔ (lo ≤ b + c ∧ b + c ≤ hi))) := by
  by_cases hl : lo ≤ a + b ∧ a + b ≤ hi <;>
    by_cases hr : lo ≤ b + c ∧ b + c ≤ hi <;>
    by_cases ht : lo ≤ a + (b + c) ∧ a + (b + c) ≤ hi <;>
    simp [leftObserved, rightObserved, checkedAdd, hl, hr, ht, Int.add_assoc]

#print axioms guardedReassociation
#print axioms resultCounterexample
#print axioms sameFailureDifferentTrace
#print axioms exactObservedCondition
#print axioms exactValueCondition
