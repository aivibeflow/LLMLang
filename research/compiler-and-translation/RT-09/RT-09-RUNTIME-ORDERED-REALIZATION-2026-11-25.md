# Ordered native effects with an explicit runtime binding

[GitHub #327](https://github.com/aivibeflow/LLMLang/issues/327) · 2026-11-25

The fixture lowers a two-step source program to C17, builds it independently of the runtime provider, links the provider from a static archive and runs the resulting ELF through a separate driver. A source-level Python oracle defines the expected effects without importing the emitter, calling the provider or reading the generated source.

## Preservation contract

The program attempts to emit tag 11 with the left input and then tag 29 with the right input. A successful emission consumes one unit of quota and updates the state. A denied emission records the attempted effect and ends the program with an explicit error and no value. On success the program returns the sum. The observation includes status, value, final state, remaining quota and the ordered sequence of tags, arguments and dispositions.

The input domain is the Cartesian product of five initial states, three quotas and five values for each of two inputs, giving 375 cases per executable. The bounded domain ensures the fixed-width C operations fit. The exact expected source fixture is part of the validation input. The oracle is independently written for that fixture.

## Evidence

On x86-64 Linux, GCC 14.2.0 and GNU binutils 2.44 produce these results identically at `-O0` and `-O2`.

| Translation and provider | Complete matches | Status, value, state and quota matches |
| --- | ---: | ---: |
| Ordered translation, intended provider | 375/375 | 375/375 |
| Reversed translation, intended provider | 0/375 | 275/375 |
| Ordered translation, event-mutating provider with the same ABI | 0/375 | 375/375 |

The reordered path preserves the intended runtime identity. The same-ABI provider changes emitted tags while preserving results, state, quota and event dispositions. A scalar projection therefore accepts 650 of the 750 changed executions per optimization level. Recording the ordered effects detects every changed execution.

Both generated object variants have an unresolved `rt_emit` reference. The two links without a provider fail, while GNU ld's trace confirms the exact archive member in each successful link. The final ELF defines `rt_emit` and lists `libc.so.6` as a hosted dependency. The ledger records the source fixture, generated source, ABI header, runtime archive and selected object, native executable, toolchain, input corpus and full observation digests. The admitted realization requires the intended archive and an exact observation match. The controls exercise each condition independently.

This is bounded differential evidence for one statically bound runtime service, with a separately written C driver and shared libc environment. It covers neither dynamic provider resolution nor validation of all possible source input and effect combinations.

## Replay

Run with Python 3.12, GCC and GNU binutils from the repository root.

```sh
fixture=research/compiler-and-translation/RT-09/RUNTIME-ORDERED-REALIZATION-01
python "$fixture/run.py" --output /tmp/rt09-ordered-runtime.json
cmp "$fixture/evidence.json" /tmp/rt09-ordered-runtime.json
```

Each run compiled into fresh temporary directories. The two full runs produced identical [evidence ledgers](RUNTIME-ORDERED-REALIZATION-01/evidence.json).
