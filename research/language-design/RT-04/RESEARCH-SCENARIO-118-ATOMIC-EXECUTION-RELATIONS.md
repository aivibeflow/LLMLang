# Research Scenario 118 — Atomic Execution Relations

**Status:** bounded comparison of direct release/acquire with a global sequential order

**Research areas:** RT-04 memory model · RT-09 compiler · RT-10 runtime · RT-13 backends

**Updated:** 2026-11-20

## Question

Which read values can a program observe when every atomic access must fit one sequential order? Which additional values become possible when the program uses relaxed loads and stores with direct release/acquire synchronization? Scenarios 113–117 isolate individual rules. This experiment derives the relations for a small program and applies the rules together.

## Model

Input consists of initial integer values and fixed sequences of at most six atomic operations in total. Each store writes a constant. Each load reads one named location. A store may be relaxed or release, and a load may be relaxed or acquire. The model follows the modification order, direct synchronization, and coherence rules of the C++20 working draft for this fragment. Go's single sequential order for its atomic operations motivates the other policy. [C++20 working draft N4861, `intro.races`](https://timsong-cpp.github.io/cppwp/n4861/intro.races) · [N4861, `atomics.order`](https://timsong-cpp.github.io/cppwp/n4861/atomics.order) · [Go Memory Model](https://go.dev/ref/mem)

1. Enumerate each location's modification orders, with its initial write first, and each load's possible source writes on that location. Identify writes by event even when their values agree.
2. Derive synchronization from each acquire that reads a release store. Take the transitive closure with order within threads and initialization order. Reject cycles in the resulting happens-before relation.
3. For a pair on one location ordered by happens-before, compare modification ranks. Use a write's own rank and a load's source rank. The second rank must be greater if that event is a write and at least as large if it is a read. This enforces the four coherence rules together.
4. To check a witness against the global policy, order each load after its source and before the next write to that location if one exists. Add program order and the per-location write orders. A total order exists exactly when this graph is acyclic. Any topological order then places each load after the latest write it observes and before all subsequent writes on its location.

The witness records modification orders, each read's source, derived synchronization, happens-before, and observed values. A separate test oracle generates actual interleavings, executes each load against the latest write, and compares the complete set of modification-order and read-from pairs for the global policy. [Enumerator](../../PROTOTYPES/RT-04-01/rt04_atomic_execution.py) · [Independent interleaving oracle](../../PROTOTYPES/RT-04-01/test_rt04_atomic_execution.py)

## Results

All locations start at zero. The observed pair follows the load order named in each row.

| Program | Observations with relaxed and direct release/acquire | Observations in a global sequential order |
|---|---|---|
| Store buffering. Each thread stores `1` (release), then loads the other's location (acquire). | All four pairs. Both loads can read initialization, so there is no synchronization between threads. | All except `(0,0)`. Putting both loads before the opposite store forms a cycle with thread order. |
| Publication. The writer stores payload `1` and then release flag `1`. The reader acquires the flag and then reads the payload. | `(0,0)`, `(0,1)`, `(1,1)`. Reading the release orders the payload write before the payload read. | The same three pairs. |
| Publication with a repeated flag value. The writer adds a relaxed store of `1` to the flag after its release store. | All four pairs. The stale observation `(1,0)` has one witness. The acquire reads the later plain store and gains no synchronization edge from the release. | All except `(1,0)`. The payload write precedes both flag writes. |
| Load buffering. Each thread first acquires the other's location, then stores `1` (release) to its own. | All except `(1,1)`. Reading both releases would make happens-before cyclic. The fixture with relaxed loads admits `(1,1)`. | All except `(1,1)`. |

The generated corpus covers all 4,096 layouts with two threads, two operations per thread, two locations, and two ordering choices for each kind of operation. The interleaving oracle executes six schedules per layout. Its witness sets agree with the global-order check in every layout. The weaker policy has additional full witnesses in 242 layouts and additional read values in 98. The counts describe this corpus with distinct constant store values. They measure behavioral differences and carry no estimate of occurrence rates or performance.

Seven tests passed on Python 3.12.14 using base `cca9d77` plus the files for this scenario.

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_atomic_execution.py' -v
```

## Consequences for candidate comparison

An all-atomic global order rules out the two stale outcomes in the store-buffering and repeated-flag fixtures. Explicit relaxed and release/acquire operations allow them under different conditions. A proof or diagnostic for release/acquire publication therefore needs the exact read-from edge. Observing the expected flag value is insufficient when multiple stores can write it. A backend for a candidate must preserve the candidate's forbidden outcomes, including through optimization.

The input fragment excludes read-modify-write, fences, mixed `seq_cst` orders, non-atomic accesses, and dependencies through loaded data. Validation of those features needs their own rules, including read-modify-write release relay and results computed from prior reads. The interleaving oracle corroborates the global-order projection. The relaxed and release/acquire side still needs independent memory-model comparison and versioned compiler and target experiments. Performance, progress guarantees, and the LLMLang policy are open.

## Draft impact and claim-level provenance (retrospective, 2026-11-23)

- **Candidate distinction:** the report compares a single global order with explicitly relaxed and direct release/acquire behavior for a bounded load/store fragment. A value-only comparison can hide distinct read-from relations; candidate backends must preserve whichever prohibited observations are eventually adopted.
- **Observation and limitation:** the global-order side is cross-checked against an independent interleaving oracle for the 4,096 generated layouts. The weaker direct release/acquire side **does not** have a separately validated general C++-memory-model oracle. RMW, fences, non-atomic behavior, target lowering and performance remain outside this result.
- **Archived-source check:** the first published committed tree `e956d25bfa34ccc649f0d674e29ea27adecbdb20` is pinned with the enumerator and tests in the [publication provenance manifest](../../quality-audit/2026-11-23-publication-provenance.json). The seven focused tests passed on a **new** CPython 3.12.14 Ubuntu runner in [CI #45254862037](https://github.com/aivibeflow/LLMLang/actions/runs/45254862037). This is not independent confirmation of the exact earlier `cca9d77 + scenario files` working-tree state.
- **Draft decision:** **no new `draft/` effect** and no accepted LLMLang memory-order profile. The comparison informs RT-04 memory semantics and downstream RT-09/RT-10/RT-13 tests; selection requires independent weak-memory and compiler/target verification.
