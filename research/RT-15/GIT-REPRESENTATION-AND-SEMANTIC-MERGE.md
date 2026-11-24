# Git Representation and Semantic Merge of LLMLang Programs

**Status:** Research proposal  
**Scope:** Repository representation, Git interoperability, and semantic merge integration.  
**Normative status:** This document records an architectural direction for investigation. It does not define final LLMLang syntax, serialization, or merge semantics.

## 1. Problem

LLMLang needs both:

- a structured, content-addressed representation suitable for efficient lookup, dependency analysis, compilation caching, and reuse;
- a durable source-control representation suitable for history, branching, review, collaboration, and reproducible checkout.

A key-value (KV) or content-addressed store and Git solve different problems. The design should integrate them rather than force one to replace the other.

A related requirement follows: ordinary Git operations should be able to invoke LLMLang-aware merge logic automatically, while retaining compatibility with repositories that contain ordinary non-LLMLang files.

## 2. Separate responsibilities

### 2.1 Git repository

Git should remain the source-control and collaboration layer. It provides:

- commit history and branch topology;
- reviewable changes and diffs;
- transport, tags, and collaboration workflows;
- a reproducible snapshot of the project's declared source state.

Git object IDs identify physical Git objects and snapshots. They are not LLMLang semantic identities.

### 2.2 Semantic object store

A KV/content-addressed store should provide efficient access to canonical semantic objects by stable IDs and content hashes, graph traversal, dependency indexing, candidate discovery, and cached derived artifacts.

The store should be reconstructible from the repository's authoritative source representation plus declared external dependencies and pinned inputs. A local cache must not become the only place where a program's source meaning exists.

### 2.3 LLMLang import/export boundary

A deterministic import/export layer should translate between repository files and the canonical Semantic Program Graph (SPG):

1. parse the repository representation;
2. resolve and validate stable IDs and typed references;
3. normalize and canonicalize semantic objects;
4. populate or query the semantic object store;
5. export a canonical, reviewable repository representation.

Formatting, file ordering, and file placement should not change semantic identity unless a particular field is explicitly defined as semantically relevant.

## 3. Repository representation

The initial repository representation should be declarative and text-based, rather than one opaque binary graph file.

An illustrative layout:

```text
my-project/
├── llmlang.toml
├── program/
│   ├── manifest.llm
│   ├── operations/
│   │   ├── calculate.llm
│   │   └── validate.llm
│   ├── types/
│   ├── contracts/
│   └── tests/
└── llmlang.lock
```

This is an example only; names, extensions, and exact layout remain open.

### 3.1 Stable semantic identity

Semantic entities should have stable IDs independent of:

- filenames and directory paths;
- declaration order;
- whitespace and formatting;
- Git blob, tree, or commit IDs.

A move or rename of a file should therefore not, by itself, change the semantic hash of its contents. A semantic change should change the relevant semantic hash.

A file may contain one or more entities. The representation should not force every tiny graph node into a separate file: file boundaries should support useful review and editing, while semantic identity remains independently addressable.

### 3.2 Candidate physical layouts

| Layout | Advantages | Disadvantages | Assessment |
|---|---|---|---|
| One file per independently meaningful entity | Focused diffs, low unrelated merge contention, easy review | Many files and directory entries | Preferred starting point for independently reusable entities |
| One file per component/module | Fewer files, convenient local context | Larger diffs and more merge contention | Useful where entities are routinely edited together |
| One binary graph file | Compact and potentially fast to load | Poor diffs, review, and ordinary merges | Not suitable as the primary Git source representation |

The recommended starting point is a hybrid of the first two: use semantic boundaries to decide what can be independently reviewed, but allow cohesive groups of declarations to share a file.

### 3.3 Lock and external dependencies

A project manifest should describe direct project-level configuration and declared dependencies. A lock representation should pin exact external semantic references and other resolution inputs needed for reproducibility.

The precise division between manifest and lock file remains open. The lock representation should not duplicate full external artifacts when immutable hashes and registry references suffice.

Generated compiler outputs, object files, caches, and large derived artifacts should normally remain outside ordinary source history and be stored in the appropriate build/artifact store. Git LFS is not required for the primary textual semantic source representation.

## 4. Three distinct identities

The design must keep these identities separate:

