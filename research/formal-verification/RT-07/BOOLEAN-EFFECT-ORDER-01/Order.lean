namespace BooleanEffectOrder

inductive Logic where
  | conjunction | disjunction

structure Observation where
  value : Option Bool
  cell : Nat
  trace : List Nat
  deriving DecidableEq

def determining : Logic → Bool → Bool
  | .conjunction, lhs => !lhs
  | .disjunction, lhs => lhs

def combine : Logic → Bool → Bool → Bool
  | .conjunction, lhs, rhs => lhs && rhs
  | .disjunction, lhs, rhs => lhs || rhs

def appendRight (logic : Logic) (lhs : Bool) (history : List Nat) (rhs : Observation) : Observation :=
  ⟨rhs.value.map (combine logic lhs), rhs.cell, history ++ rhs.trace⟩

def lazyEval (logic : Logic) (lhs rhs : Observation) : Observation :=
  match lhs.value with
  | none => lhs
  | some value => if determining logic value then lhs else appendRight logic value lhs.trace rhs

def eagerEval (logic : Logic) (lhs rhs : Observation) : Observation :=
  match lhs.value with
  | none => lhs
  | some value => appendRight logic value lhs.trace rhs

theorem effectFreeSuccessfulRightAgrees (logic : Logic) (left right : Bool) (cell : Nat)
    (history : List Nat) :
    lazyEval logic ⟨some left, cell, history⟩ ⟨some right, cell, []⟩ =
      eagerEval logic ⟨some left, cell, history⟩ ⟨some right, cell, []⟩ := by
  cases logic <;> cases left <;> cases right <;>
    simp [lazyEval, eagerEval, determining, appendRight, combine]

theorem determiningBranchEquality (logic : Logic) (left : Bool) (cell : Nat)
    (history : List Nat) (right : Observation) (fixed : determining logic left = true) :
    lazyEval logic ⟨some left, cell, history⟩ right =
      eagerEval logic ⟨some left, cell, history⟩ right ↔
      (∃ result, right.value = some result) ∧ right.cell = cell ∧ right.trace = [] := by
  constructor
  · intro equal
    have result := congrArg Observation.value equal
    have successful : ∃ value, right.value = some value := by
      cases eqValue : right.value with
      | none => simp [lazyEval, eagerEval, appendRight, fixed, eqValue] at result
      | some value => exact ⟨value, rfl⟩
    have state : right.cell = cell := by
      simpa [lazyEval, eagerEval, appendRight, fixed] using (congrArg Observation.cell equal).symm
    have trace : history ++ right.trace = history ++ [] := by
      simpa [lazyEval, eagerEval, appendRight, fixed] using (congrArg Observation.trace equal).symm
    exact ⟨successful, state, List.append_cancel_left trace⟩
  · rintro ⟨⟨result, value⟩, state, trace⟩
    have equal : right = ⟨some result, cell, []⟩ := by
      cases right
      simp_all
    rw [equal]
    exact effectFreeSuccessfulRightAgrees logic left result cell history

theorem determiningBranchCannotEraseWriteTrace :
    lazyEval .conjunction ⟨some false, 0, []⟩ ⟨some true, 0, [201, 200]⟩ ≠
      eagerEval .conjunction ⟨some false, 0, []⟩ ⟨some true, 0, [201, 200]⟩ := by
  decide

theorem determiningBranchCannotEraseError :
    lazyEval .disjunction ⟨some true, 0, []⟩ ⟨none, 2, [202, 300]⟩ ≠
      eagerEval .disjunction ⟨some true, 0, []⟩ ⟨none, 2, [202, 300]⟩ := by
  decide

#print axioms effectFreeSuccessfulRightAgrees
#print axioms determiningBranchEquality
#print axioms determiningBranchCannotEraseWriteTrace
#print axioms determiningBranchCannotEraseError

end BooleanEffectOrder
