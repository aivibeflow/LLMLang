# RT-23/24 — Three-way merge of interface mapping revisions

**Date** · 2026-11-21  
**Baseline** · `b52ba2fb32e2c315997c74d8924c2c9aaeb177dc`  
**Status** · Bounded experiment for [Plan §4.5](../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question and approaches

Can independently edited interface mappings be combined without accepting an ambiguous export or overwriting a newer revision? The experiment uses keys of the form (namespace, interface) and values of the form (export symbol, exact signature identity). Its candidate profile permits at most one interface per exported symbol in a namespace. Other namespaces can use the same symbol independently. A catalog names a semantic root and supplies exact signatures.

| Approach | Trade-off |
|---|---|
| Merge final maps by content | Minimal history. Equal concurrent edits can coalesce, and checking final content alone misses an intervening removal and restoration. |
| Compare explicitly recorded edits and causal revisions | Conservatively rejects even equal edits to the same key, including explicit writes of the former value. Needs retained edit intent and revision ancestry. |
| Validate combined mappings and guard publication by revision plus catalog | Finds collisions between disjoint keys and binds review to a semantic root. Requires a catalog generated from the correct semantic candidate and a publication mechanism that checks all guarded inputs together. |

[RT-24 mapping domain](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#9-interface-mapping-revision-merge) · [RT-23 consistency rules](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md#8-consistency-generations-and-concurrency) · [RT-23 exact-tree recovery](RT-23-EXACT-TREE-COMMIT-RECOVERY.md)

## Experiment and results

The model imports a base and two direct children of that base, with the base itself also accepted as a tip. It checks that each child's edits reproduce its reported state. A candidate combines disjoint edit keys, validates the source states and combined mapping against one exact catalog, and records the ordered base/left/right revision identities. The resulting mapping revision has a deterministic parent set. Swapping the two tips preserves the merged revision and changes the role-sensitive candidate identity.

| Control | Observation |
|---|---|
| Independent namespaces use the same symbol | Both edits survive and the output revision is deterministic. |
| Nine pairs of same-key edits, including equal writes, delete/delete and delete/update | All pairs require review. |
| Disjoint keys introduce the same symbol into one namespace | Each proposal is valid alone. The combined mapping is rejected. |
| Catalog signature disagreement | The proposed target is rejected before publication. A separate unchanged case retains the base revision. |
| Removal and later restoration of the same logical mapping | Content returns to its former value, but the revision changes. The old publication fails. |
| Catalog moves to a different semantic root with identical signatures | The old publication fails. Explicit preparation in the new context allows publication. |
| Tip omits the edit that produced its claimed state | Reconstructing from the pinned base detects the disagreement. |

A serialized in-memory compare-and-set step checks the head tuple and catalog before replacing the selected mapping. The experiment covers revision-bound publication. A production transaction still needs durable storage, ownership authorization, arbitrary ancestry and a rule for changes that legitimately migrate a signature across catalogs. This single-catalog model conservatively requires valid old and new signatures together. It also assumes the catalog is authoritative. Mapping identity remains separate from immutable semantic object identity, repository history and commit receipt identity.

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01` run the following on CPython 3.12.14. Six mapping test methods and eight recovery test methods passed. [Experiment](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_interface_mapping_merge.py)

```sh
python -B -m unittest -v tests.test_rt23_interface_mapping_merge tests.test_rt23_commit_recovery
```

## Public-interface integration (2026-11-24; proposed)

Follow-up discriminator, not a change to reported results: the tested symbol/signature mapping is only one of public-name catalog, operation-to-provider binding and external export mapping. Test cross-map consistency and exact revision-bound conformance evidence, including disjoint edits that combine into a missing or stale provider proof. Existing CAS and collision controls are useful but do not establish contract refinement.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## RT-36 follow-up: explicit assumptions (proposed)

External mappings must bind exact assumption and provider revisions; conditional admission, authorization and proof closure remain distinct. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
