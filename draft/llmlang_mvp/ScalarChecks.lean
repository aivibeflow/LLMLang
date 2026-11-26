import Std

/-!
This independent integer model checks the Calculator's signed 64-bit addition
contract. The model uses an operand guard and proves the result against the
mathematical sum. The theorem concerns the model and its stated input range.
-/

namespace LLMLang.MVP

def i64Min : Int := -9223372036854775808

def i64Max : Int := 9223372036854775807

def fitsI64 (value : Int) : Prop :=
  i64Min ≤ value ∧ value ≤ i64Max

inductive AdditionOutcome where
  | value (result : Int)
  | overflow
  deriving DecidableEq, Repr

/-- Check range using the sign of the second operand and a bound on the first. -/
def guardedAdd (left right : Int) : AdditionOutcome :=
  if 0 ≤ right then
    if left ≤ i64Max - right then .value (left + right) else .overflow
  else
    if i64Min - right ≤ left then .value (left + right) else .overflow

/-- The contract classifies a mathematical sum without using the operand guard. -/
def additionContract (left right : Int) (outcome : AdditionOutcome) : Prop :=
  match outcome with
  | .value result => result = left + right ∧ fitsI64 result
  | .overflow => ¬ fitsI64 (left + right)

theorem guardedAdd_satisfies_contract
    (left right : Int) (hleft : fitsI64 left) :
    additionContract left right (guardedAdd left right) := by
  unfold fitsI64 at hleft
  unfold guardedAdd
  split <;> split
  · exact ⟨rfl, by omega, by omega⟩
  · intro fits
    exact (by omega : ¬ (left + right ≤ i64Max)) fits.2
  · exact ⟨rfl, by omega, by omega⟩
  · intro fits
    exact (by omega : ¬ (i64Min ≤ left + right)) fits.1

theorem checked_i64_add_exact_outcome
    (left right : Int) (hleft : fitsI64 left) (_hright : fitsI64 right)
    (outcome : AdditionOutcome) :
    guardedAdd left right = outcome ↔ additionContract left right outcome := by
  constructor
  · intro equality
    rw [← equality]
    exact guardedAdd_satisfies_contract left right hleft
  · intro contract
    have actual := guardedAdd_satisfies_contract left right hleft
    cases evaluated : guardedAdd left right <;> cases outcome <;>
      simp_all [additionContract]
    · exact contract (actual.1 ▸ actual.2)
    · exact actual (contract.1 ▸ contract.2)

-- Controls cover the exact bounds and both directions of overflow.
example : guardedAdd i64Max 0 = .value i64Max := by decide
example : guardedAdd i64Min 0 = .value i64Min := by decide
example : guardedAdd i64Max 1 = .overflow := by decide
example : guardedAdd i64Min (-1) = .overflow := by decide

#print axioms checked_i64_add_exact_outcome

end LLMLang.MVP
