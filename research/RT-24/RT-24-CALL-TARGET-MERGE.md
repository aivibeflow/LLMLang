# RT-24 — Independent call-target changes in one declaration

**Date** · 2026-11-21

**Baseline** · `6aaac55`

**Status** · Bounded three-way merge experiment for [Plan §4.5](../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question and merge laws

When both branches edit the same caller, under what assumptions may a structural merge retain both changes? The existing slot-level merge treats competing body addresses as an update/update conflict. This fixture compares it with a narrower rule that can merge independent exact retargets within a declaration whose call occurrences are already identified. [Closed-inventory merge](RT-24-CLOSED-THREE-WAY-MERGE.md)

The new rule applies only to one explicitly designated fixture caller. Its declaration ID, opaque content, reference list, and call selectors must agree across the base and tips. Only an alternative's exact target address may change. Stable site and target selectors are an input assumption. The rule does not infer identity across moved or rewritten bodies.

| Approach | Consequence |
|---|---|
| Whole-slot three-way merge | Conservative where a declaration has opaque or unvalidated internal structure. Requires review even when each branch touched a different call. |
| Compose exact retargets of unchanged selectors | Retains independent edits and reports a conflict when branches pick different providers for the same selector. Requires a trustworthy selector correspondence and a fresh whole-graph import. |
| Automatically propagate every changed caller address | Could keep some upstream references closed. It also rewrites callers whose selected version was intentional, so RT-20 needs explicit migrate/preserve decisions and separate validation. |

## Results

All three input states are imported from Git independently. The candidate's entire declaration inventory is reconstructed in a fresh store. Exact input trees, inventory digests and semantic roots remain in evidence.

| Control | Observation |
|---|---|
| Retarget two different calls in the same caller | The candidate retains both exact target addresses. Swapping the branches preserves export bytes and semantic selections. |
| Retarget the same selector differently | The merge reports the conflicting site and target selector. |
| Change a guard alongside a retarget | The retarget merge law refuses the wider edit. |
| Preserve the old caller version for an existing upstream caller | Whole-graph reconstruction succeeds and the upstream address stays equal. |
| Add an upstream caller pinned to one branch's version | Both tips import independently. The composed caller gets a distinct address, leaving the branch-specific exact pin unresolved. The candidate fails closed. |

The evidence supports narrower structural merge rules where both scope and correspondence are explicit. The result remains a structural candidate. Contract identity does not prove compatibility, and stable selectors in this fixture do not establish source occurrence continuity in arbitrary code. Mapping changes, dynamic targets, parallel body edits, rebase/cherry-pick, approval and publication remain separate.

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01` run on CPython 3.12.14 and Git 2.52.0. All 18 focused and baseline tests passed. [Fixture](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_call_target_merge.py)

```sh
python -B -m unittest -v tests.test_rt24_call_target_merge tests.test_rt24_semantic_merge_core tests.test_rt24_merge_tree_gate
```

## Exact retained reproduction (2026-11-21)

The declared command passed **18/18 tests** on exact checkout `fa98a20c8ab5d3f28980b609c04aaec135dddde5` under CPython 3.12.14 and Git 2.56.1. See [workflow run #44950912463](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463) and retained artifact [14725820800](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463/artifacts/14725820800). The artifact records the report/test/implementation SHA-256 values and log digest `e8896e6e060b87235e1c9ef7f74dae922d302c2823216c6f4ec2f3000f834b80`. The declared Git 2.52.0 environment is not reproduced by this run; the observed version is 2.56.1.

## Public-interface integration (2026-11-24; proposed)

Follow-up: retargeting two direct concrete calls is distinct from replacing a scoped public provider binding. Add controls where independent changes to public contract and provider selection merge structurally but invalidate refinement evidence; validate the complete candidate before publication. Existing exact-retarget results remain bounded to the original fixture.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This follow-up does not change earlier results or accepted rules.
