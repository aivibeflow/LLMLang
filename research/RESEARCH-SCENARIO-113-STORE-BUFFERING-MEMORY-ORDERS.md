# Research Scenario 113 — Store Buffering and Atomic Memory Orders

**Status:** Bounded executable litmus comparison; no LLMLang memory model selected  
**Research area:** RT-04 ownership/effects/memory model; RT-10 runtime  
**Updated:** 2026-11-20

## Question

What observations should LLMLang permit when concurrent tasks perform atomic writes and reads on distinct locations? Scenario 61 identified this as a discriminating experiment but had no executable corpus. This scenario makes one small case concrete: two tasks each write one location and then read the other.

## Litmus

Initially `x = 0` and `y = 0`:

```text
Task 1:                         Task 2:
x.store(1, order);              y.store(1, order);
r1 = y.load(order);             r2 = x.load(order);
```

The outcome `(r2, r1) = (0, 0)` is impossible under sequential consistency: a single global order would have to place each task's write before its own read, while both reads observe the initial values, creating a cycle. A deliberately weaker abstract profile that orders each location independently admits all four pairs, including `(0, 0)`. The executable enumerator is at [rt04_store_buffering.py](PROTOTYPES/RT-04-01/rt04_store_buffering.py); two assertions pin these outcome sets.

| Profile | Possible `(r2, r1)` outcomes | Both reads see initial values? |
|---|---|---|
| One global sequentially consistent order | `(0,1)`, `(1,0)`, `(1,1)` | No |
| Abstract independent per-location order | `(0,0)`, `(0,1)`, `(1,0)`, `(1,1)` | Yes |

## Interpretation and limitations

This isolates the cost/guarantee boundary between a single global order and weaker cross-location ordering. It is not a complete C++, Rust, Go, or hardware model: the weak profile is an intentionally minimal abstraction, not a claim that all relaxed atomics permit arbitrary outcomes. The model omits read-modify-write, synchronizes-with edges, fences, dependencies, non-atomic races, and compiler transformations. It says nothing about logical races, progress, or target-specific implementation cost. Real language/runtime validation must bind litmus outcomes to a formal memory model and compiler/backend versions across targets.

The same prototype includes a separate message-passing outcome relation: writer stores payload then flag; reader loads flag then payload. A stated synchronizes-with edge when the reader observes `flag = 1` excludes stale `payload = 0`; without that edge, the toy relation admits it. This is an axiom-driven demonstration of happens-before's observable consequence, not an implementation deriving synchronization from real atomic operations. The additional test makes the premises visible rather than inferring a memory-order rule.

This result complements Scenario 61's ownership/isolation/shared-memory comparison but does not choose among them. A coherent LLMLang proposal still needs a data-race rule, atomic order lattice and defaults, mixed atomic/non-atomic policy, FFI/unsafe boundary, and conformance suite. In particular, the language must state whether ordinary safe code can reach this low-level shared-atomic API and how its guarantee composes with channels, locks, and ownership transfer.

## Reproduction

From this directory, run `python -m unittest test_rt04_store_buffering.py`.
