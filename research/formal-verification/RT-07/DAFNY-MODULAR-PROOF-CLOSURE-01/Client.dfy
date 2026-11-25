include "Provider.dfy"

module Client {
  import Provider

  method Fits(base: nat, ordinal: nat) returns (fits: bool)
    requires base <= Provider.MaxWord
    ensures fits <==> base + 16 * ordinal <= Provider.MaxWord
  {
    var last := Provider.LastOrdinal(base);
    fits := ordinal <= last;
  }
}
