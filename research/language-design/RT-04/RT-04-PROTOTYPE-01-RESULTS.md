# RT-04 Prototype 01 — Results

**Status:** exploratory executable comparison; no architecture selected  
**Updated:** 2026-11-19
**Implementation:** [RT-04 Prototype 01](../PROTOTYPES/RT-04-01/README.md)

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

52 unit tests cover primitive signatures, closed/open effects, positive/negative/unknown refinement, transitive effect propagation, explicit and ambient capabilities, duplicate/unknown resource consumption, branch-consistent and branch-inconsistent joins, branch-local double consumption, loop re-consumption, malformed CFG references, transitive effect-bound acceptance/rejection, incomplete call-graph UNKNOWN results, definite violations despite incomplete graphs, typed call arity/argument/result checks, unknown signatures, structural Result types, scoped capability authorization, path containment, grant attenuation, explicit call-site delegation, recipient acceptance, revocation propagation, unknown delegation, unknown callees/effects, and malformed input.

The CI workflow runs:

    python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v

GitHub Actions run [44320445701](https://github.com/aivibeflow/LLMLang/actions/runs/44320445701) completed successfully on commit `015a8299cb32b09c77e8bd35443bef203d196f5d`; the RT-04 step ran all 52 tests and reported `OK`. The run also passed the repository-structure checks. Earlier runs exposed two incorrect fixtures (typed callee signature omitted; missing-delegation case lacked a callee-local grant); both fixtures were corrected before this passing run. These tests cover only the exact finite declaration/CFG model and fixtures. They are not compiler tests, source-to-model correspondence proofs, runtime authorization tests, or evidence of complete dependency discovery.

## 4. Findings

1. **Refinement needs a three-valued result.** A known positive value is accepted, a known non-positive value is rejected, and missing evidence is UNKNOWN. Missing evidence must not be treated as success.
2. **Transitive effects are graph-derived.** The entry → load → read fixture propagates fs.read to entry. This is only as sound as the supplied call graph.
3. **Capability declarations and ambient authority differ.** Function-local requirements can be checked through callers in B; A checks a global ambient context. Neither proves a runtime token is authorized.
4. **Affine use requires control-flow analysis.** A linear list catches repeated consumption in one straight-line sequence. The CFG experiment additionally rejects repeated consumption on a reachable path and joins where one path has consumed a resource while another leaves it available. Mutually exclusive branches that both consume the same resource agree at the join and are accepted.
5. **Effect bounds need complete transitive summaries.** A declared `effect_bound` is checked against direct plus reachable callee effects. Acceptance requires explicit completeness assertions for every function in the reachable closure. Missing completeness evidence or unresolved callees yields UNKNOWN, never an accepted empty summary. A known out-of-bound effect remains a definite rejection even if another part of the graph is incomplete.
6. **Completeness assertions are not completeness proofs.** The prototype's `call_graph_complete` list is fixture metadata. It does not authenticate a producer or prove that source extraction discovered dynamic, generated, FFI, handler, or reflective calls.
7. **The CFG result is intentionally narrow.** Exact path-state propagation is finite for a finite resource set and converges on cycles, but can grow exponentially with resource count. It does not establish correctness of a source-to-CFG extractor or model path predicates, borrows, returns, cleanup, or terminal-path obligations.
8. **Scoped authority needs more than capability names.** The Profile B experiment checks capability identity and hierarchical path scope, rejects over-broad child grants, requires explicit caller-to-callee grant transfer and recipient acceptance, and propagates ancestor revocation to descendants.
9. **Delegation evidence must be explicit.** A missing call-site transfer for a scoped callee requirement is UNKNOWN; a known insufficient, revoked, or unaccepted grant is rejected. This closes only a fixture-level static check, not runtime authorization.
10. **The vectors expose trade-offs, not a ranking.** B has more static obligations and rejects more malformed declarations; A is simpler and leaves more obligations to runtime/convention.

## 5. Defects and unresolved semantics

Not implemented: symbolic refinements/SMT; effect-row unification and handlers; authenticated source-to-call-graph completeness; dynamic dispatch/FFI/generated-call extraction; path-sensitive branch conditions; borrow/lifetime analysis; general source-level resource transfer/return/drop/finalization; async suspension; runtime token authenticity, expiry, dynamic revocation consistency, concurrent calls, and TOCTOU checks; independent call-graph/CFG completeness evidence; concurrency/memory model; canonical SPG and hash propagation. Scenario 97 now has a bounded cleanup-error composition model and an independent ownership-obligation projection; this does not implement cleanup in source semantics or close the broader error/cancellation/fuel composition question.

The model demonstrates candidate checker obligations, not that Profile B is coherent or preferable.

## 6. Next experiments

1. Compare both vectors against RT-03 profiles A and D using shared observable traces.
2. Replace fixture-level call-graph completeness assertions with evidence bound to source/snapshot, extractor identity, scope, and assumptions; add dynamic dispatch, FFI, generated-call, handler, and reflection cases.
3. Extend Scenario 97's bounded resource-transfer/cleanup outcome model with source/path correspondence and asynchronous/divergent cleanup, then compare explicit path-state propagation with an independently reviewed reference model.
4. Define the trusted issuer/root-grant model and test revocation consistency across concurrent operations before considering runtime authorization.
5. Extend the type experiment with declared ADT constructors and explicit error propagation only after RT-03 observable semantics are defined.


## 7. RT-03 A/D × RT-04 A/B cross-profile trace check

A companion finite trace-oracle experiment now covers four shared fixtures: pure return, declared filesystem read, ordered repeated writes, and an undeclared network effect. It is documented in [RT-03/RT-04 Cross-Profile Traces](RT-04-RT-03-CROSS-PROFILE-TRACES.md) and implemented by `test_rt03_rt04_cross_profile.py`.

The combined prototype suite now contains 69 tests (the original 52 plus four cross-profile trace-oracle tests and 13 RT-03 reference-interpreter tests). GitHub Actions run [44321514801](https://github.com/aivibeflow/LLMLang/actions/runs/44321514801) completed successfully on PR head `1dd72ee542e96e49eac236db202f8eba611bbbb3`; the RT-04 test-discovery step and repository-structure checks passed. The PR documentation cross-link was merged as [PR #18](https://github.com/aivibeflow/LLMLang/pull/18). A follow-up corrected the Profile A fixture so it actually requires the declared ambient fs.read capability; the corrected test suite passed GitHub Actions run [44321753780](https://github.com/aivibeflow/LLMLang/actions/runs/44321753780) and was merged as [PR #19](https://github.com/aivibeflow/LLMLang/pull/19).

The cross-check is a small hand-authored observation oracle, not a second independent complete reference semantics. It demonstrates that RT-04's set-like effect summaries discard trace order/payload and that Profile B's open-row annotation does not yet implement row unification or handler coverage. RT-03 remains open; no architecture is selected.


## 8. Executable RT-03 A/D reference semantics slice

A bounded interpreter was added in [`rt03_reference.py`](../PROTOTYPES/RT-04-01/rt03_reference.py), with 13 tests in [`test_rt03_reference.py`](../PROTOTYPES/RT-04-01/test_rt03_reference.py). It evaluates literals, strict left-to-right integer addition, ordered sequences, explicit result-shaped values, and declared effect requests. Profile A rejects effects. Profile D uses deterministic in-memory fixture handlers for file read/write, state read/write, and network send, recording ordered events with operation, payload, and outcome.

The first CI run exposed one test fixture that declared experimental `state.read`/`state.write` labels to RT-04 Profile B without its open-row annotation; the test input was corrected rather than expanding RT-04's closed effect vocabulary. The corrected full suite ran **69 tests** and passed, together with repository-structure checks, in GitHub Actions run [44341691042](https://github.com/aivibeflow/LLMLang/actions/runs/44341691042). The implementation and documentation were merged in [PR #21](https://github.com/aivibeflow/LLMLang/pull/21).

This is a bounded reference slice, not a complete semantics or profile decision. It does not implement parsing, variables/functions/recursion, general effect handlers or row inference, Result propagation, exceptions/cancellation, resource lifecycle, concurrency, divergence, or source-to-expression completeness. Handler behavior is deterministic and in-memory only. A second independent evaluator/formal model remains required before treating the behavior as corroborated.


## 9. Differential RT-03 evaluator cross-check

A second bounded evaluator was added in [`rt03_smallstep.py`](../PROTOTYPES/RT-04-01/rt03_smallstep.py), using explicit control/value stacks and no dependency on the recursive `rt03_reference.py`. Nine differential test methods compare the two implementations over pure expressions, explicit result values, state/file/network effects, reordered writes, malformed inputs, and a generated corpus of nine two-write sequences.

The combined suite now contains 78 tests (69 previous tests plus 9 differential test methods). GitHub Actions run [44342292723](https://github.com/aivibeflow/LLMLang/actions/runs/44342292723) passed all 78 tests and repository-structure checks; the implementation was merged in [PR #22](https://github.com/aivibeflow/LLMLang/pull/22). This is algorithmically independent implementation cross-checking only; both evaluators share the same exploratory contract, so independent review and a separately derived formal semantics remain open.
