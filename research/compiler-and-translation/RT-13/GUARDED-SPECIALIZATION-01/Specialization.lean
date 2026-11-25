set_option autoImplicit false

def referenceDivide (numerator divisor : Nat) : Option Nat :=
  if divisor = 0 then none else some (numerator / divisor)

def guardedDivide
    (numerator divisor exponent : Nat) (available checked : Bool) : Option Nat :=
  if divisor = 0 then
    none
  else if available = true ∧ checked = true ∧ divisor = 2 ^ exponent then
    some (numerator >>> exponent)
  else
    some (numerator / divisor)

theorem guarded_division_refines
    (numerator divisor exponent : Nat) (available checked : Bool) :
    guardedDivide numerator divisor exponent available checked = referenceDivide numerator divisor := by
  by_cases zero : divisor = 0
  · simp [guardedDivide, referenceDivide, zero]
  · by_cases gate : available = true ∧ checked = true ∧ divisor = 2 ^ exponent
    · simp [guardedDivide, referenceDivide, gate, Nat.shiftRight_eq_div_pow]
    · simp [guardedDivide, referenceDivide, zero, gate]

theorem denominator_check_cannot_be_removed : (63 : Nat) >>> 1 ≠ 63 / 6 := by
  decide

#print axioms guarded_division_refines
#print axioms denominator_check_cannot_be_removed