1. **Git identity** — blob/tree/commit identity of physical repository content and history.
2. **Semantic identity** — hashes such as `OpHash`, `ImplHash`, and other typed semantic hashes, identifying canonical semantic meaning.
3. **Action identity** — an `ActionKey` identifying a computation over exact semantic inputs, action implementation, configuration, and relevant environment.

Consequences:

- Reformatting may change a Git blob and commit without changing an `ImplHash`.
- A semantic implementation change changes the corresponding `ImplHash`.
- A build or analysis result is reusable only if its full ActionKey and dependency closure match; semantic hash equality alone is insufficient.
- Git history records when and how a change was introduced; it does not define semantic equivalence.

This is consistent with the content-addressed compilation-cache model: a changed semantic node changes its semantic hash, and dependent action keys change when that node is among their exact hash-relevant inputs. No independent dirty-flag mechanism should be required for correctness.

## 5. Merge architecture

### 5.1 Design objective

A normal user workflow should be sufficient:

```bash
git merge feature-branch
git rebase feature-branch
git cherry-pick <commit>
```

When Git encounters LLMLang source files, it should be able to invoke LLMLang-aware merge logic automatically. Ordinary files should continue to use Git's normal merge behavior.

The semantic merge engine itself should be independent of Git. Git is one adapter and invocation mechanism, not the owner of LLMLang merge semantics.

### 5.2 Git custom merge driver

Git supports custom merge drivers selected through `.gitattributes`. A repository may associate LLMLang source patterns with a driver:

```gitattributes
*.llm merge=llmlang
*.llmsrc merge=llmlang
```

A local Git configuration can define the driver:

```ini
[merge "llmlang"]
    name = LLMLang semantic merge
    driver = llmlang git-merge %O %A %B %P
```

The driver receives:

| Placeholder | Meaning |
|---|---|
| `%O` | Common ancestor/base version |
| `%A` | Current-side version; the driver writes the merged result here |
| `%B` | Other-side version |
| `%P` | Repository path |

The driver should return zero only when it has produced a valid merge result in `%A`. A nonzero exit status reports a conflict or failure to Git. It must not silently choose one side when semantic correctness is unknown.

The configuration command is local to the user's Git configuration; committing `.gitattributes` does not install an executable or automatically configure every contributor's machine. LLMLang tooling should therefore provide an explicit, repeatable setup/check command (for example, a future `llmlang git install` and `llmlang git doctor`). Exact CLI names are illustrative.

A custom merge driver is invoked for file-level merges. It is not automatically a whole-repository graph merge.

### 5.3 Git mergetool

Git also supports a separately configured interactive mergetool. This can provide a human-facing interface for resolving conflicts after Git has attempted a merge.

Illustrative configuration:

```ini
[merge]
    tool = llmlang

[mergetool "llmlang"]
    cmd = llmlang mergetool "$BASE" "$LOCAL" "$REMOTE" "$MERGED"
    trustExitCode = true
```

This mechanism is useful for interactive conflict resolution, but it is not a substitute for the automatic custom merge driver. The two interfaces may coexist:

- custom merge driver for automatic semantic merging;
- mergetool for interactive inspection and resolution of remaining conflicts.

### 5.4 Whole-program graph merge

A Semantic Program Graph can span multiple files. Independently merging each file may produce a syntactically valid file set that is semantically inconsistent as a whole. Examples include:

- duplicate or conflicting stable IDs;
- references to entities removed or renamed on the other branch;
- incompatible concurrent changes to a shared contract;
- a change to one entity that invalidates assumptions in another;
- split/merge operations on semantic entities that cannot be inferred from line-level edits.

Therefore, the long-term design should support a repository-level semantic merge operation:

1. Obtain base, ours, and theirs repository states.
2. Import each state into a canonical SPG.
3. Perform a three-way semantic merge using stable IDs, typed relations, and explicit identity/lineage operations.
4. Detect conflicts at semantic boundaries, including cross-file conflicts.
5. Validate graph integrity, reference resolution, contract consistency, and relevant dependency constraints.
6. Export a canonical repository representation when the result is unambiguous.
7. Return structured conflict information when human or policy decisions are required.

A Git custom merge driver can be the initial integration interface, but a per-file invocation alone cannot guarantee whole-graph consistency. Possible future integration designs include:

- a driver that delegates to a repository-level coordinator using a prepared merge context;
- a dedicated Git integration/helper that operates on the three repository trees;
- a Git merge strategy or other plumbing-level adapter, if supported workflows require whole-tree control.

