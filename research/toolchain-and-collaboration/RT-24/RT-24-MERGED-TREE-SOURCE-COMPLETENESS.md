# RT-24 — Source completeness across a merged Git tree

- **Status** · Executable study of the first repository-wide validation gate
- **Date** · 2026-11-21
- **Plan** · §4.5, end-to-end semantic merge and synchronized commit lifecycle
- **Baseline** · `66863d1684fa366425c36961d60c57395c0511d0`, based on main `e4251f6c88219f35e6df59d889c3af4016b1ef2c`

## 1. Question

What evidence lets a semantic merge candidate advance from a Git tree to caller-impact planning? Compare Git's clean merge result, the existing exact-reference audit over an object store, and a check that also binds the graph to its declared source inventory. The study covers two branches of a closed, acyclic program and one direct callable target. [Plan §4.5](../../../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle) · [RT-24 merge contract](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#7-three-way-semantic-merge-contract)

## 2. Prior evidence and boundaries

- Git's `merge-tree --write-tree` performs a merge and writes the result tree without updating the index or working tree. Its exit status reports Git conflicts. `ls-tree` supplies the tracked tree entries for validating a declared inventory. [Git merge-tree](https://git-scm.com/docs/git-merge-tree#_description) · [Git ls-tree](https://git-scm.com/docs/git-ls-tree)
- The candidate graph audit follows stored exact references from the selected roots and checks kinds, content, and dependency metadata. The separate reverse audit compares indexed edges with a new traversal of selected declaration payloads. Both start from the supplied snapshot. [RT-20 graph audit](../RT-20/RT-20-CANDIDATE-GRAPH-AUDIT.md) · [Reverse lookup implementation](../../PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_dependency_index.py)
- RT-05 shows how equal immutable values can occupy two independently managed selections. The fixture below carries selection keys in its source comparison, even when the index stores only one edge for a shared value. [Typed SPG experiment](../../semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md#7-results-and-falsifiers)
- The proposed Git architecture treats local storage as reconstructible. RT-19 owns isolated snapshots, RT-20 owns caller obligations, RT-22 owns Git and worktree operations, and RT-23 binds validation and recovery to the exact tree ultimately committed. The experiment tests the evidence handed from the tree reader to graph validation and impact planning. [Git representation](../RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) · [ADR-014](../../../draft/adr/014-git-semantic-merge.md) · [RT-19](../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) · [RT-20](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) · [RT-22](../RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md) · [RT-23](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md)

## 3. Alternatives and falsifiers

| Approach | Evidence it consumes | Failure that distinguishes it |
|---|---|---|
| Use Git's clean result to advance | The merge algorithm reports no conflict | Both branch tips are valid and Git constructs one tree, but the tree lacks a required exact declaration. |
| Validate the candidate against the available store | Exact roots, typed edges, and transitive stored objects | A historical object in a warm store can satisfy a call even though a fresh reconstruction from the candidate fails. |
| Validate a declared, closed tree and observe incoming calls from it | Exact tree and blob inventory, fresh reconstruction, and comparison of source occurrences with the indexed values | A common omission must be detected even if the index and payload audit agree. A replay at another tree must require renewed tree evidence under this policy. |

An alternative to a closed tree would allow an immutable external import or retained-history manifest. That approach can reduce duplication if its exact dependencies are available and verified on a fresh reconstruction. It needs an explicit source of each allowed hash and its transitive closure. The prototype studies explicit retention in the candidate tree as the positive control. [RT-24 repository representation](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#4-repository-representation-contract)

## 4. Fixture and method

`program/manifest.json` declares schema version `1` and enumerates the ordinary blobs under the reserved `program/` directory. Source rows pair a fixture-local selection slot with a versioned `llmlang.semantic-object` declaration. `notes.txt` is an ordinary file outside the fixture's source inventory. The reader resolves a Git revision to its exact tree, compares the manifest with `ls-tree`, and reads each listed blob by object ID. A missing or unlisted source path makes the inventory insufficient. Version mismatch and duplicate keys or slots reject the input. The selected projection of the source comes from an initially empty Content Store and uses the existing typed declaration publisher and graph audit. [Executable fixture](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py)

The base supplies a contract and `callee` version `v1`. Ours selects `v2`. Theirs adds `caller` in a different file, pinning `v1` by exact hash and recording the required contract and call condition. Each of the three input states is imported before asking Git to merge. In the positive control, ours also includes `v1` under `callee.old`, so both exact values appear in the merged inventory. The harness verifies the common ancestor and verifies that merging has left HEAD and the working tree unchanged. [Test cases](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py)

For one exact callee, the observation traverses raw declaration rows from the verified source inventory and compares `(slot, call-site/target ID, condition, required Contract hash)` with the indexed edges expanded to selected slots. It also checks slot coverage and canonical declaration bytes. The candidate evidence binds the Git tree, inventory blob digest, observation model, and the existing reverse-query identity including its snapshot, target, scope, extractor/schema, and edge digest. The query adapter checks tree and inventory before delegating to the existing snapshot evidence validator. The observation uses a different traversal from the index, while sharing the repository, JSON parser, and prototype trust domain. [Test harness](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py) · [Dependency evidence scope](../../semantic-representation/RT-06/SEMANTIC-DEPENDENCY-INDEX.md)

The planner control holds the target hash and its recognized `implementation` policy role fixed. This isolates the fallback caused by incomplete coverage from the planner's fallback for an unknown artifact kind. [Planner implementation](../../PROTOTYPES/DEPENDENCY-GRAPH-01/src/impact_planning.py)

## 5. Results

| Claim | Evidence class | Observation |
|---|---|---|
| MERGE-01 | Experimental result | Base and both branch tips import successfully. Git produces a clean merge. Fresh import rejects the merged tree because `v1` is absent. Seeding the store from the base makes the existing structural graph audit pass and leaves exactly one reachable value absent from the declared selections, `v1`. |
| MERGE-02 | Experimental result | When the merged tree explicitly retains `v1`, fresh reconstruction resolves the new call to that exact hash. The adapter delivers the exact caller hash, site, target, condition, and required Contract hash to RT-20. |
| MERGE-03 | Experimental result | Removing the caller only from the snapshot projection produces an empty reverse index and `SUPPORTED_WITHIN_SCOPE` from the payload-only audit. The source comparison finds both the missing slot and `caller/invoke/direct`. It reports `GAP_FOUND` and causes RT-20 to add `HUMAN_REVIEW` and `FULL_REVALIDATION`. |
| MERGE-04 | Experimental result | Two selections of an equal caller produce one indexed value edge. Expanding it to occurrences matches both source slots. Removing one slot is detected even though the edge digest stays the same, and replaying the old evidence against the new snapshot returns `UNKNOWN`. |
| MERGE-05 | Experimental result | Substituting the old value into a known callee slot preserves the queried edge digest. The source-to-value comparison reports `source-value-mismatch:callee`. |
| MERGE-06 | Experimental result | The reader rejects a disappeared declared file, an unlisted tracked source file, and an unsupported manifest version. |
| MERGE-07 | Experimental result | A fresh Git clone reconstructs the same semantic snapshot after moving and reformatting one declaration file. The tree and inventory identities differ. The snapshot-only adapter accepts the old reverse evidence, while the tree-bound wrapper requires a new witness. The recomputed witness passes. |

These witnesses separate graph consistency from reproducibility from the declared source. MERGE-03 isolates loss of a declaration before both graph readers see it. MERGE-04 and MERGE-05 show why an edge digest alone provides insufficient evidence even for this closed format. Confidence is high for the bounded fixtures and depends on the complete reserved directory and the typed declaration schema. [Reproduction corpus](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py)

## 6. Consequences for merge and commit validation

- A complete inventory with an unavailable exact target yields an invalid candidate. Unresolved inventory coverage yields insufficient context. Historical target retention can advance only when the allowed source of its exact value is explicit and reconstructible. [MERGE-01/02/06](#5-results)
- Supply RT-20 with source-scoped evidence and the selected occurrences for which call decisions are needed. Rebuilding the candidate after a CIP edit requires fresh coverage for the edited inputs. The existing `ReverseLookupEvidence` binding checks remain useful within their snapshot scope. [MERGE-03/04/05](#5-results) · [RT-20 planning](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)
- Bind validation for commit preparation to the exact Git candidate tree as well as its reconstructed semantic snapshot. Equal semantic roots can permit reuse of appropriately scoped semantic evidence after checking the new tree. Git proves a physical tree identity and RT-23 still owns the final expected-ref and recovery protocol. [MERGE-07](#5-results) · [RT-23 synchronized commit](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md#92-commit-preparation-and-synchronization-protocol)

This evaluates DEP-088, RT-06 to RT-24, with concrete cases for source coverage and exact reverse edges. It also supplies bounded evidence for the RT-20 gate in DEP-091 and the RT-23 tree boundary in DEP-093. The experimental selection slots avoid choosing an identity policy. A production reader still needs parser-to-source completeness, authorized evidence producers, versioned external locks and all supported dispatch mechanisms. A semantic merge core, mapping revision, behavioral compatibility, completed caller decisions, and synchronized commit recovery are later gates. ADR-014 stays Proposed. [Dependency map](../../research-management/RESEARCH-DEPENDENCY-MAP.md#12-canonical-semantic-representation-diff-and-merge-rt-24) · [RT-24 implementation sequence](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#14-implementation-sequence-and-gates)

## 7. Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, run the fixture on Git with `merge-tree --write-tree`. All repositories are disposable, the fixture generates its inputs from constants, and each Git command has a 30-second timeout. The run used CPython 3.12.14, Git 2.52.0, and Linux 6.18.57 x86-64. Expect seven passing tests, including the controlled rejection and replay cases.

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v tests.test_rt24_merge_tree_gate
```

The seven new tests and the earlier 158-test semantic dependency selection passed together. Full Dependency Graph discovery ran 404 tests with the same failure and optional Z3 skip observed in 397 tests at the exact baseline. `test_analysis_bound_returns_unknown_not_success` expects `UNKNOWN` and receives `NEEDS_REVIEW`. [CI test selection](../../../.github/workflows/semantic-dependency-index.yml)
