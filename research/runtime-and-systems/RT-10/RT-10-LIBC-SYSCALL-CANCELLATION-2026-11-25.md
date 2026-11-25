# RT-10 — Deferred cancellation at libc and raw Linux read boundaries

Can a direct Linux syscall replace libc `read` when a caller relies on a POSIX thread cancellation point? The experiment queues a deferred cancellation before a known one-byte read and checks completion, cleanup and the byte left in the pipe. The branch baseline is `6e2365868342ec6fbf5488044bb83316e377bd37`. [Raw and libc nonblocking I/O](RT-10-POSIX-NONBLOCKING-PIPE-IO.md) · [POSIX threading interfaces and cancellation points](https://man7.org/linux/man-pages/man7/pthreads.7.html)

The worker uses deferred cancellation and installs a cleanup callback. Two barriers hold it before the operation. While the worker is held, the controller optionally requests cancellation and writes the byte. After release, the worker calls either libc `read` or the x86-64 Linux `SYS_read` entry via inline assembly. It records any returned result and then calls `pthread_testcancel` explicitly. The controller joins the worker and checks the remaining pipe data.

| Entry path and cancellation | Worker completion | Cleanup callback | Byte consumed by worker |
|---|---|---:|---:|
| libc with no request | Returns normally | No | 1 |
| Raw syscall with no request | Returns normally | No | 1 |
| libc with queued cancellation | Cancelled before read returns | Yes | 0 |
| Raw syscall with queued cancellation | Read returns, then explicit check cancels | Yes | 1 |

All four cases agree across glibc, musl and both optimization levels, for 16 runs. The test verifies static archive selection and fresh process state. A join result of cancelled and a completed cleanup callback occur in both pending-request cases, even though the input stream has different remaining content. The raw read path reaches its explicit cancellation check after the effect already occurred. [Archive identities and observation receipts](LIBC-SYSCALL-CANCELLATION-01/evidence.json)

A portable adapter that promises libc-like early cancellation must establish its own cancellation boundary when it invokes the raw syscall. Terminal state alone cannot describe completed I/O. The experiment checks a queued request before a ready nonblocking pipe read. It leaves cancellation that races a blocking syscall, signal interruption, transferring multiple bytes, foreign cleanup, and other kernel and libc profiles open. [POSIX architecture issue](https://github.com/aivibeflow/LLMLang/issues/326)

## Reproduction

Use x86-64 Linux 6.18.57, GCC 14.2.0 (Debian 14.2.0-19), glibc 2.41, musl 1.2.5, GNU Binutils 2.44 and CPython 3.12.14. The runner uses the archive and static ELF checks from the [cross-libc study](RT-10-POSIX-CROSS-LIBC-2026-11-25.md#reproduction). Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/LIBC-SYSCALL-CANCELLATION-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --musl-root /path/to/extracted/musl > /tmp/llmlang-rt10-libc-cancellation.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-libc-cancellation.json
```
