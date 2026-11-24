# Research Scenario 113 — Store Buffering and Atomic Memory Orders

**Status:** Bounded executable litmus comparison; no LLMLang memory model selected  
**Research area:** RT-04 ownership/effects/memory model; RT-10 runtime  
**Updated:** 2026-11-20

## Prior-art guarantees added after the abstract comparison

The toy profiles above are useful discriminators, but they must not be mistaken for the default contract of a real language. Current official Rust documentation lists `Relaxed`, `Release`, `Acquire`, `AcqRel`, and `SeqCst`; it says relaxed imposes no ordering constraints beyond atomicity, release/acquire can establish ordering when the acquire observes a release value, and a store-load pair of SeqCst operations preserves a total order. Go chooses a more constrained built-in atomic contract: all atomic operations behave as if in one sequentially consistent order, and a race-free program has a sequentially consistent explanation (DRF-SC). These are different choices, not one common “weak vs strong” switch.

| Prior art | Atomic/read-write contract relevant to these litmus cases | Design implication |
|---|---|---|
| Rust/C++20 ordering family | Multiple explicit orders. Relaxed atomics remain atomic without ordering other memory; each atomic object has a modification order and coherence constraints; release/acquire can publish preceding writes when the acquire reads from the release sequence/value as specified; SeqCst imposes a total order on SeqCst operations. | A relaxed profile needs formal read-from, modification-order, happens-before, coherence, and SC-order rules. An acquire/release profile must state the edge condition precisely. |
| Go | Atomic operations are collectively sequentially consistent; data-race-free programs also have sequentially consistent outcomes. Go defines constrained outcomes for racy programs rather than making all racy behavior fully undefined. | A simpler atomic ordering API can reduce programmer choice, but does not alone solve data races or logical race conditions. |

### What the same-location fixture does and does not capture

The C++ coherence requirements are four relations for each atomic object, not a single global ordering rule:

| Requirement | Constraint when the first operation happens-before the second |
|---|---|
| Write-write | A later modification must follow the earlier modification in that object's modification order. |
| Read-read | A later load must read from the same modification or a later one than the write observed by the earlier load. |
| Read-write | A load must read from a modification earlier in modification order than the subsequent write. |
| Write-read | A load must read from the happens-before write or a later modification. |

The toy read-read fixture covers only the second row, represented as nondecreasing write indices in one reader's observed sequence. It omits read-from choices across threads, the other three coherence relations, release sequences, synchronizes-with/happens-before construction, and SeqCst's cross-object order. Hence it illustrates one per-object constraint but cannot stand in for C++/Rust `Relaxed` or a complete coherence model. Go instead makes all atomic operations sequentially consistent, which entails a single order across its atomic operations, a stronger cross-location promise than per-object monotonicity alone.

The data-race boundary also differs in how it is stated. Go's definition exempts a conflicting location when all accesses are atomic; it strongly advises serializing concurrent mutation. C++ defines a race when potentially concurrent conflicting actions include a non-atomic action and are unordered by happens-before, with undefined behavior. Rustonomicon says safe Rust guarantees absence of data races, primarily through ownership, while its Reference lists data races among undefined behavior; `unsafe` shifts responsibility but does not change the language contract. These are not merely differences in diagnostic tooling: they change which programs have defined semantics. A mixed atomic/non-atomic access should therefore be an explicit corpus case with a stated classification, not inferred from the atomic counter example.

