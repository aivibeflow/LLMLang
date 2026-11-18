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
| Resource use | No static affine-use check | Affine consumption with linear sequence and branch-sensitive CFG |
| Unknown refinement | Unsupported | UNKNOWN, not accepted as proof |

Both profiles compute transitive effect summaries over the supplied call graph. This isolates the comparison from a trivial direct-only-vs-transitive distinction.

## 3. Executed tests

18 unit tests cover primitive signatures, closed/open effects, positive/negative/unknown refinement, transitive effect propagation, explicit and ambient capabilities, duplicate/unknown resource consumption, branch-consistent and branch-inconsistent joins, branch-local double consumption, loop re-consumption, malformed CFG references, unknown callees/effects, and malformed input.

The CI workflow runs:

    python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v

The current run must be checked before recording a passing CI result. These tests cover only the exact finite declaration/CFG model and fixtures. They are not compiler tests, source-to-model correspondence proofs, runtime authorization tests, or evidence of complete dependency discovery.

## 4. Findings

1. **Refinement needs a three-valued result.** A known positive value is accepted, a known non-positive value is rejected, and missing evidence is UNKNOWN. Missing evidence must not be treated as success.
2. **Transitive effects are graph-derived.** The entry → load → read fixture propagates fs.read to entry. This is only as sound as the supplied call graph.
3. **Capability declarations and ambient authority differ.** Function-local requirements can be checked through callers in B; A checks a global ambient context. Neither proves a runtime token is authorized.
4. **Affine use requires control-flow analysis.** A linear list catches repeated consumption in one straight-line sequence. The CFG experiment additionally rejects repeated consumption on a reachable path and joins where one path has consumed a resource while another leaves it available. Mutually exclusive branches that both consume the same resource agree at the join and are accepted.
5. **The CFG result is intentionally narrow.** Exact path-state propagation is finite for a finite resource set and converges on cycles, but can grow exponentially with resource count. It does not establish correctness of a source-to-CFG extractor or model path predicates, borrows, returns, cleanup, or terminal-path obligations.
6. **The vectors expose trade-offs, not a ranking.** B has more static obligations and rejects more malformed declarations; A is simpler and leaves more obligations to runtime/convention.

## 5. Defects and unresolved semantics

Not implemented: call-site argument/result typing; symbolic refinements/SMT; effect-row unification and handlers; checking declared effect bounds against inferred transitive effects; path-sensitive branch conditions; borrow/lifetime analysis; resource transfer/return/drop/finalization; error/cancellation cleanup composition; async suspension; capability attenuation/revocation/delegation/runtime checks; dynamic dispatch/FFI/generated calls; independent call-graph/CFG completeness evidence; concurrency/memory model; canonical SPG and hash propagation.

The model demonstrates candidate checker obligations, not that Profile B is coherent or preferable.

## 6. Next experiments

1. Check declared effect bounds against transitive inferred effects, including unknown call edges.
2. Add typed call-site argument/result checking and a small ADT/result type.
3. Add capability scope/attenuation and distinguish static possession from runtime authorization.
4. Compare both vectors against RT-03 profiles A and D using shared observable traces.
5. Add tests that omit call edges and require UNKNOWN, never an empty dependency set.
6. Add resource transfer/return and cleanup outcomes, then compare explicit path-state propagation with an independent reference implementation.
