# RT-10 typed POSIX vector output and exact write continuation

**Date** 2026-11-25 · **Plan** §5.3 · **Issue** [#326](https://github.com/aivibeflow/LLMLang/issues/326)

A native nonblocking pipe emits a vector of 8,192 bytes with empty vector segments and a split inside a nonempty segment. The fixture fills the pipe, opens one 4 KiB slot and attempts the output. Static glibc and musl builds compare the portable `writev` entry point with explicit Linux `SYS_writev` through the syscall wrapper. The runner verifies the exact linker-selected libc archive and compares both optimization levels.

| Observation | Checked disposition |
| --- | --- |
| Full pipe | `EAGAIN`, no committed progress |
| One slot available | Exactly 4,096 bytes commit from the beginning of the vector |
| Resume through the exact cursor | The remaining 4,096 bytes complete the intended stream |
| Reissue the full vector | 12,288 total bytes, including a duplicated 4,096-byte prefix |
| Empty vector request | A successful zero-byte request |
| Closed peer with signals controlled by the fixture | `EPIPE`, no further progress |

Sixteen native vector trials agree across eight builds. The C probe checks exact contents and the independent Python oracle recomputes both stream fingerprints. Lean proves the exact list concatenation for a checked prefix and suffix without axioms. A second proof using `propext` establishes that full reissue after positive progress produces an overlong stream.

The trusted adapter reports the primitive-specific result and binds progress to the exact original vector and current descriptor incarnation. A typed facade can expose `Progress`, `WouldBlock`, `ZeroRequest` and `PeerClosed` as distinct dispositions. A continuation operates on the unwritten suffix. Execution policy separately handles readiness, external ownership and cancellation. The proofs cover explicit prefix semantics and do not certify Linux, the native C implementation or a broader POSIX profile. Concurrent writers, other backings, signal policy, alternative kernels and production typing remain open.

Reproduce with GCC 14.2.0, Lean 4.36.0, Python 3.12.14 and the pinned musl development sysroot from the [cross-libc fixture](RT-10-POSIX-CROSS-LIBC-2026-11-25.md).

```bash
study=research/runtime-and-systems/RT-10/POSIX-WRITEV-TYPED-PROGRESS-01
python "$study/run.py" --musl-root "$MUSL_SYSROOT" | cmp "$study/evidence.json" -
```

Two builds and replays reproduced the ledger byte for byte.
