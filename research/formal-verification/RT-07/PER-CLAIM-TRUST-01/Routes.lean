import Boundary

namespace TrustBoundary

theorem kernelReduction : Claim := rfl

theorem foreignReduction : Claim :=
  underInputAssumption observedInput inputIsNine

theorem nativeReflection : Claim := by
  unfold Claim
  native_decide

theorem openPremise (agreement : observedInput = 9) : Claim :=
  underInputAssumption observedInput agreement

end TrustBoundary
