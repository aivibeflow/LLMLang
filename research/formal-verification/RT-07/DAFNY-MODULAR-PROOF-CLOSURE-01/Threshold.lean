import Std.Tactic

namespace Threshold

def maxWord : Int := 18446744073709551615

structure BoundContract (base last : Int) : Prop where
  lower : base + 16 * last ≤ maxWord
  upper : maxWord < base + 16 * (last + 1)

def referenceProvider (base : Int) : Int := (maxWord - base) / 16

theorem proveProvider (base : Int) (h : base ≤ maxWord) :
    0 ≤ referenceProvider base ∧ BoundContract base (referenceProvider base) := by
  unfold referenceProvider
  constructor
  · omega
  · constructor <;> omega

theorem callerConditional (base last ordinal : Int) (h : BoundContract base last) :
    ordinal ≤ last ↔ base + 16 * ordinal ≤ maxWord := by
  have lower := h.lower
  have upper := h.upper
  omega

theorem callerClosed (base ordinal : Int) (h : base ≤ maxWord) :
    ordinal ≤ referenceProvider base ↔ base + 16 * ordinal ≤ maxWord :=
  callerConditional base (referenceProvider base) ordinal (proveProvider base h).2

theorem substitutedZeroRefuted : ¬ BoundContract 0 0 := by
  intro h
  have upper := h.upper
  unfold maxWord at upper
  omega

theorem substitutedZeroWrongAtOne :
    ¬ ((1 : Int) ≤ 0 ↔ 0 + 16 * 1 ≤ maxWord) := by
  unfold maxWord
  omega

#print axioms proveProvider
#print axioms callerConditional
#print axioms callerClosed
#print axioms substitutedZeroRefuted
#print axioms substitutedZeroWrongAtOne

end Threshold
