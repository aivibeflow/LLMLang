import Defs

namespace CacheTrial

theorem generated : Claim := by
  intro n
  rfl

end CacheTrial

set_option pp.proofs true in
#print CacheTrial.generated
#print axioms CacheTrial.generated
