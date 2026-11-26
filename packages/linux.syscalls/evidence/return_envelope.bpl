// Model tags: 0 = ABI violation, 1 = progress, 2 = zero from a nonempty read, 3 = errno.
// Signed values model raw RAX. Count is the nonnegative slice length.
function signed64(value: int): bool {
  -9223372036854775808 <= value && value <= 9223372036854775807
}

function count64(count: int): bool {
  0 <= count && count <= 9223372036854775807
}

function linuxResult(raw: int, count: int): bool {
  (-4095 <= raw && raw < 0) || (0 <= raw && raw <= count)
}

// The provider retains the exact count or errno from the ABI.
function providerOutcome(reading: bool, raw: int, count: int, tag: int, value: int): bool {
  (tag == 3 && -4095 <= raw && raw < 0 && value == -raw) ||
  (tag == 2 && reading && raw == 0 && count > 0 && value == 0) ||
  (tag == 1 && 0 <= raw && raw <= count &&
    !(reading && raw == 0 && count > 0) && value == raw) ||
  (tag == 0 && !linuxResult(raw, count) && value == 0)
}

// The caller observes bounded progress, a zero-length result from a nonempty
// read, or a Linux errno. Descriptor-specific EOF interpretation is external.
function publicOutcome(reading: bool, count: int, tag: int, value: int): bool {
  (tag == 1 && 0 <= value && value <= count &&
    !(reading && count > 0 && value == 0)) ||
  (tag == 2 && reading && count > 0 && value == 0) ||
  (tag == 3 && 1 <= value && value <= 4095)
}

procedure decode(reading: bool, raw: int, count: int) returns (tag: int, value: int)
  requires signed64(raw) && count64(count);
  ensures providerOutcome(reading, raw, count, tag, value);
{
  if (-4095 <= raw && raw < 0) {
    tag, value := 3, -raw;
  } else if (raw < 0 || raw > count) {
    tag, value := 0, 0;
  } else if (reading && raw == 0 && count > 0) {
    tag, value := 2, 0;
  } else {
    tag, value := 1, raw;
  }
}

procedure refine(reading: bool, raw: int, count: int, tag: int, value: int)
  requires signed64(raw) && count64(count);
  requires linuxResult(raw, count);
  requires providerOutcome(reading, raw, count, tag, value);
  ensures publicOutcome(reading, count, tag, value);
{
}

// Control: an errno is decoded as a transfer in the faulty implementation.
procedure rejectErrnoAsProgress() returns (tag: int, value: int)
  ensures providerOutcome(true, -4, 5, tag, value);
{
  tag, value := 1, 4;
}

// Control: without the Linux return envelope, a provider rejection can be visible.
procedure rejectMissingKernelAssumption()
  requires providerOutcome(true, -4096, 5, 0, 0);
  ensures publicOutcome(true, 5, 0, 0);
{
}
