# Research Scenario 115 — Fences and the Sequentially Consistent Order

**Status:** Source-backed contract comparison plus bounded axiom-driven fence fixture; no LLMLang memory model selected  
**Research area:** RT-04 ownership/effects/memory model; RT-09 compiler; RT-10 runtime  
**Updated:** 2026-11-20

## Questions

1. How can a release fence and acquire fence synchronize through relaxed atomic operations?
2. What does C++'s sequentially consistent (`seq_cst`) total order cover, and what does it not promise when weaker operations are mixed in?

## C++ fence synchronization

The current C++ draft specifies release/acquire fences through an atomic read-from link. A release fence `A` synchronizes with acquire fence `B` when there are atomic operations `X` and `Y` on the same object, `A` is sequenced before `X`, `Y` is sequenced before `B`, and `Y` reads the value written by `X` or by a side effect in the hypothetical release sequence headed by `X` if `X` were a release operation. A fence is therefore not, by itself, a global barrier over arbitrary threads or locations; the required atomic link carries the synchronization.

Bounded publication fixture, with atomic relaxed payload and flag, both initially zero:

```text
Writer:                              Reader:
payload.store(1, relaxed);           r = flag.load(relaxed);
release_fence();                     if r == 1 {
flag.store(1, relaxed);                  acquire_fence();
                                         observed = payload.load(relaxed);
                                     }
```

When the reader's flag load reads from the post-fence writer store, the stipulated fence-to-fence relation excludes stale `observed == 0`. If the load has no such read-from/release-sequence link, this fixture derives no synchronization edge and allows `{0, 1}`. The prototype maps this premise to the allowed payload set; it does not execute the code or infer read-from.

## What `seq_cst` adds

The current C++ draft requires one total order `S` over all `seq_cst` operations, including `seq_cst` fences, subject to strongly-happens-before and atomic-coherence constraints. It makes `S` consistent with each object's modification order and constrains values observed by `seq_cst` loads. The draft explicitly warns that this total order is not required to be consistent with all happens-before edges when acquire/release operations are mixed in. It further states the broad sequential-consistency guarantee only for a data-race-free program using exclusively `seq_cst` atomic operations; weaker orders can invalidate that guarantee.

Thus the useful distinction is:

| Claim | Scope |
|---|---|
| One order for all `seq_cst` operations and fences | The standard's `S` order with its stated constraints |
| A single sequentially consistent interleaving for the whole program | Only under the draft's stated conditions; mixing weaker operations requires reasoning from the full rules |
| Fences synchronize any preceding/following memory automatically | Not guaranteed; fence synchronization requires the specified atomic link |

Scenario 113's global-order enumerator models one all-operations sequentially consistent candidate profile. It is not a general C++ checker for mixtures of relaxed, acquire/release, fences, and `seq_cst` operations.

## Evidence and limits

[`fence_publication_payload_outcomes`](../PROTOTYPES/RT-04-01/rt04_store_buffering.py) takes an explicit fence synchronization premise and returns `{1}` or `{0, 1}` for a relaxed atomic payload. One test checks both branches. The fixture does not derive the atomic relation, model fence placement errors, or validate compiler/hardware behavior. The source comparison is normative reference evidence; it is not a LLMLang design choice.

The open language questions remain whether fences are exposed at all, how source-level atomic operations bind to them, which mixed-order combinations are allowed, how the global order is specified, and how each candidate backend preserves those observations across targets.

## Sources

- [C++ draft — atomic orderings, coherence, and the `seq_cst` order (`atomics.order`)](https://eel.is/c++draft/atomics.order)
- [C++ draft — fences and their synchronization conditions (`atomics.fences`)](https://eel.is/c++draft/atomics.fences)
- [C++ draft — complete atomics clauses](https://eel.is/c++draft/atomics)
