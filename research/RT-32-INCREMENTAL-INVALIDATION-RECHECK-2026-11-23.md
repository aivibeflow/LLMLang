# RT-32: Incremental analysis and invalidation recheck

**Date:** 2026-11-23  
**Baseline:** `7cbdd1b6db4c30c617abe784b3bdf36e9ddeba60` (`main`)  
**Scope:** compare invalidation/reuse rules in the existing cache proposal and dependency-graph impact-planning prototype. This is a bounded model recheck, not compiler integration or a normative decision.

## Result

The evidence favors content-addressed action results over timestamps or dirty flags. Reuse is justified only when the action identity covers all result-determining semantic inputs, configuration, and relevant tool/environment identity, and the dependency closure is known complete. A changed `ImplHash` changes dependent action keys only where the corresponding action consumes that implementation or a derived result. Reverse edges can find/schedule affected actions; they do not establish completeness by themselves.

| Strategy | Correctness/reuse properties | Assessment |
|---|---|---|
| Invalidate everything | Conservative when the invalidation boundary is truly complete; discards unrelated work | Safe fallback, costly for local changes |
| Content-addressed ActionKeys over complete dependencies | Reuses unaffected results and separates semantic object, computation, and output identity | Preferred candidate; correctness is conditional on completeness and deterministic/captured inputs |
| Timestamps/dirty flags | Cheap hints, but do not encode semantic identity or hidden dependencies | Scheduling hints only; insufficient authority for cache reuse |
| Unknown dependency closure | Cannot show that old result still applies | Fail closed: full revalidation or mark non-cacheable until completeness is established |

The affected action policy is stage-specific: re-derive semantic/type and contract analyses when their semantic inputs change; regenerate tests when their test specification or generated test input changes; run tests against changed implementation, contract, environment, or test inputs; rebuild code-generation/optimization outputs when their ActionKey inputs change; and re-prove only when the checked property, assumptions, proof inputs, or verifier identity changes. Evidence can become stale even when the semantic object did not change (for example, verifier/tool identity or evidence scope changes); conversely, a semantic change can affect downstream results even when no prior evidence exists. Semantic impact and evidence applicability therefore need separate relations.

Non-semantic metadata can be excluded from action identity only after a canonical semantic projection demonstrates that it cannot affect results. The current prototype includes determinism and field-sensitive action identity cases, but does not define a production metadata schema or prove such a projection for compiler inputs.

## Reproduction

On CPython 3.12.14, from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, ran:

```text
python3 -B unittest suite: tests.test_impact_planning,
tests.test_dependency_discovery, tests.test_semantic_dependency_index
Ran 72 tests; 0 failures, 0 errors, 0 skipped.
```

The tests exercise scoped completeness evidence, stale/missing evidence, conservative fallback for unknown completeness, action planning and deterministic identity, and dependency discovery/index behavior. They are synthetic prototype tests; they do not execute a production compiler cache. Relevant source hashes at the baseline: `impact_planning.py` `d349799ab9579923fd86ef68fa2a93537ae183843b9b59b742f5ff7a63cdaad1`; `test_impact_planning.py` `eb9fa3b9c9489c8b36b0a17cb8665784b7eeea8541e8e04de224d996dbd1ff11` (SHA-256).

## Remaining evidence and decisions

- Integrate invalidation across actual type checking, contract checking, optimization, code generation, tests, and proof actions, with complete input capture.
- Specify and validate semantic projections for metadata-only changes and property-specific evidence freshness.
- Demonstrate impact/non-interference gates against source-derived dependency discovery, including external/environmental inputs and unknown cases.
- Benchmark local edits, shared-component edits, and broad semantic changes on controlled representative workloads; the current action-count fixtures are not runtime performance measurements.
- Select canonical identity formats, cache compatibility/trust rules, and production fallback behavior.

Thus §3.2 remains partially researched/prototyped; this report narrows the candidate rule but does not close its checkboxes or choose a production implementation.
