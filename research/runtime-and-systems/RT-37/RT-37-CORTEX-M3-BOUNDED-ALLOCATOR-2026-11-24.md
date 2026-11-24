# Comparing fixed slots and a bounded Cortex-M3 arena

- **Date:** 2026-11-24
- **Research:** RT-37 EMB-02, RT-25 and RT-34
- **Baseline:** `738853e571b7e04915441b91075cae9046292cb8`
- **Evidence:** Four Cortex-M3 ELF images run in QEMU, 2,704 checked reservations and one executed wraparound control

Four fixed 16-byte slots and a checked linear cursor both fit the same 64-byte Cortex-M3 SRAM arena. For a sequence of 17 four-byte requests, fixed slots accept the first four while the linear cursor accepts the first sixteen. In this fixture the fixed-slot routine uses fewer linked instruction bytes at both backends.

## Profile and comparison

The fixed-slot policy reserves a whole slot for each successful request of one to 16 bytes. The linear policy rounds the byte cursor up to the requested alignment, reserves the requested number of bytes, and advances to the first unreserved byte. Both accept alignments 1, 2, 4, 8 and 16. Both use a 32-bit cursor and an explicit failure value of `0xffffffff`. Each failed request leaves the cursor unchanged. The firmware computes reservations as offsets in the linked arena.

The linear guard checks that the cursor and size are at most 64 and that the request is nonempty. With a valid alignment, rounding adds at most 15. The aligned start stays within 64 because the arena capacity is a multiple of every admitted alignment. Adding the requested size yields at most 128 before the capacity check. These bounds explain the absence of wraparound within the admitted arithmetic. The reference uses unbounded integer division for rounding. LLVM and Rust use the mask form.

| Policy | Successful requests per 676 observations | Successful four-byte requests per 17 | Linked LLVM routine | Linked Rust routine |
| --- | ---: | ---: | ---: | ---: |
| Fixed slots | 57 | 4 | 50 B | 92 B |
| Checked linear cursor | 148 | 16 | 104 B | 120 B |

The corpus has 640 combinations of boundary cursor, size and alignment values and four request sequences. It includes malformed cursor seeds to check that they are preserved on failure. Each image matches both the reservation offset and new cursor after every request. The arena starts at `0x20000000`, and the cursor follows its 64 bytes at `0x20000040`. Static SRAM extent is 68 bytes in all four images. The linked routine sizes exclude the embedded request corpus and UART harness.

The valid LLVM control omits the upper bound on request size. From cursor 16, it admits an aligned request of `0xffffffff` bytes because the sum wraps to 15. The control emits `B|000000100000000f!`. The checked policy rejects it with `B|ffffffff00000010!`, retaining cursor 16. The harness compares numeric offsets and leaves the arena payload untouched.

## Reproduce and scope

Use LLVM/LLD 19.1.7, Rust 1.85.1, Python 3.12.14 and QEMU 10.0.13 with `lm3s6965evb`. Both backends compile at O2. The [ledger](cortex-m3-allocator/results.json) records the exact hashes, linked resources, trace identities and control observations. Five fresh replays produced identical ledgers.

```sh
fixture=research/runtime-and-systems/RT-37/cortex-m3-allocator
output=$(mktemp)
python3 -B "$fixture/run.py" --qemu "$(command -v qemu-system-arm)" --output "$output"
cmp "$fixture/results.json" "$output"
```

The result compares sequential monotonic reservation policies for a fixed arena. Reclaiming or borrowing payload regions, lifetime validation, concurrent and ISR allocation, run-time fragmentation across workloads, kernel frames and hardware deadlines remain separate research obligations.
