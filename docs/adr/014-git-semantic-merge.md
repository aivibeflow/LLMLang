# ADR-014: Git repository representation and semantic merge

- **Status:** Proposed
- **Date:** 2026-11-17
- **Decision owners:** LLMLang project
- **Related research:** [Git integration and Semantic Diff/Merge](../../research/GIT-SEMANTIC-REPOSITORY.md)
- **Related architecture note:** [Git Representation and Semantic Merge of LLMLang Programs](../../GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md)

## Context

LLMLang needs stable semantic identity, efficient graph lookup and incremental computation, while preserving ordinary source-control properties: reviewable changes, history, branching, cloning, collaboration, and reproducible checkout.

Git and the semantic object store have different responsibilities. Git identifies physical repository objects and snapshots; LLMLang semantic hashes identify canonical semantic content. Treating Git object IDs as semantic IDs would couple language semantics to file layout and serialization. Conversely, making an external KV store the only authoritative home of source meaning would make a Git clone incomplete and introduce a separate availability, replication, backup, and consistency dependency.

The repository representation must remain sufficient to reconstruct the semantic graph and its required indexes from declared inputs. Local caches and derived stores must not become the sole source of truth.

## Decision

Adopt the following direction for the prototype:

1. **Git remains the authoritative version-control and source-distribution layer.** The repository stores a deterministic, reviewable textual representation of LLMLang source and project metadata. A checkout must contain enough authoritative information to reconstruct the declared program state, subject to explicitly declared external dependencies.
2. **The semantic object store is a derived, content-addressed layer.** It may use KV storage and keys such as `OpHash` and `ImpHash` for lookup, deduplication, dependency traversal, and cache reuse. Its contents must be reproducible from authoritative repository inputs and pinned dependencies; a local cache is disposable.
3. **Keep identities separate.** Git blob/tree/commit IDs identify physical repository content and history. Semantic hashes identify canonical semantic content. Action keys identify computations over exact semantic inputs, tool versions, configuration, and relevant environment.
4. **Use deterministic import/export.** The toolchain imports repository source into the canonical Semantic Program Graph and exports a canonical, reviewable representation. Formatting, declaration order, and file placement must not change semantic identity unless explicitly defined as semantically relevant.
5. **Separate merge semantics from Git integration.** Implement semantic three-way merge over base/ours/theirs graph states. Git is an adapter and invocation mechanism, not the owner of semantic merge rules.
6. **Integrate incrementally with Git.** Start with a custom merge driver configured through `.gitattributes` for LLMLang files. Provide explicit local setup/doctor commands; committing attributes alone does not install the executable or local Git configuration.
7. **Fail closed.** Automatically resolve only cases where the merge rules establish a unique valid result. Report semantic conflicts, invalid merged graphs, and insufficient context instead of silently selecting a side.
8. **Validate repository-wide consistency.** A per-file merge driver is not sufficient evidence that a multi-file Semantic Program Graph is consistent. The design must provide a repository-level validation/coordinator step before accepting the merged state.

## Alternatives considered

### Store authoritative semantic objects only in an external KV database

Rejected for the initial architecture. It makes a normal Git clone insufficient to reconstruct source meaning and requires a separate sync protocol, service or shared store, backup policy, and atomic coordination with Git commits.

### Store only one opaque serialized graph blob in Git

Rejected as the primary source representation. It weakens ordinary review, produces coarse diffs, and can make small semantic edits rewrite large files.

### Treat Git blob/tree/commit IDs as LLMLang semantic identities

Rejected. Physical serialization, formatting, and file placement can change without changing semantic meaning.

### Use only Git's textual merge

Rejected as the long-term semantic merge model. Textual merge cannot reliably detect semantic identity, cross-file dependencies, or contract-level conflicts.

## Consequences

### Positive

- A Git clone remains the foundation for reproducible source checkout.
- Semantic storage can be optimized independently and safely discarded/rebuilt.
- Semantic identity remains stable across formatting and file moves.
- Git history and semantic identity are both available without conflating them.
- Merge logic can be tested independently of Git and later exposed through other integrations.

### Costs and risks

- Canonical serialization and deterministic import/export require careful specification.
- Reconstructing semantic indexes has a cost; cache performance must be measured.
- Repository-level merge coordination is more complex than a simple per-file driver.
- External dependencies must be pinned and retrievable for reproducible reconstruction.
- The prototype must verify that semantic hashes and action keys include every correctness-relevant input.

## Implementation plan

1. Specify the minimal textual repository representation and canonical import/export.
2. Prove round-trip determinism and that formatting/file moves do not change semantic hashes.
3. Implement semantic diff over stable IDs and hash-relevant content.
4. Implement three-way merge for independent additions, update/update, delete/update, rename/move, and explicit split/merge lineage.
5. Validate graph integrity and cross-file references after merge.
6. Add a Git merge-driver prototype and end-to-end tests using real temporary repositories.
7. Benchmark merge correctness, conflict rates, runtime, and cache/store reconstruction cost.
8. Revisit this ADR after prototype evidence; do not treat the Proposed status as a final commitment.

## Supersession and relationship to earlier notes

This ADR captures the current project direction and supersedes the earlier embedded ADR-0001 proposal that treated the external KV store as the authoritative home of semantic code. The earlier proposal remains preserved in the research report as historical research material. The current direction keeps Git repository source authoritative and makes KV a reconstructible derived store.
