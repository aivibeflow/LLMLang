# RT-10 — Nonblocking POSIX pipe I/O through libc and Linux syscalls

**Date** · 2026-11-21  
**Baseline** · `017e64b87c87371309197a392165258b8b088dd1`  
**Status** · Bounded native experiment for [Plan §5.3](../../../PLAN.md#53-posix-architecture-and-conformance)

## Question and contract

Which observations must survive an adapter change from libc to a raw Linux syscall when reading or writing a nonblocking byte stream? The candidate API distinguishes `Progress(n)`, `EndOfStream`, `WouldBlock`, `Interrupted`, and `Failed(error)`. It uses one call per operation and returns the transferred prefix length. A zero-length read yielding zero reports `Progress(0)`. A positive-length read yielding zero reports EOF in this pipe profile. The kernel's signal delivery is separately observable. Each read fixture checks the destination prefix and untouched suffix.

The [POSIX.1-2024 read contract](https://pubs.opengroup.org/onlinepubs/9799919799/functions/read.html) distinguishes an empty pipe with an open writer from EOF. Its [write contract](https://pubs.opengroup.org/onlinepubs/9799919799/functions/write.html) defines nonblocking writes at or below `PIPE_BUF` differently from larger requests and associates a broken pipe with `EPIPE` and `SIGPIPE`. Linux-specific capacity controls and the raw register/return convention remain inside the fixture. [Linux pipe rules](https://man7.org/linux/man-pages/man7/pipe.7.html) · [Linux syscall ABI](https://man7.org/linux/man-pages/man2/syscall.2.html)

| API or realization | Trade-off |
|---|---|
| Close POSIX mapping with libc | Preserves existing call and error conventions. Every caller must distinguish short transfer, EOF, and transient error and save `errno` immediately after failure. |
| Typed one-call facade above either adapter | Makes the next action explicit and hides raw error encoding. Needs a precise zero-length rule and a decision on which OS effects are part of observations. |
| Higher-level repeat or exact-length operation | Useful as a separate policy layer. Needs a progress counter, readiness and cancellation rules, and a way to report completed bytes if a later call fails. Transparently repeating calls can change timing, effects, and the meaning of partial success. |

## Method and results

The C program compares libc `read`/`write` with an x86-64 Linux inline assembly adapter. libc reports `-1` with thread-local `errno`; the raw kernel path returns negative error numbers. Both paths feed the same classifier. Setup and cleanup use libc, including nonblocking pipe creation, capacity queries and signal handling. The adapter makes no claims about libc cancellation points or the behavior of other POSIX wrappers.

| Fixture | Expected and observed |
|---|---|
| Empty pipe with writer open | Positive request returns would-block. Zero-length read returns zero progress. Destination stays untouched. |
| Oversized request on empty pipe | Write reports a prefix equal to capacity on this host. A further write reports would-block. A read requesting more than capacity returns just the written prefix. |
| Two-byte atomic request with one byte free | The write reports would-block. Draining yields exactly the preceding contents. |
| Pending data followed by writer close | The reader first receives the queued byte. The next positive read returns EOF. |
| Closed reader descriptor or no pipe readers | Closed descriptor returns `EBADF`. Writing with all reader endpoints closed reports `EPIPE` and delivers `SIGPIPE`. |

Both adapters matched all 14 expected calls at both observed capacities (4,096 and 65,536 bytes, with `PIPE_BUF=4096`) and both GCC optimization levels, for 112 syscall observations. All buffer and signal checks passed. The exact oversized write count is a Linux fixture expectation based on the queried capacity. The portable safety check is to propagate the count actually reported.

Three isolated classifier mutations failed on the predicted witnesses. Removing the positive-size guard misclassified the zero-length read. Mapping would-block to EOF failed with a writer still open. Returning the requested size in place of the actual result failed on the oversized write.

Retain the one-call typed facade as a candidate for the POSIX vertical slice. Above it, an exact-length action needs distinct semantics for advancing a cursor, readiness, interruption, cancellation, and partial progress. This study exercised no actual `EINTR`, concurrent writers, close races, descriptor reuse, blocking I/O, or process startup. Linux x86-64, one process, valid buffers, and a controlled `SIGPIPE` handler are explicit fixture assumptions. The result informs RT-03/10 error and effect observation and RT-13 ABI portability. [POSIX architecture](POSIX-RUNTIME-ARCHITECTURE.md) · [Dependency map](../../research-management/RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

Run from the repository root on Linux x86-64. The observed run used Linux 6.18.57, GCC 14.2.0, GNU ld 2.44, and glibc 2.41.

```sh
out=$(mktemp -d)
for level in 0 3; do
  cc -std=gnu17 -O"$level" -Wall -Wextra -Werror \
    research/runtime-and-systems/PROTOTYPES/POSIX-IO-01/nonblocking_pipe.c -o "$out/pipe-O$level" &&
  "$out/pipe-O$level" || exit 1
done
```

Expect four passing adapter/capacity lines per executable. [Probe source](../PROTOTYPES/POSIX-IO-01/nonblocking_pipe.c)

Related proposed application proof: [CF-008 — Linux pipe transfer](../../formal-verification/CONTRACT-FORMALIZATION-CORPUS/cases/CF-008-linux-pipe-transfer.md) covers blocking byte-stream pipes and explicitly excludes nonblocking EAGAIN. Extending it to readiness and nonblocking operations requires separate contracts; it is not new experimental evidence for this report.
