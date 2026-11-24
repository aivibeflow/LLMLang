# RT-05 — Admission of imported typed graphs

**Date** · 2026-11-21  
**Baseline** · `017e64b87c87371309197a392165258b8b088dd1`  
**Status** · Bounded executable experiment for [Plan §1.1](../../../PLAN.md#11-semantic-program-graph-and-program-representation)

## Question and alternatives

Can a store expose an imported graph to the evaluator or dependency reader after validating its content addresses? The [typed SPG experiment](RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) already demonstrated persistence and replay for compiler output. Here the producer can construct a different payload and compute valid addresses for it.

| Admission policy | Trade-off |
|---|---|
| Verify persistence and trust an authorized producer | Reuse existing store checks with low additional cost. Consumers depend on the producer checking types, selections, and dependencies before publication. |
| Verify persistence and check the typed graph independently | Read the typed instruction tree, reconstruct call uses, and check declarations and edges before handing off to consumers. This requires a version-matched checker and does not establish source correspondence. |
| Rebuild from the pinned source inventory and compare | Reconcile compiler output and source selection, including declared references that never appear in a graph supplied by a producer. Requires the exact source, profile, resolver, and independently established inventory closure. |

The independent check borrows the shape of validation over typed instructions and declarations from [WebAssembly Core validation](https://www.w3.org/TR/wasm-core-2/#validation). The SPG fixture additionally checks agreement between executable references and the store's typed edges. [RT-24 merged-tree source completeness](../../toolchain-and-collaboration/RT-24/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) gives evidence for the separate source inventory requirement.

## Model and experiment

Run the generic persistence reader first. For one selected snapshot, check the kind of each selected value, operation interfaces and contract edges, and bindings keyed to the exact operation their provider declares. Read each selected implementation's stored instruction tree, infer its result type under the interface parameters, and consume one reference slot per call in compiler preorder, including calls in both conditional arms. Exact calls require a selected implementation. Operation calls require a selected binding. The declared `uses` edges must equal the set of the owner and all referenced targets. Ordered and repeated calls remain distinct in the tree and reference vector.

The experiment uses the current acyclic exact-reference encoding, with integer and Boolean values and ordered events. It compares the existing reader with an independent checker that reads stored instructions directly. It preserves unused historical store values without treating them as selected candidates or alternate providers. Exact recursive groups are outside this checker profile. Binding-resolved runtime recursion and termination require a separate judgment.

## Results

| Control | Persistence | Independent check |
|---|---|---|
| Compiler output with an exact call nested inside an operation call | Admitted | Admitted. Fourteen observations matched the numeric result and ordered event oracle. |
| Stored Boolean return under an integer interface | Admitted | Rejected. Unchecked evaluation returned Python `True`. |
| Call with a Boolean argument, missing use edge, unused reference, invalid position, or malformed argument position in an unchosen branch | All five admitted | All five rejected. The call with a missing use edge remained executable, so an edge-only dependency walk could omit work. |
| Removed provider selection, binding selection, or operation selection, with old values retained in the store | All three admitted | All three rejected. |
| Valid compiler-produced exact recursive group | Admitted | Rejected as outside the supported encoding. |
| Well-typed body emitting an event absent from its declared trace set | Admitted | Admitted structurally. The evaluator observed the unexpected event. Contract conformance needs separate evidence. |

The nine malformed or incomplete graphs were serialized and re-read with internally consistent value and root digests. For the missing-edge witness, inspecting only blob integrity or replaying the selected input gives success. The witness directly bears on DEP-009 and the closed merge candidate boundary of DEP-087. It does not establish RT-06 source coverage, provenance, behavior under foreign effects, or correctness for other schema versions. The experiment validates the loaded logical graph. Raw wire canonicalization and resource limits for decoding remain outside its scope.

The evidence favors a typed admission check where an exact graph can be supplied independently of the trusted lowering path. Trusted rebuild remains a useful comparison where source is authoritative. Choosing between these designs requires extension to recursive groups, workloads with representative graph sizes, and a source-to-graph completeness check. The canonical schema and language profile remain open.

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` using CPython 3.12.14. The recorded run was on Linux 6.18.57 x86-64 and reported 16 passing tests across the two modules.

```sh
python -B -m unittest -v tests.test_spg_representation tests.test_spg_admission
```

[Checker](../../PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_admission.py) · [Fixtures](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_admission.py) · [Dependency map](../../RESEARCH-DEPENDENCY-MAP.md)
