import Std.Tactic
import Std.Tactic.BVDecide
import Init.Data.BitVec.Bitblast

namespace CheckedAddition

def widened (a b : BitVec 32) : BitVec 33 :=
  a.signExtend 33 + b.signExtend 33

theorem widened_definition (a b : BitVec 32) :
    widened a b = a.signExtend 33 + b.signExtend 33 := rfl

theorem widened_int (a b : BitVec 32) :
    (widened a b).toInt = a.toInt + b.toInt := by
  have aLow := BitVec.le_toInt a
  have aHigh := BitVec.toInt_lt (x := a)
  have bLow := BitVec.le_toInt b
  have bHigh := BitVec.toInt_lt (x := b)
  have width : 32 ≤ 33 := by decide
  have fits : ¬ (a.signExtend 33).saddOverflow (b.signExtend 33) := by
    simp only [BitVec.saddOverflow, BitVec.toInt_signExtend_of_le width, Bool.or_eq_true,
      decide_eq_true_eq, not_or]
    omega
  unfold widened
  rw [BitVec.toInt_add_of_not_saddOverflow fits]
  simp only [BitVec.toInt_signExtend_of_le width]

theorem source_overflow (a b : BitVec 32) :
    (BitVec.slt (widened a b) (6442450944 : BitVec 33) ||
      BitVec.slt (2147483647 : BitVec 33) (widened a b)) =
        a.saddOverflow b := by
  have lower : (6442450944 : BitVec 33).toInt = -2147483648 := by decide
  have upper : (2147483647 : BitVec 33).toInt = 2147483647 := by decide
  apply Bool.eq_iff_iff.mpr
  simp only [Bool.or_eq_true, BitVec.slt_iff_toInt_lt, widened_int, lower, upper,
    BitVec.saddOverflow, decide_eq_true_eq]
  omega

theorem sign_extract (a : BitVec 32) :
    a.extractLsb' 31 1 = BitVec.ofBool a.msb := by
  bv_normalize

theorem target_overflow (a b : BitVec 32) :
    ((a.extractLsb' 31 1 == b.extractLsb' 31 1) &&
      (a.extractLsb' 31 1 != (a + b).extractLsb' 31 1)) =
        a.saddOverflow b := by
  rw [BitVec.saddOverflow_eq]
  simp only [sign_extract]
  cases a.msb <;> cases b.msb <;> cases (a + b).msb <;> decide

theorem narrow_sum (a b : BitVec 32) : (widened a b).extractLsb' 0 32 = a + b := by
  unfold widened
  bv_normalize

#print axioms source_overflow
#print axioms target_overflow
#print axioms narrow_sum

end CheckedAddition
