module

public import Provider
meta import Inspect

namespace ReceiptFixture

public theorem checkedComposition (n : Nat) : ReturnsInput n := checkedProvider n

public theorem conditionalComposition (n : Nat) : ReturnsInput n := conditionalProvider n

end ReceiptFixture

#inspect_receipt ReceiptFixture.checkedComposition
#inspect_receipt ReceiptFixture.conditionalComposition
#inspect_receipt ReceiptFixture.conditionalProvider