The Rust atomic-ordering and Go memory-model references are linked in [Sources](#sources). The store-buffering toy's “independent per-location” row is not a claim about Go, and it should not be treated as a standalone implementation of C++/Rust relaxed ordering. Rust's atomic integer `fetch_add` documentation defines an atomic read-modify-write that returns the previous value and accepts an ordering argument. Atomicity of that update is separate from its ordering effect on other locations. Full C++20 normative review, formal relation modeling, mixed atomic/non-atomic races, compiler litmus runs, and target-specific measurements remain open.

## Question

What observations should LLMLang permit when concurrent tasks perform atomic writes and reads on distinct locations? Scenario 61 identified this as a discriminating experiment but had no executable corpus. This scenario makes one small case concrete: two tasks each write one location and then read the other.

## Litmus

Initially `x = 0` and `y = 0`:

```text
Task 1:                         Task 2:
x.store(1, order);              y.store(1, order);
r1 = y.load(order);             r2 = x.load(order);
```

The outcome `(r2, r1) = (0, 0)` is impossible under sequential consistency: a single global order would have to place each task's write before its own read, while both reads observe the initial values, creating a cycle. A deliberately weaker abstract profile that orders each location independently admits all four pairs, including `(0, 0)`. The executable enumerator is at [rt04_store_buffering.py](../../PROTOTYPES/RT-04-01/rt04_store_buffering.py); two assertions pin these outcome sets.

| Profile | Possible `(r2, r1)` outcomes | Both reads see initial values? |
|---|---|---|
| One global sequentially consistent order | `(0,1)`, `(1,0)`, `(1,1)` | No |
| Abstract independent per-location order | `(0,0)`, `(0,1)`, `(1,0)`, `(1,1)` | Yes |

## Interpretation and limitations

This isolates the cost/guarantee boundary between a single global order and weaker cross-location ordering. It is not a complete C++, Rust, Go, or hardware model: the weak profile is an intentionally minimal abstraction, not a claim that all relaxed atomics permit arbitrary outcomes. The model omits fences, dependencies, mixed atomic/non-atomic operations, and compiler transformations. It says nothing about logical races, progress, or target-specific implementation cost. Real language/runtime validation must bind litmus outcomes to a formal memory model and compiler/backend versions across targets.

The same prototype includes a separate message-passing outcome relation: writer stores payload then flag; reader loads flag then payload. A stated synchronizes-with edge when the reader observes `flag = 1` excludes stale `payload = 0`; without that edge, the toy relation admits it. This is an axiom-driven demonstration of happens-before's observable consequence, not an implementation deriving synchronization from real atomic operations.

It also distinguishes atomic read-modify-write from a non-atomic load/add/store counter increment. For two tasks each incrementing once from zero, a single atomic counter's final value is always 2, while enumerated interleavings of the three-step non-atomic increment permit final values 1 and 2. This demonstrates atomicity/indivisibility preventing lost updates; it does not establish ordering of unrelated payload memory. Combining multiple locations or checking a condition before increment still requires a larger atomic protocol. The finite model assumes operations terminate and uses non-negative integers without overflow.

Finally, a same-location read-read fixture records a narrow coherence obligation: if a thread observes atomic writes in modification-order sequence `1` then `2`, a later load may not go backward to `1` or the initial `0`. The enumerator compares monotone observation sequences with a deliberately permissive relation that has no coherence rule. This isolates one of the four C++ per-object coherence constraints from global sequential consistency; it is not a complete relaxed-memory model and does not claim that a real language permits all independently chosen reads.

This result complements Scenario 61's ownership/isolation/shared-memory comparison but does not choose among them. A coherent LLMLang proposal still needs a data-race rule, atomic order lattice and defaults, mixed atomic/non-atomic policy, FFI/unsafe boundary, and conformance suite. In particular, the language must state whether ordinary safe code can reach this low-level shared-atomic API and how its guarantee composes with channels, locks, and ownership transfer.

## Reproduction

From this directory, run `python -m unittest test_rt04_store_buffering.py`.

## Sources

- [Rust `std::sync::atomic::Ordering` (Rust 1.100 docs, viewed 2026-11-20)](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html)
- [The Go Memory Model (viewed 2026-11-20)](https://go.dev/ref/mem)
- [Rust `Atomic::fetch_add` (Rust 1.100 docs, viewed 2026-11-20)](https://doc.rust-lang.org/std/sync/atomic/struct.Atomic.html)
- [Rustonomicon — Data Races and Race Conditions (viewed 2026-11-20)](https://doc.rust-lang.org/nomicon/races.html)
- [C++ draft — Data races (`intro.races`, viewed 2026-11-20)](https://eel.is/c++draft/intro.races)
- [cppreference — C++ atomic coherence requirements (viewed 2026-11-20)](https://cppreference.com/w/cpp/atomic/memory_order.html)
