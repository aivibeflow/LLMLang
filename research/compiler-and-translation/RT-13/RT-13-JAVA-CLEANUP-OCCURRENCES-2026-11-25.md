# RT-13 — Java cleanup and repeated failure occurrences

Can a Java backend preserve every ordered cleanup failure when two operations throw the same exception object? This fixture compares native try-with-resources with a generated-style explicit occurrence accumulator. The branch baseline is `0a5ae806ec41cee87b03d5e8d407abd91146bd34`. [Java scalar backend evidence](RT-13-GENERATED-JAVA-INTEGER-LOWERING-2026-11-24.md) · [Backend selection issue](https://github.com/aivibeflow/LLMLang/issues/329)

The body and two resource closes independently succeed, throw a distinct tagged exception, or throw the same shared exception instance. Both variants record the body, inner close and outer close in order. The automatic variant reports the primary throwable, direct suppressed values and direct cause. The explicit variant captures each failure as a separate record containing its stage and throwable tag. It applies the same two resource cleanup actions in reverse acquisition order. [Java try-with-resources translation](https://docs.oracle.com/javase/specs/jls/se21/html/jls-14.html#jls-14.20.3) · [Throwable suppression contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/Throwable.html)

| Failure conditions | Automatic primary | Explicit failure occurrences |
|---|---|---|
| Body, inner and outer each throw a distinct exception | Body, with inner and outer suppressed in order | Body, inner, outer |
| Body succeeds, both closes throw distinct exceptions | Inner, with outer suppressed | Inner, outer |
| Body and inner close throw the same object, outer succeeds | Self-suppression error with the original object as cause | Body and inner, each with the shared tag |
| Body succeeds, both closes throw the same object | Self-suppression error with the original object as cause | Inner and outer, each with the shared tag |

All 27 cases agree with the independent oracle in interpreted and forced HotSpot compilation modes. Both modes record the same resource event order. Six automatic cases replace the leading failure with a self-suppression error. The explicit variant retains the original order and each stage's failure record across those cases. The receipt preserves direct suppression and cause separately. [Java fixture](JAVA-CLEANUP-OCCURRENCES-01/Fixture.java) · [Exact case ledger](JAVA-CLEANUP-OCCURRENCES-01/evidence.json)

Together with the scalar pilot, this supports Java as a hosted alternative for the checked subsets. A lowering that promises independently observable cleanup failures needs an explicit occurrence representation for this profile. Physical resource release, asynchronous exceptions, foreign ABI, memory footprint, other JVMs and initial backend selection remain open. [Cleanup outcome composition](../../language-design/RT-04/RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md)

## Reproduction

Use Debian OpenJDK 21.0.13+9-1-deb13u2 with its `jdk.compiler` module and CPython 3.12.14. The runner compiles Java 21 source and class targets, compares `-Xint` and `-Xcomp`, and verifies compilation records for both cleanup methods. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/compiler-and-translation/RT-13/JAVA-CLEANUP-OCCURRENCES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt13-java-cleanup.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-java-cleanup.json
```
