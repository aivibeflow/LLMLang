# RT-04 typed capability attenuation and residual error effects

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

A separately compiled Rust library ties distinct read, audit and write permits to a supplied authority. The authority constructor and permit fields are private. The driver chooses synthetic cases through an isolated fixture function. It cannot obtain the fixture authority. Native effect methods use only their corresponding scoped permits. The pipeline handles a missing read as a normal absent result and propagates a busy read as a different public error. Later authority refusals and performed-effect failures have separate variants.

| Observed result per optimization | Count |
| --- | ---: |
| Denied read | 108 |
| Absent result handled | 36 |
| Busy read propagated | 36 |
| Denied audit or write | 18 |
| Audit or write operation reports failure | 9 |
| Present result | 9 |

All 432 native outcomes and ordered effect traces match the independent oracle. The denied-read case has no effect. Missing and busy results retain the read event. A completed audit remains in the trace when the next write lacks its permit. An audit may also emit an event and then report failure. These cases distinguish a residual error from effects already taken.

Five compiler controls refuse attempting to use a read permit for writing, an unavailable write grant method on a read permit, construction of a private permit, construction of fixture authority through its private method, and a match omitting an unhandled error. A candidate type layer can express attenuated capabilities and residual errors separately from the declared effect trace. The test records control effects in memory under one trusted fixture issuer. Production capability issuance, revocation, external side effects and effect-row inference remain open.

Reproduce with Rust 1.85.1 and CPython 3.12.14 from the repository root.

```bash
study=research/language-design/RT-04/TYPED-CAPABILITY-ERRORS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent runs reproduce the native dispositions, traces and compiler refusals.
