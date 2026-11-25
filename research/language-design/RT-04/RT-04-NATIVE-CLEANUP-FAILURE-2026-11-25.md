# RT-04 — Native cleanup failure under Rust unwind and abort

What reaches the caller when the body fails and cleanup also fails? The experiment checks native destructor events and process outcomes under two Rust panic strategies, then compares a separate explicit cleanup API that returns both domain errors. The branch baseline is `55988066cea7af2b9db45972d16d585b167fae91`. [Cleanup error composition](RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md) · [Fatal failure and unwinding](../RT-03/RESEARCH-SCENARIO-65-FATAL-FAILURE-AND-UNWINDING.md)

The implicit case creates an outer guard and an inner guard. Entering either destructor writes and flushes its own event. The inner destructor may panic after recording entry. The body's normal success, domain error and panic are distinct. The caller wraps the function in `catch_unwind`. The explicit case instead calls a fallible close operation after the body returns an ordinary result, and exposes a typed error containing the body failure, the cleanup failure, or both. Each run uses a separate process.

| Body and cleanup | Unwind build | Abort build |
|---|---|---|
| Domain error and successful destructor | Inner and outer drop run, body error reaches caller | Same |
| Domain error and destructor panic | Inner and outer drop run, caller catches panic | Inner drop starts, process aborts before outer drop |
| Body panic and successful destructor | Both drops run, caller catches panic | Process aborts before either drop |
| Body panic and destructor panic | Inner drop starts, process aborts before outer drop | Process aborts on body panic before either drop |
| Domain error and explicit cleanup error | Outer drop runs, caller receives both errors | Same |

The runner checks all ten cases in each of four native builds. It compares the exact flushed event sequences and exit states. Optimization levels 0 and 2 agree within each panic strategy. A typed domain error is visible after successful implicit cleanup. A destructor panic interrupts that return and can prevent outer cleanup. The explicit result carries both original error values in the tested ordinary-error paths. [Native event ledger](NATIVE-CLEANUP-FAILURE-01/evidence.json)

The explicit variant covers return and domain error. The fixture gives the close operation a deterministic success or failure, and its guard events report entry. Resource reclamation, explicit close during panic, other languages and foreign ABI boundaries, process-external recovery, and the LLMLang failure policy remain open. [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

Use rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, LLVM 19.1.7 and CPython 3.12.14 on x86-64 Linux. The runner disables core dumps for child fixtures and records `-6` for SIGABRT. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/language-design/RT-04/NATIVE-CLEANUP-FAILURE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/pinned/rustc > /tmp/llmlang-rt04-native-cleanup.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt04-native-cleanup.json
```
