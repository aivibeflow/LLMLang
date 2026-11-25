# RT-26 logical disk accounting and Linux process counters

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

A native child writes and reads an ordinary temporary file, reads a sparse hole, flushes it, rewrites a small region twice, and truncates it. The child stops at each phase boundary. A separate observer samples `/proc/<pid>/io`, so reading the accounting interface adds no bytes to the measured child's counters. Exact successful return values and buffer contents determine the logical transfer.

| Phase | Logical read | Logical write | Linux read bytes | Linux write bytes | Cancelled write bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Buffered 4 KiB write | 0 | 4,096 | 0 | 4,096 | 0 |
| Cached read of the same data | 4,096 | 0 | 0 | 0 | 0 |
| Read sparse hole | 8,192 | 0 | 0 | 0 | 0 |
| Flush | 0 | 0 | 0 | 0 | 0 |
| Two overlapping 512-byte writes | 0 | 1,024 | 0 | 4,096 | 0 |
| Truncate | 0 | 0 | 0 | 0 | 4,096 |

Both batches reproduce all 36 native phase deltas on the measured host. The logical byte and syscall counters match the direct transfer oracle. The storage counters represent different kernel accounting. A successful read from cache or a sparse hole can transfer logical bytes with no storage read charge. The truncated dirty page contributes a cancellation counter independently of successful logical writes.

The delegated budget model checks 48 input histories with 62 admissible requests and 82 refusals. Preflight reserves the maximum, then settlement retains actual logical bytes and returns the surplus. Applying the observed storage-byte schedule to a logical-byte cap would exceed that cap in 42 histories. Scope and metric therefore belong in the budget definition. A runtime can enforce its logical task budget at the primitive and treat kernel process measurements as separate platform evidence. OS/container enforcement requires the explicitly promised metric and aggregation scope.

The native study covers one Linux x86-64 filesystem and does not measure actual device transfers, disk latency, cross-process charge attribution, network counters or hardware PMU access. The task ledger models serialized ownership and settlement. Physical limits and portable deployment policy remain open.

Reproduce with GCC 14.2.0 and CPython 3.12.14 on Linux with access to a child process's I/O counters.

```bash
study=research/runtime-and-systems/RT-26/NATIVE-DISK-ACCOUNTING-01
python "$study/run.py" --exact /tmp/llmlang-disk.json --native /tmp/llmlang-disk-native.json
cmp "$study/evidence.json" /tmp/llmlang-disk.json
```

Compare the kernel-specific raw observations with the archived native log when repeating on the same accounting setup.
