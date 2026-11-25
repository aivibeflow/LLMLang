module Provider {
  const MaxWord: int := 18446744073709551615

  method LastOrdinal(base: nat) returns (last: nat)
    requires base <= MaxWord
    ensures base + 16 * last <= MaxWord
    ensures MaxWord < base + 16 * (last + 1)
  {
    last := (MaxWord - base) / 16;
  }
}
