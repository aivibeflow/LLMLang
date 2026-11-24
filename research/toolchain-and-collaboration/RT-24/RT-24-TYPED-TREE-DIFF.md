# RT-24 — Typed semantic diff over closed Git trees

**Date** · 2026-11-21

**Baseline** · `b0142c27f5632a859c379b78a10cb22f500ebfd8`

**Status** · Bounded executable experiment for [Plan §4.5](../../../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question and alternatives

Can a reviewer distinguish a changed call target, changed guard, and physical file move before approving a merge plan? Git text gives exact physical evidence but exposes formatting as change. Comparing slot hashes removes physical layout churn but cannot explain which call changed. A typed diff can retain exact call targets and conditions, provided the matched declarations and call-site selectors are meaningful in this profile.

The fixture implements typed diff over independent closed imports. This is separate from validating a materialized candidate against an already proposed plan. The existing use-site extractor and RT-20 audit are suitable consumers or comparison points. [RT-24 diff contract](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#6-semantic-diff-contract) · [RT-20 candidate diff](../RT-20/RT-20-CANDIDATE-SEMANTIC-DIFF.md) · [Closed source inventory](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md)

## Model and observations

Pin each Git tree, inventory digest and imported semantic root. Compare selected declaration slots deterministically. Pair old and new edge selectors only where the slot, declaration ID and kind are equal. Call edges retain both the site and target selector, exact target identity, condition, and caller-required contract. A changed target produces a retarget event. A changed condition with the same target produces a modify event. For a replaced declaration, edge continuity remains unresolved.

The result carries an identity tied to the ordered semantic roots and a separate identity tied to exact source evidence. The versioned fixture policy and canonical stores determine the comparison. The semantic identity can be stable across a physical rearrangement while the evidence identity changes.

| Control | Outcome |
|---|---|
| Move a file and reorder the manifest | No selection, body or edge changes. Semantic diff identity remains equal while physical evidence changes. |
| Retarget one alternative and modify another condition in the same call site | The report distinguishes the two selectors, preserves the exact required contract, and inverts the target pair when the input order is reversed. |
| Move an equal value to a different selection slot | Reports remove and add. Equal value hashes do not establish continuity of managed occurrences. |
| Replace a declaration ID within one slot | Reports replacement without claiming edge continuity across it. |
| Candidate tree depends on a former version absent from its source | Import fails before diff. The result cannot be misread as an empty change set. |

The results favor separating semantic diff from physical evidence and pairing edges only under a declared selection policy. The fixture does not infer lineage or classify split/merge, graph roots versus internal references, external dependency locks, mapping changes, or arbitrary source-derived call completeness. RT-20 compatibility and impact dispositions remain separate. [Dependency map](../../RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01` run on CPython 3.12.14 and Git 2.52.0. The recorded run passed 12 tests. [Experiment](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_typed_tree_diff.py)

```sh
python -B -m unittest -v tests.test_rt24_typed_tree_diff tests.test_rt24_merge_tree_gate
```
