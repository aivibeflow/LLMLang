import Wrapped
open TrustBoundary
set_option pp.fullNames true

#check (wrappedKernel : Claim)
#check (wrappedForeign : Claim)
#check (wrappedNative : Claim)
#check (premiseDischarged : Claim)
#check (openPremise : observedInput = 9 → Claim)

#print axioms wrappedKernel
#print axioms wrappedForeign
#print axioms wrappedNative
#print axioms openPremise
#print axioms premiseDischarged
#print axioms unrelatedAgreement
