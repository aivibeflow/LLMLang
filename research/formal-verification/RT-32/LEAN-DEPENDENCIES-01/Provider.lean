module

public import Lean
meta import Inspect

namespace ReceiptFixture

public def ReturnsInput (n : Nat) : Prop := n = n

public axiom environmentPremise (n : Nat) : ReturnsInput n

public theorem checkedProvider (n : Nat) : ReturnsInput n := by simp [ReturnsInput]

private theorem providerBridge (n : Nat) : ReturnsInput n := environmentPremise n

public theorem conditionalProvider (n : Nat) : ReturnsInput n := providerBridge n

end ReceiptFixture

#inspect_receipt ReceiptFixture.checkedProvider
#inspect_receipt ReceiptFixture.conditionalProvider
#inspect_receipt ReceiptFixture.providerBridge
