# RT-04 asynchronous cancellation and fallible resource finalization

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

The Rust fixture acquires two local resource guards with explicit suspension points. It varies cancellation before acquisition and after either suspension, failure of each acquisition, and diagnostics from each release. The same ownership model supports implicit guard destruction and an explicit consuming finalizer. Both release the acquired tracking capabilities. The explicit path can also return cleanup diagnostics as an ordered part of the result.

| Checked outcome per optimization | Count |
| --- | ---: |
| Cancellation | 48 |
| First acquisition failure | 24 |
| Second acquisition failure | 16 |
| Completion | 8 |
| Cleanup diagnostics | 32 |
| Diagnostics carried in explicit results | 8 |
| Diagnostics observed only through implicit drop | 24 |

All 192 native schedules preserve the independent oracle's result, acquisition order and one-time release trace. The two-resource cleanup runs in reverse acquisition order. If both explicit finalizers diagnose an issue, the result carries both diagnostics in that order. When cancellation drops the pending future, cleanup remains in the lifecycle trace. The controller receives cancellation instead of a domain-specific cleanup result.

Distinguish release of an ownership capability from successful completion of an external finalizer. The fixture models local ownership release and records cleanup diagnostics independently. It exercises manually polled Rust futures with one task. External reclamation, concurrent cancellation, effect handlers, language runtime design and general cleanup contracts remain open.

Reproduce with Rust 1.85.1 and CPython 3.12.14 from the repository root.

```bash
study=research/language-design/RT-04/ASYNC-RESOURCE-CANCELLATION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh builds and executions reproduced the result and event digests.
