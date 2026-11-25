# RT-10 repeated cancellation and terminal resource settlement

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

An actual CPython `asyncio.TaskGroup` runs a worker owning a native file descriptor. The program gates its body, the start of cleanup and the finalizer's close. It compares a directly awaited finalizer with a retained, protected finalizer. Both variants observe native file descriptor state at terminal publication. A body may succeed, fail after a native one-byte write, or cancel before the write. The controller can issue two further cancellation signals during cleanup.

| Control | Observed outcome |
| --- | --- |
| Direct finalizer with a second cancellation during its wait | Twelve schedules publish terminal cancellation while the descriptor is open. The experiment then closes that controlled descriptor itself. |
| Retained and shielded finalizer | Every one of 18 schedules waits for close before publishing the terminal result. |
| Primary body failure and cleanup diagnostic | The protected path preserves both in separate fields. Their order in the trace follows body effect, close, cleanup diagnostic and terminal publication. |
| Cancellation before operation | The file has no new content. An already performed write remains observable after a later cancellation request. |

All 36 complete outcomes and event sequences match the independent finite oracle. The candidate chooses the primary body disposition when it reaches cleanup. A later cancellation records a request while cleanup is in progress. The worker retains ownership until finalization has settled, and publication has separate fields for the body cause and cleanup diagnostic.

The fixture uses CPython cooperative scheduling, local native file descriptors and controlled cleanup diagnostics. General cancellation priority, task cancellation liveness, platform-specific close failures, blocking foreign code and production runtime policy remain open.

Reproduce with CPython 3.12.14 on Linux.

```bash
study=research/runtime-and-systems/RT-10/ASYNC-TERMINAL-SETTLEMENT-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent runs reproduce the exact scheduled outcomes.
