# Research Scenario 117 — Atomic Write/Read Coherence Relations

**Status:** executable fixtures for three coherence rules on one atomic object

**Research area:** RT-04 ownership, effects, and memory model · RT-10 runtime · RT-13 backends

**Updated:** 2026-11-20

## Question

What do the C++ write-write, read-write, and write-read coherence requirements rule out when the relevant happens-before and modification-order premises are already known? Scenario 113 described these rules and tested read-read coherence, but did not encode the other three as executable finite constraints.

## Source contract

The C++ draft states four coherence requirements for an atomic object. When a write happens before another write, modification order must respect that order. When two reads are ordered by happens-before, their source writes must be in nondecreasing modification order. If a read happens before a write, its source must strictly precede that write. If a write happens before a read, the source can be that write or a later one. These constraints apply to the write each read observes. [C++ draft, `intro.races`, viewed 2026-11-20](https://eel.is/c++draft/intro.races)

Rust documents its atomic ordering family as the same as C++20's. `Relaxed` operations preserve atomic access and allow independent ordering across objects in the absence of other constraints. [Rust `Ordering`, viewed 2026-11-20](https://doc.rust-lang.org/stable/core/sync/atomic/enum.Ordering.html)

## Finite fixtures

Each write has an ID so two writes of equal values can be distinguished. Both read/write fixtures start from a supplied modification order `init < w1 < w2` and consider all three writes as read sources.

| Relation | Supplied premise | Allowed relation in the fixture | Excluded witness |
|---|---|---|---|
| Write-write | `w0` happens-before `w1` on one object | Only modification order `(w0, w1)` | `(w1, w0)` |
| Read-write | A load happens-before `w1` | Load source must precede `w1`, so only `init` | Reading `w1` or `w2` |
| Write-read | `w1` happens-before a load | Load source must be `w1` or later, so `w1` or `w2` | Reading `init` |

Four new tests check the allowed sets, an inconsistent write order, and malformed input. All 12 atomic litmus tests passed on Python 3.12.14 using base `08c8490` plus the Scenario 117 changes. [Prototype](../../PROTOTYPES/RT-04-01/rt04_store_buffering.py) · [Tests](../../PROTOTYPES/RT-04-01/test_rt04_store_buffering.py)

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_store_buffering.py' -v
```

## Interpretation and limits

Both mixed cases use the same candidate writes. Reversing the happens-before edge changes whether the boundary write `w1` is an eligible source. Together with Scenario 113, the fixtures exercise all four rules on a single object. Their inputs supply the ordering relations. Source extraction, joint execution consistency, release sequences, fences, and compiler transformations remain separate validation tasks.

## Next validation

1. Bind read-from, modification-order, and happens-before constraints into one small execution relation and reject cyclic/inconsistent assignments.
2. Add cross-location synchronization and SeqCst consistency without assuming them from a per-object rule.
3. Compare the model with an independent implementation and version-pinned litmus executions on at least two compiler/target pairs.
4. Revisit the proposed LLVM `Relaxed`→`monotonic` mapping in Scenario 116 against the full accepted source relation before making any lowering claim.

## References

- [C++ draft — data races and coherence (`intro.races`)](https://eel.is/c++draft/intro.races)
- [C++ draft — atomic order and coherence ordering (`atomics.order`)](https://eel.is/c++draft/atomics.order)
- [Rust atomic `Ordering`](https://doc.rust-lang.org/stable/core/sync/atomic/enum.Ordering.html)
- [Scenario 113 — Store Buffering and Atomic Memory Orders](RESEARCH-SCENARIO-113-STORE-BUFFERING-MEMORY-ORDERS.md)
- [Scenario 116 — Atomic Backend Lowering Obligations](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-116-ATOMIC-BACKEND-LOWERING-OBLIGATIONS.md)
