# RT-10 — Signal interruption and restart of a blocking pipe read

**Date** · 2026-11-21

**Baseline** · `ce1a4e5`

**Status** · Bounded native experiment for [Plan §5.3](../../../PLAN.md#53-posix-architecture-and-conformance)

## Question

Does observing a signal imply that a blocked I/O operation has returned? A typed POSIX facade needs to distinguish signal handling, interruption before progress, actual completion, and the policy that decides whether to retry. This complements the nonblocking pipe cases by examining a blocked read with no available bytes.

| Approach | Observation and cost |
|---|---|
| Return after one underlying read with restart disabled | The call can return interruption. A caller can decide whether to retry after checking cancellation or a deadline. |
| Use platform restart behavior | The handler can run and the same read can keep waiting. Applicability depends on the operation, signal disposition and OS. |
| Retry in a language-level loop | Can give the language an explicit policy. The retry point must account for reported bytes, deadlines, cancellation and possible effects. The probe does not implement this loop. |

[POSIX read](https://pubs.opengroup.org/onlinepubs/9799919799/functions/read.html) · [POSIX sigaction](https://pubs.opengroup.org/onlinepubs/9799919799/functions/sigaction.html) · [Linux restart behavior](https://man7.org/linux/man-pages/man7/signal.7.html)

## Method and results

A forked process reads from an empty pipe through either libc `read` or Linux `syscall(SYS_read, ...)`. The parent observes the blocked syscall through procfs before delivering SIGUSR1. The signal handler writes a separate acknowledgment byte and preserves `errno`. In the restart case, the parent waits until the child is again in the read before supplying one data byte. Observation uses a bounded fixture timeout and no delay assumption about when the handler begins.

| Signal action | Return value and output | libc at O0/O3 | syscall wrapper at O0/O3 |
|---|---|---:|---:|
| No restart | `-1`, `EINTR`, destination sentinel preserved | 40/40 | 40/40 |
| SA_RESTART | One byte supplied only after the acknowledgment and renewed read | 40/40 | 40/40 |

All 160 observations matched. Successful signal handling is observable before the restarted call returns. Treating acknowledgment as terminal I/O evidence would allow downstream state to advance while the read still waits.

The finding supports retaining an explicit interruption outcome for one-call I/O and expressing retry or cancellation separately. The experiment exercises one blocking pipe read before any progress. It does not establish behavior after partial transfer, cancellation-point semantics, other syscalls, non-Linux targets, or latency guarantees. The syscall wrapper uses the same kernel and reports normalized libc-style error numbers. Procfs access is a test harness requirement and need not be part of the runtime interface.

## Reproduction

From the repository root on Linux x86-64 with readable child syscall information. The recorded runs used Linux 6.18.57, GCC 14.2.0, and glibc 2.41. [Native probe](../PROTOTYPES/POSIX-INTERRUPT-01/read_interrupt.c)

```sh
out=$(mktemp -d)
for level in 0 3; do
  cc -std=c17 -O"$level" -Wall -Wextra -Werror \
    research/runtime-and-systems/PROTOTYPES/POSIX-INTERRUPT-01/read_interrupt.c -o "$out/read-O$level" &&
  timeout 20s "$out/read-O$level" || exit 1
done
```

Related proposed application proof: [CF-008 — Linux pipe transfer](../../formal-verification/CONTRACT-FORMALIZATION-CORPUS/cases/CF-008-linux-pipe-transfer.md) uses the scoped pre-progress EINTR contract for retry and distinguishes safety from termination. It is not additional experimental evidence for this report.
