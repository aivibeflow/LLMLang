# RT-19 — Multi-file publication boundary recheck

**Research item:** `PLAN.md` §7.6 — Toolchain Server and semantic development API  
**Date:** 2026-11-24  
**Baseline main:** `dec70dfe8f603661ef6777d121dbc830ea6818e4`  
**Evidence type:** source-bound comparison of publication mechanisms plus a focused rerun of the current Toolchain prototype  
**Status:** bounded comparison; no repository format or publication backend selected  
**Question:** How should an accepted semantic snapshot become a multi-file Git-visible tree without exposing a mixed or stale generation?

## Current evidence boundary

Prototype 01 accepts a snapshot in process memory and exports one canonical JSON file. The implementation writes a temporary file in the destination directory, flushes and `fsync`s its contents, then uses `os.replace`; an optional previous-file digest detects external edits. Its 9 focused tests passed on this current-main checkout. The prototype README explicitly excludes multi-file generations, Git integration, persistence, crash recovery, and cross-process locking. Therefore the test result supports a single-file replacement boundary only.

ADR-014 requires Git-visible canonical inputs to reconstruct meaning, separates physical Git identifiers from semantic hashes, and requires repository-level validation because per-file operations cannot establish whole-graph consistency. The RT-19 protocol comparison separately leaves multi-file export and Git reconciliation open. These constraints are used here as comparison premises, not as evidence that any candidate has been implemented.

## Candidate publication mechanisms

| Candidate | Visible unit | Failure / recovery behavior | Main strengths | Main costs and unresolved risks |
|---|---|---|---|---|
| **P-A: replace files one by one, then write a root/manifest last** | Readers can observe a mixture until the final manifest is published; readers that pin and verify a manifest can reject mixed generations | Restart scans generation IDs and validates every file hash against the manifest; incomplete generations are ignored or cleaned | Simple ordinary files and reviewable layout; can publish without replacing a directory | Not an atomic multi-file visibility boundary; all readers must pin a generation and fail closed; stale files/deletions and directory fsync semantics need rules |
| **P-B: write immutable generation directory, then atomically switch a pointer** | One pointer or symlink changes the selected generation | Old and new generations coexist; restart validates pointer target and generation manifest, then garbage-collects unreachable generations | Readers can pin one complete immutable generation; staging failures do not alter current generation | Atomic pointer replacement and durability vary by filesystem/OS; path traversal, permissions, concurrent publishers, and checkout portability need explicit support; symlink policy can be restrictive |
| **P-C: build and validate exact Git tree/index, then commit/ref-update as publication receipt** | A Git tree/commit identifies the complete candidate; branch/ref update is the publication boundary | Before ref update, old commit remains authoritative; after update, recover from the commit; retry locates commit by operation/root identity | Fits Git-authoritative reconstructibility; whole-tree hash is already available; no runtime reader needs a mutable multi-file filesystem generation | The worktree/index can still show staged or mixed files to local tools; accepted-but-uncommitted state needs durable outbox; ref concurrency and external edits need CAS/reconciliation; commit-as-receipt does not replace a workspace journal |

P-A only gives atomicity to readers that honor the generation manifest protocol. P-B makes that protocol visible in the filesystem namespace but depends on supported atomic pointer replacement. P-C gives the clearest authoritative whole-tree receipt, but it must be coordinated with the pending accepted workspace and must not equate Git object identity with semantic identity.

## Bounded recommendation for the next experiment

Use the RT-19 logical split already identified: the durable workspace journal owns accepted root, operation ID, and pending publication receipt; immutable content can be prepared independently; Git remains the reconstruction authority. For the next implementation slice, stage all canonical files and deletions in a private generation, compute and validate the exact tree against the accepted semantic root, then publish through a compare-and-swap Git ref update. Treat the Git commit as the synchronized receipt, not as the pre-publication acceptance transaction.

This favors a staged private generation plus exact Git tree/ref publication as the experiment to implement. It does not require a permanent generation-directory repository layout: the adapter may materialize the tree into a temporary worktree/index. Do not report export complete until the ref points at the exact validated tree. On retry, operation ID plus semantic root and tree ID must identify an already completed publication. Unexpected edits or a changed expected ref should return a conflict and leave the accepted pending operation available for reconciliation.

## Required discriminating checks

1. Inject termination during generation writing, after tree validation, before ref update, and after ref update but before journal receipt.
2. Reopen the journal and repository; verify no partial tree is accepted, and that a completed ref update is recorded without a duplicate commit.
3. Exercise file additions, replacements, deletions, renames, modes, symlinks policy, and paths containing unusual but valid characters.
4. Race two publishers against the same expected ref and require exactly one CAS winner; preserve the loser as a conflict.
5. Modify the worktree externally during staging and verify the coordinator either publishes the pinned tree or refuses; it must never silently absorb the unrelated edit.
6. Compare durability and supported-platform behavior of temporary index/worktree staging with any directory-pointer implementation before making filesystem claims.

These are proposed checks, not tests run by this recheck. The 9/9 current prototype test result does not cover them.

## Remaining dependencies

- Persistent accepted-workspace journal and idempotency key lifecycle.
- Canonical SPG/source import-export format and complete root-to-file projection.
- Supported Git versions, ref CAS mechanism, worktree/index isolation, and filesystem durability matrix.
- External edit reconciliation, authorization, concurrent workspaces, and multi-file failure injection.
- Maintainer approval of the proposed Toolchain workflow/ADR remains an external decision.

**Conclusion:** ordinary per-file atomic replacement does not make a semantic snapshot atomic. The most useful next discriminator is whole-tree validation followed by an exact Git-ref publication receipt coordinated with durable accepted-pending state. Repository layout and production selection remain open.
