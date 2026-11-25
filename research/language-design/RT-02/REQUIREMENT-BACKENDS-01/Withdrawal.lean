import Lean

def Valid (balance amount : Int) : Prop :=
  0 < amount ∧ amount ≤ balance

def Exact (before amount : Int) (success : Bool) (after : Int) : Prop :=
  (success = true ↔ Valid before amount) ∧
    (success = true → after = before - amount) ∧
    (success = false → after = before)

theorem acceptsValid (before amount after : Int) (success : Bool)
    (contract : Exact before amount success after) (valid : Valid before amount) :
    success = true ∧ after = before - amount := by
  have accepted := contract.1.mpr valid
  exact ⟨accepted, contract.2.1 accepted⟩

theorem preservesRejected (before amount after : Int) (success : Bool)
    (contract : Exact before amount success after) (rejected : success = false) :
    after = before := contract.2.2 rejected

theorem preservesNonnegative (before amount after : Int) (success : Bool)
    (contract : Exact before amount success after) (initial : 0 ≤ before) :
    0 ≤ after := by
  cases success with
  | false =>
    simpa only [preservesRejected before amount after false contract rfl] using initial
  | true =>
    have within := (contract.1.mp rfl).2
    have update := contract.2.1 rfl
    omega

theorem failureFrameMatters :
    ¬ Exact 10 0 false 9 := by
  intro contract
  have equal := preservesRejected 10 0 9 false contract rfl
  omega

#print axioms acceptsValid
#print axioms preservesRejected
#print axioms preservesNonnegative
#print axioms failureFrameMatters
