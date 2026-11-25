import Routes

namespace TrustBoundary

theorem wrappedKernel : Claim := kernelReduction

theorem wrappedForeign : Claim := foreignReduction

theorem wrappedNative : Claim := nativeReflection

theorem premiseDischarged : Claim := openPremise rfl

end TrustBoundary