The initial implementation should not pretend that a per-file driver has access to a reliable, complete three-way repository snapshot unless that context is explicitly provided.

### 5.5 Two-stage merge and validation

The conceptual flow is:

```text
Git merge orchestration
        |
        v
LLMLang Git adapter
        |
        v
Semantic merge engine
        |
        +--> merged SPG --> validate --> export
        |
        +--> semantic conflicts --> structured report / human resolution
```

The engine should distinguish at least:

- **clean semantic merge** — a unique result is established under the merge rules;
- **resolvable semantic conflict** — alternatives are identified and require an explicit decision;
- **invalid merged graph** — structural or semantic invariants fail;
- **insufficient information** — the engine cannot establish a safe result.

A clean textual merge is not sufficient evidence of a clean semantic merge. Conversely, a textual conflict need not imply a semantic conflict if the engine can establish a valid graph result.

## 6. Merge semantics and safety requirements

The semantic merge engine should be conservative:

- Preserve stable IDs when edits concern the same continuing entity.
- Do not infer that two entities are identical merely because their names or contracts look similar.
- Treat split, merge, replacement, and lineage changes as explicit semantic operations when identity cannot be preserved unambiguously.
- Never silently resolve incompatible contract changes by choosing one branch.
- Validate references after merging, not only while parsing individual files.
- Preserve provenance for changes and conflict resolutions.
- Make merge output deterministic for identical base/ours/theirs inputs and identical merge policy/tool versions.
- Record the exact inputs and merge-engine identity when producing auditable merge evidence.
- Keep formatting-only changes from creating semantic conflicts where canonicalization can safely remove them.

Automatic resolution must be limited to cases where the merge rules establish a unique valid result. Uncertainty must remain visible.

## 7. Rename, move, split, and partial repository concerns

Git can detect physical file renames heuristically, but file rename detection must not define semantic identity. Stable entity IDs are authoritative for semantic continuity.

The design still needs explicit rules for:

- moving an entity between files;
- renaming a declaration without changing its identity;
- splitting one entity into multiple entities;
- merging multiple entities into one;
- deleting an entity still referenced by another branch's changes;
- partial checkout/sparse checkout and merges where not all graph files are present;
- submodules, packages, generated files, and external semantic references;
- concurrent edits to lock files and dependency declarations.

If the merge engine lacks the complete semantic context needed for a safe decision, it should fail closed or request the missing context rather than manufacture a result.

## 8. Recommended staged implementation

### Stage 1 — Repository source representation

- Define a canonical textual serialization for a small set of SPG entities.
- Define stable IDs and typed references.
- Implement deterministic import/export and round-trip tests.
- Prove that formatting and file moves do not change semantic hashes.

### Stage 2 — Git driver prototype

- Implement a small `llmlang git-merge` adapter using Git's documented custom-driver placeholders.
- Support three-way merge of a single file containing independently identifiable entities.
- Add `.gitattributes` patterns and a setup/diagnostic command.
- Test clean merges, add/add, modify/modify, delete/modify, rename/move, and driver failure behavior.

### Stage 3 — Semantic conflict model

- Define structured conflict types and machine-readable reports.
- Add contract and cross-reference validation.
- Add deterministic merge rules for non-conflicting changes.
- Add an interactive mergetool interface for unresolved conflicts.

### Stage 4 — Repository-level merge

- Merge complete base/ours/theirs SPGs rather than isolated files.
- Integrate with Git through an adapter that has explicit access to the three repository states.
- Test cross-file conflicts, entity split/merge, dependency changes, and partial-context failure.
- Ensure the merged source can reconstruct the same canonical SPG and semantic hashes.

## 9. Open research questions

1. What exact textual serialization should be canonical, and how should human-authored versus generated formatting be handled?
2. Should the initial merge engine merge entities independently and then validate the graph, or operate on the entire SPG from the first prototype?
3. What explicit semantic operations are needed for rename, move, split, merge, replacement, and deletion?
4. What Git integration interface gives the engine complete base/ours/theirs context without fragile dependence on incidental worktree state?
5. How should conflict reports and human resolutions be represented so that they are reviewable, reproducible, and auditable?
6. How should semantic merge interact with package/lock resolution and external immutable artifact references?

## 10. Current recommendation

