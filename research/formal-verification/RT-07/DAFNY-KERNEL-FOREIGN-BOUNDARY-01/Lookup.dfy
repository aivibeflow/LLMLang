module Core {
  newtype Word = value: int | 0 <= value < 18446744073709551616 witness 0

  const Limit: int := 18446744073709551616
  const EntryBytes: int := 16

  // A read-only lookup in a table identified by (base, count).
  // 0 is success, 1 is an invalid ordinal, 2 is address overflow.
  function Expected(base: Word, count: Word, slot: Word): (int, Word)
  {
    if slot >= count then (1, 0)
    else
      var address := base as int + EntryBytes * (slot as int);
      if address >= Limit then (2, 0)
      else (0, address as Word)
  }

  method Checked(base: Word, count: Word, slot: Word) returns (status: int, address: Word)
    ensures (status, address) == Expected(base, count, slot)
  {
    if slot >= count {
      return 1, 0;
    }
    var maximum := (Limit - 1 - (base as int)) / EntryBytes;
    if slot as int > maximum {
      return 2, 0;
    }
    var selected := base as int + EntryBytes * (slot as int);
    return 0, selected as Word;
  }
}

module {:extern "ffi_bridge"} Bridge {
  import opened Core

  method {:extern "resolve"} Foreign(base: Word, count: Word, slot: Word)
    returns (status: int, address: Word)
    ensures (status, address) == Expected(base, count, slot)
}

module Client {
  import opened Core
  import Bridge

  method ViaForeign(base: Word, count: Word, slot: Word) returns (status: int, address: Word)
    ensures (status, address) == Expected(base, count, slot)
  {
    status, address := Bridge.Foreign(base, count, slot);
  }

  method DirectedClient()
  {
    var tag, address := ViaForeign(18446744073709551600, 2, 1);
    assert tag == 2 && address == 0;
  }
}
