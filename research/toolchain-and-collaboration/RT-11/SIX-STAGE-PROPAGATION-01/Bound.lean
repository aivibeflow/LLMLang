def bounded (offset inputMax outputMax : Int) : Prop :=
  ∀ input : Int, input ≤ inputMax → input + offset ≤ outputMax

theorem affine_bound_iff (offset inputMax outputMax : Int) :
    bounded offset inputMax outputMax ↔ inputMax + offset ≤ outputMax := by
  constructor
  · intro proof
    exact proof inputMax (Int.le_refl _)
  · intro bound input admitted
    exact Int.le_trans (Int.add_le_add_right admitted _) bound

theorem endpoint_refutes (offset inputMax outputMax : Int)
    (outside : outputMax < inputMax + offset) : ¬ bounded offset inputMax outputMax := by
  intro proof
  exact Int.not_lt.mpr ((affine_bound_iff offset inputMax outputMax).mp proof) outside

#print axioms affine_bound_iff
#print axioms endpoint_refutes
