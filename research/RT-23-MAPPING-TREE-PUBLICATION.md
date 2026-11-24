# RT-23 — Publish an exact interface mapping as part of the Git tree

**Date** · 2026-11-21

**Baseline** · `95f95a7`

**Status** · Bounded Git publication experiment for [Plan §4.5](../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question

When an interface mapping changes together with semantic and ordinary files, which observations can establish that the published branch contains the approved combination? The mapping-revision experiment validates exact edits and a semantic catalog in memory. Exact-tree commit recovery publishes a Git tree and receipt. This experiment ties their inputs together in one disposable repository. [Interface mapping merge](RT-23-INTERFACE-MAPPING-MERGE.md) · [Exact-tree commit recovery](RT-23-EXACT-TREE-COMMIT-RECOVERY.md)

| Representation | Consequence |
|---|---|
| Store mappings under an independent mutable reference | Supports independent lifecycle. Publication needs a transaction or explicit coordination between the mapping reference and the branch. |
| Store a canonical mapping artifact in the same tree | The branch commit and receipt can identify both domains. The artifact needs exact validation against the approved catalog and semantic snapshot. This fixture evaluates the approach. |
| Recover mappings only from semantic contents | Avoids extra tracked bytes if the mapping is derivable. The fixture maps two different namespaces and assumes those choices are independent inputs. |

## Method and results

The fixture computes a mapping candidate from two independently changed namespaces and a catalog bound to the closed semantic root. Its canonical mapping blob includes the catalog, semantic root, causal mapping revision, inputs and contents. The gate reads the candidate tree, reconstructs the semantic root and compares the complete expected mapping blob before calling the existing Git publisher.

| Control | Observation |
|---|---|
| Exact mapping, updated semantic source and approved ordinary bytes | The prepared commit and receipt publish together. Repeating the gate recovers the same commit. |
| Changed mapping bytes at the same closed semantic root | The gate rejects the mismatch and leaves the branch and receipt unchanged. |
| Same mapping blob at a changed semantic root | The catalog is rejected as stale, even though this experiment keeps its signature table equal. |
| Missing mapping blob | The gate rejects the candidate before ref publication. |

Embedding the mapping in the committed tree is sufficient for the Git publication boundary in this fixture. The catalog and approval are trusted inputs. The experiment does not derive signatures from arbitrary source, authenticate approval, manage external mapping ownership, or implement a transaction across an independent mutable mapping store and Git. It supplies a discriminator for placement and recovery, separate from compatibility evidence.

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, use CPython 3.12.14 and Git 2.52.0. Eighteen tests passed. [Mapping publication experiment](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_mapping_tree_publication.py)

```sh
python -B -m unittest -v tests.test_rt23_mapping_tree_publication tests.test_rt23_interface_mapping_merge tests.test_rt23_commit_recovery
```

## RT-36 follow-up: explicit assumptions (proposed)

Recompute policy admission and closure when exact provider or authorization changes; an atomic mapping publication alone is not proof. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