Use Git for source history and collaboration, and a KV/content-addressed store for semantic-object lookup and derived-artifact reuse. Keep the repository source representation textual, deterministic, and reconstructible.

For Git integration, provide both:

- a standard custom merge driver as the first automatic integration point for LLMLang files;
- a separate interactive mergetool for unresolved conflicts.

Keep the semantic merge engine independent of Git. Design toward repository-level three-way SPG merging because cross-file graph invariants cannot be guaranteed by independent file merges alone. Do not claim whole-program semantic correctness from a file-level driver without an explicit repository-wide validation step.

## 11. Related LLMLang architecture documents and study set

This document is the primary research source for repository representation and semantic diff/merge. It must be studied together with the following documents whenever Git merge, branch integration, semantic synchronization, or commit behavior is designed or changed:

- [ADR-014 — Git repository representation and semantic merge](../../docs/adr/014-git-semantic-merge.md): records the current proposed architectural direction and rejected alternatives. Its status is **Proposed**, not Accepted.
- [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](../RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md): specifies candidate import/export laws, semantic diff classes, deterministic base/ours/theirs merge, conflict results, mapping revision separation, RT-20 CIP integration, and prototype gates.
- [RT-24 Identity and SPG Reconciliation](../RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md): reconciles the candidate merge contract with identity Studies 05–08, RT-03, the semantic dependency index, package identity, and the current executable subset. It explicitly leaves Stable Entity ID versus content-addressed identity unresolved.
- [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md): owns impact planning, per-call-site migrate/preserve/adapt decisions, caller versioning, hash propagation, validation/audit gates, and verified completion.
- [RT-22 — LLMLang Git Repository and Worktree MCP Surface](../RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md): owns the external repository/worktree operation contract, Git coordination, commit preparation, and recovery guarantees.
- [RT-23 — Single-Instance Toolchain with Shared Semantic State and Incremental Multi-Worktree File Views](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md): owns the single-server runtime, shared immutable semantic state, versioned interface mappings, per-worktree file views, and synchronized semantic/filesystem commit protocol.
- [RT-19 — Toolchain Server and Semantic Development API](../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md): owns the broader transport-neutral semantic API and Change Set/Snapshot lifecycle.
- [AIVibeFlow LLMLang MCP integration](https://github.com/aivibeflow/aivibeflow/blob/main/specs/integrations/LLMLANG-MCP-GIT-WORKSPACE.md): owns AIVibeFlow provider selection, orchestration, platform policy, and the cross-repository integration boundary.

### Ownership and consistency rules

- This document owns the overall research direction and Git merge-driver/mergetool integration direction; RT-24 refines the candidate representation, diff, merge algorithm, and conflict contract.
- RT-20 owns caller-impact completeness and semantic change validation; merge must not bypass its caller migration and hash-propagation invariants.
- RT-22 owns externally observable repository/worktree operations and their recovery contract.
- RT-23 owns runtime coordination and the invariant that a successful LLMLang commit synchronizes the exact validated semantic snapshot and selected regular-file changes into one Git commit.
- ADR-014 records a proposed decision; it does not supersede the detailed research contracts above.
- Git merge/rebase/cherry-pick is not complete for LLMLang until the merged repository representation has been imported/reconciled, the resulting semantic state validated, and the synchronized commit protocol completed. A clean per-file merge alone is insufficient.

- RT-24 owns the candidate technical contract for canonical import/export, semantic diff, three-way merge, conflict results, determinism, and its prototype/test gates. Its unresolved schema and identity assumptions remain owned by RT-05 and SPG research.

**Required study set:** read this document, RT-24, RT-24 Identity and SPG Reconciliation, ADR-014, RT-20, RT-22, and RT-23 together. For identity/schema assumptions, also read Studies 05–08, RT-03, and Semantic Dependency Index research. No standalone RT-05 specification currently exists. Include RT-19 and the AIVibeFlow integration spec when changing Toolchain API or orchestration boundaries.

## References

- Git attributes documentation: https://git-scm.com/docs/gitattributes
- Git configuration documentation: https://git-scm.com/docs/git-config
- Git mergetool documentation: https://git-scm.com/docs/git-mergetool
- LLMLang [Semantic Compilation Cache](../RT-11/SEMANTIC-COMPILATION-CACHE.md)
- LLMLang [Global Semantic Artifact Store](../RT-12/GLOBAL-SEMANTIC-ARTIFACT-STORE.md)
