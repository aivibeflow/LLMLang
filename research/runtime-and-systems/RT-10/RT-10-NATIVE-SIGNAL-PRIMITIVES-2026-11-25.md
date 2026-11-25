# RT-10 native signal interruption and primitive contracts

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

A Linux fixture directs a signal to a worker thread after observing its syscall in `/proc/self/task`. A bounded acknowledgement confirms the signal handler ran. The handler performs an async-signal-safe write and preserves the thread's error indicator. The publisher then determines whether the interrupted call already returned or needs a byte supplied to finish the restarted read.

| Operation or signal policy | Native result | Contract disposition |
| --- | --- | --- |
| Blocking pipe read, handler without restart | `-1`, `EINTR` | Interrupted |
| Blocking pipe read, handler with `SA_RESTART` | One byte delivered by the restarted call, with the previous `E2BIG` still in `errno` | Performed |
| Blocking poll, handler without restart | `-1`, `EINTR` | Interrupted |
| Blocking poll, handler with `SA_RESTART` | `-1`, `EINTR` | Interrupted |
| Nonblocking read on an empty pipe with a writer | `-1`, `EAGAIN` | Would block |
| Read on an empty pipe after the writer closes | Zero result, with stale `E2BIG` | End of stream |
| Read on an invalid descriptor | `-1`, `EBADF` | Failure |

Seventy native probes match the oracle across GCC `-O0` and `-O2`, including 40 directed signal schedules. Interrupted calls in the fixture start without available bytes. After they return, a newly supplied byte remains available to a later reader. A successful restarted read owns its delivered byte. A zero result and a successful positive result require their primitive-specific interpretation and do not consult stale `errno`.

The runtime can expose indexed primitive outcomes and make synchronization, interruption, retry policy and terminal settlement explicit. A caller needs to distinguish a signal notification from a cancellation result and from a completed operation. The fixture uses Linux x86-64, glibc, local pipes, and one controlled reader. General restart policies, partial-transfer interruption, other mechanisms and OSes, signal availability in sandboxes, and production contracts remain open.

Reproduce with GCC 14.2.0 and CPython 3.12.14 on Linux with access to own thread syscall status.

```bash
study=research/runtime-and-systems/RT-10/NATIVE-SIGNAL-PRIMITIVES-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent runs reproduced the observation trace.
