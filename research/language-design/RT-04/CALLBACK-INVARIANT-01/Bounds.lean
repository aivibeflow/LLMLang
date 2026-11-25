namespace CallbackInvariant

structure Bounds where
  lower : Int
  upper : Int
  deriving DecidableEq

def Valid (bounds : Bounds) : Prop :=
  bounds.lower ≤ bounds.upper

inductive Order
  | lowerFirst | upperFirst

def intermediate (before after : Bounds) (order : Order) : Bounds :=
  match order with
  | .lowerFirst => ⟨after.lower, before.upper⟩
  | .upperFirst => ⟨before.lower, after.upper⟩

def finish (before after : Bounds) (rollback : Bool) : Bounds :=
  if rollback then before else after

def safe (before after : Bounds) (order : Order) (observer rollback : Bool) : Prop :=
  Valid (finish before after rollback) ∧
    (observer = true → Valid (intermediate before after order))

theorem endpointsPreserve (before after : Bounds) (rollback : Bool)
    (pre : Valid before) (target : Valid after) : Valid (finish before after rollback) := by
  cases rollback
  · exact target
  · exact pre

theorem preciseObserverCondition (before after : Bounds) (order : Order) (observer rollback : Bool)
    (pre : Valid before) (target : Valid after) :
    safe before after order observer rollback ↔
      (observer = false ∨ Valid (intermediate before after order)) := by
  have final := endpointsPreserve before after rollback pre target
  cases observer <;> simp [safe, final]

theorem someSafeOrder (before after : Bounds) (pre : Valid before) (target : Valid after) :
    Valid (intermediate before after .lowerFirst) ∨ Valid (intermediate before after .upperFirst) := by
  change after.lower ≤ before.upper ∨ before.lower ≤ after.upper
  by_cases lowerFirst : after.lower ≤ before.upper
  · exact Or.inl lowerFirst
  · exact Or.inr (Int.le_trans pre (Int.le_trans (Int.le_of_lt (Int.lt_of_not_ge lowerFirst)) target))

theorem rollbackKeepsEarlierExposure (before after : Bounds) (order : Order)
    (invalid : ¬ Valid (intermediate before after order)) :
    finish before after true = before ∧ ¬ safe before after order true true :=
  ⟨rfl, fun accepted => invalid (accepted.2 rfl)⟩

#print axioms endpointsPreserve
#print axioms preciseObserverCondition
#print axioms someSafeOrder
#print axioms rollbackKeepsEarlierExposure

end CallbackInvariant
