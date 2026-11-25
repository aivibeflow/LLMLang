# RT-10 — Scoped POSIX conformance receipts

What must a conformance claim carry to distinguish a declared feature, an observed operating-system behavior and an unmeasured profile? This study specifies a candidate receipt schema and checks it against two native evidence sets. The branch baseline is `40ea23a214f4aa75fcfdbf767360f0320a202901`. [POSIX architecture issue](https://github.com/aivibeflow/LLMLang/issues/326)

A claim names its selected specification edition, operation, observation and conditions. The environment key names the architecture, kernel, libc artifact, feature-test request, entry point and fixture conditions. The receipt records the exact observation and disposition, the artifact digest, and the test inventory needed to audit coverage. This prototype indexes the observed environment and keeps specification-edition intent in the operation or feature request. A full system edition claim would need a separate inventory of required operations and options.

| Disposition | Meaning |
|---|---|
| Observed | Exact receipts record the requested observation in the selected profile |
| Unsupported | An applicable availability check reports the feature missing at that boundary |
| Contradicted | An exact native observation disagrees with the selected claim |
| Unknown | The inventory has no adequate evidence for the requested scope and observation |

An optional feature needs an explicit availability disposition and behavior evidence for profiles where the feature is advertised. A documented implementation-defined behavior needs an edition clause, selected implementation and documented choice, and a runtime observation of that choice under stated conditions. A platform parameter such as a returned limit needs the operation or object scope for that parameter. The prototype indexes only the observations in two pinned evidence files. It makes no inferred claims about undocumented choices or unrelated options. [Descriptor edition evidence](POSIX-EDITION-DESCRIPTORS-01/evidence.json) · [Cancellation evidence](LIBC-SYSCALL-CANCELLATION-01/evidence.json)

The two receipts supply 46 entries. Seventeen controls distinguish a visible operation and its tested behavior, an unsupported header and unmeasured runtime, a new request and a full edition claim, and identical cancellation terminal results with different I/O outcomes. An exact receipt supports retained input for libc under the queued-cancellation schedule and contradicts that observation for the raw syscall. Changing the kernel, archive, architecture or condition leaves the claim unknown. A byte change to a pinned input receipt is refused before indexing. [Control results and receipt pins](POSIX-PROFILE-EVIDENCE-01/evidence.json)

This schema supplies a candidate acceptance boundary for individual observations and optional features. A broad claim would need a reviewed normative inventory, sufficient coverage for every applicable row, and a declared treatment of implementation-defined or unsupported options. The prototype assumes the selected digests are already trusted. It leaves normative standard selection, public interchange, receipt signatures, independent review and comprehensive conformance open. [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md)

## Reproduction

Use CPython 3.12.14. The runner reads existing native receipts without rebuilding the native experiments. Hash seeds 1 and 2 produced the same results.

```bash
fixture=research/runtime-and-systems/RT-10/POSIX-PROFILE-EVIDENCE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt10-posix-profile.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-posix-profile.json
```
