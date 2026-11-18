# RT-04 Prototype 01 — Results

**Status:** exploratory executable comparison; no architecture selected  
**Date:** 2026-11-18  
**Implementation:** [RT-04 Prototype 01](PROTOTYPES/RT-04-01/README.md)

## 1. Question

Can two small type/effect/ownership/capability vectors be made executable against the same declarations, exposing meaningful differences without assuming complete LLMLang semantics?

## 2. Compared vectors

| Dimension | Profile A | Profile B |
|---|---|---|
| Base types | Primitive types | Primitive types plus PositiveInt refinement experiment |
| Effects | Closed effect vocabulary | Effect-row annotation plus transitive summary |
| Capabilities | Ambient program context | Explicit function requirements propagated through calls |
| Resource use | No static affine-use check | Per-function at-most-once consumption |
| Unknown refinement | Unsupported | UNKNOWN, not accepted as proof |

Both profiles compute transitive effect summaries over the supplied call graph. This isolates the comparison from a trivial direct-only-vs-transitive distinction.

## 3. Executed tests

12 unit tests cover primitive signatures, closed/open effects, positive/negative/unknown refinement, transitive effect propagation, explicit and ambient capabilities, duplicate/unknown resource consumption, unknown callees/effects, and malformed input.

**Local execution:** `python -m unittest -v` — **12 tests passed**.

This is limited to the exact finite declaration model and fixtures. It is not a compiler test, source-to-model correspondence proof, runtime authorization test, or evidence of complete dependency discovery.

## 4. Findings

1. **Refinement needs a three-valued result.** A known positive value is accepted, a known non-positive value is rejected, and missing evidence is UNKNOWN. Missing evidence must not be treated as success.
2. **Transitive effects are graph-derived.** The entry → load → read fixture propagates fs.read to entry. This is only as sound as the supplied call graph.
3. **Capability declarations and ambient authority differ.** Function-local requirements can be checked through callers in B; A checks a global ambient context. Neither proves a runtime token is authorized.
4. **Affine use catches one narrow class of error.** B rejects duplicate consumption in one function. It does not model control-flow joins, borrow conflicts, task transfer, or cleanup.
5. **The vectors expose trade-offs, not a ranking.** B has more static obligations and rejects more malformed declarations; A is simpler and leaves more obligations to runtime/convention.

## 5. Defects and unresolved semantics

Not implemented: call-site argument/result typing; symbolic refinements/SMT; effect-row unification and handlers; checking declared effect bounds against inferred transitive effects; branch-sensitive affine dataflow; borrowing/lifetimes; capability attenuation/revocation/delegation/runtime checks; dynamic dispatch/FFI/generated calls; independent call-graph completeness evidence; error/cancellation/finalizer composition; concurrency/memory model; canonical SPG and hash propagation.

The model demonstrates candidate checker obligations, not that Profile B is coherent or preferable.

## 6. Next experiments

1. Add branch-sensitive resource-state dataflow with join-point consistency.
2. Check declared effect bounds against transitive inferred effects, including unknown call edges.
3. Add typed call-site argument/result checking and a small ADT/result type.
4. Add capability scope/attenuation and distinguish static possession from runtime authorization.
5. Compare both vectors against RT-03 profiles A and D using shared observable traces.
6. Add tests that omit call edges and require UNKNOWN, never an empty dependency set.
