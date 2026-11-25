namespace TypedEdgeProjections

/-- The mathematical execution model used by the finite fixture. -/
def observe (delta factor input : Nat) : Nat :=
  factor * input + delta

theorem firstTwoObservationsDetermineParameters {delta factor otherDelta otherFactor : Nat}
    (zero : observe delta factor 0 = observe otherDelta otherFactor 0)
    (one : observe delta factor 1 = observe otherDelta otherFactor 1) :
    delta = otherDelta ∧ factor = otherFactor := by
  simp [observe] at zero one
  omega

#print axioms firstTwoObservationsDetermineParameters

end TypedEdgeProjections
