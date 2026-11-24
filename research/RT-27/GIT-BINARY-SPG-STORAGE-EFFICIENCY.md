# Git Storage Efficiency for Immutable SPG Objects

**Status:** Preliminary research; architecture decision pending  
**Date:** 2026-11-23  
**Plan area:** Stage 4 — Semantic storage, versioning, and Git integration  
**Scope:** Git packfile storage efficiency when the logical SPG state changes only by adding and removing immutable objects.  
**Non-goal:** This report does not select the canonical SPG serialization, identity model, shard key, or semantic merge algorithm.

> **Core workload assumption:** An existing SPG object is immutable. A repository-state transition adds new objects and/or removes objects from the selected graph state; it does not rewrite an existing object's payload. This is a workload assumption for storage research, not a decision about stable entity identity, lineage, or the exact meaning of deletion.

## 1. Executive summary

Git can store binary blobs efficiently across history. A packed Git object is represented either as a compressed whole object or as a delta against another object. A delta reconstructs the target from a base object using copy and insert instructions. Git therefore does not require every historical version of a binary container to occupy a complete independent copy.

This is promising for SPG containers whose records are immutable and whose serialized order remains stable:

- Appending records can leave most previous byte ranges unchanged.
- Removing records while preserving the order of survivors can leave large reusable byte ranges.
- Rewriting/reordering many records, changing offsets or headers globally, or changing compression output can reduce similarity and worsen deltas.
- Git's delta search is heuristic and bounded; good compression is not guaranteed.
- Git delta compression is a storage optimization only. It does not provide semantic diff, semantic merge, or conflict safety.

**Preliminary recommendation:** keep bounded stable shards as the primary candidate and immutable segments as a competing candidate. Do not select a layout until a reproducible long-history benchmark compares them using realistic SPG object distributions and branch patterns.

## 2. Git storage behavior relevant to SPG

### 2.1 Packfiles and deltas

Git packfiles store objects as either whole compressed objects or deltas against base objects. Packfiles are self-contained: the base needed to reconstruct a delta must be available in the pack. The pack index supports locating packed objects.

The delta representation consists of instructions that reconstruct a target object from a base object. It is not a semantic record-level diff; it operates on byte sequences.

Sources:
- [git-pack-objects](https://git-scm.com/docs/git-pack-objects)
- [pack-format](https://git-scm.com/docs/pack-format.html)

### 2.2 Delta candidate selection

Git's pack operation groups candidate objects using heuristics involving object type, size, and path/name locality, then compares candidates within a bounded window. The documented defaults are `pack.window=10` and `pack.depth=50` for `git pack-objects`; configuration and command options can change packing behavior. Delta depth limits the work required to reconstruct an object.

Consequences for SPG:
- Revisions of the same shard at the same path are plausible delta candidates.
- Stable shard paths and sizes can help candidate locality, but do not guarantee that Git will select a particular base.
- A small delta is not guaranteed merely because the logical change is small.
- Repacking configuration, Git version, history shape, and object reachability can affect results.

Source: [git-pack-objects — delta compression options and heuristics](https://git-scm.com/docs/git-pack-objects).

### 2.3 Large-object threshold

The current Git documentation states that the default `core.bigFileThreshold` is 512 MiB. Objects above the configured threshold are stored deflated in packfiles without attempting delta compression. The threshold is configurable.

This is a meaningful constraint for SPG container design. It is not a recommended target size: the benchmark should test multiple substantially smaller shard sizes and leave operational headroom. Do not design around the assumption that a very large single container will receive useful inter-version deltas.

Sources:
- [git-config: core.bigFileThreshold](https://git-scm.com/docs/git-config.html)
- [git-pack-objects](https://git-scm.com/docs/git-pack-objects)

### 2.4 Git history versus the working tree

A checked-out file is materialized as a complete blob even when its packed historical representation is a delta. Git's internal delta compression reduces object-database and transfer storage; it does not make random access to an individual SPG record automatic.

The SPG format still needs record boundaries, an index or lookup strategy, integrity checks, and deterministic import/export.

### 2.5 Deletion and reachability

Removing an object from the current semantic state does not erase its historical bytes from Git. Earlier commits may still reference a tree/blob containing that object. This is desirable for history and rollback.

A tombstone is therefore a semantic/storage representation choice, not a requirement for Git to preserve history. A tombstone may be useful for append-only segment interpretation, but it has its own index, compaction, and conflict semantics.

## 3. Expected behavior for the SPG add/remove workload

Assume a container serializes records in a stable order:

`[A][B][C][D]`

### 3.1 Append

Transition:

`[A][B][C][D] -> [A][B][C][D][E][F]`

The old prefix remains byte-identical. A delta can copy the old prefix and insert the new suffix. This is a favorable pattern, subject to Git's candidate-selection and threshold behavior.

### 3.2 Delete while preserving survivor order

Transition:

`[A][B][C][D][E][F] -> [A][B][D][F]`

The new representation can reuse ranges corresponding to surviving records and omit deleted ranges. The number and size of copy ranges, container framing, offset tables, checksums, and index layout all affect the resulting delta.

### 3.3 Delete followed by compaction

Compaction may rewrite a container or segment. If it preserves record bytes and order, Git may still find common ranges, but a new layout, changed block compression, regenerated offsets, or global headers can reduce similarity. Compaction also adds new historical blobs; old commits continue to retain old states while reachable.

### 3.4 Reordering and unstable serialization

A serializer that changes record order between exports can make a small logical change look like a large byte-level change. Deterministic serialization alone is insufficient if ordering is deterministic but depends on a mutable property. The ordering key must itself be stable under the selected identity/placement model.

Do not use content hash as a shard key or placement key until the identity and update/lineage model explicitly permits it. This research does not choose that model.

## 4. Candidate layouts

| Candidate | Add | Delete | Git delta prospects | Main cost/risk |
|---|---|---|---|---|
| One large mutable container | Rewrite affected container | Rewrite affected container | Potentially good if bytes/order remain stable; avoid exceeding big-file threshold | Large rewrite/materialization and poor random access |
| Bounded stable shards | Rewrite only affected shards | Rewrite only affected shards | Potentially good; limits blob size and unrelated changes | Requires stable placement and balanced shards |
| Immutable segments | Add new segment | Tombstone or new selection/index state | Existing segments stay unchanged; new segment stored once | Segment accumulation, manifest/index growth, compaction |
| Chunked records inside bounded containers | Rewrite affected chunks/container metadata | Remove or mark records/chunks | May localize byte changes if chunk boundaries remain stable | Chunk index, fragmentation, boundary stability |
| Independently compressed blocks | Add/remove compressed blocks | Remove block or tombstone | Can preserve unchanged compressed blocks; Git delta may be less useful within compressed payloads | Compression framing and per-block metadata |

### 4.1 Bounded stable shards

This is the strongest initial candidate to benchmark:
- keep the number of tracked files bounded;
- place many records in each shard;
- use a stable deterministic placement rule;
- cap shard size well below the default large-object threshold;
- keep object records and framing deterministic;
- update only shards touched by additions/removals.

Potential shard keys (type, stable ID range/prefix, or another stable partition key) remain alternatives. The selected key must not depend on unresolved identity assumptions.

### 4.2 Immutable segments

This remains a serious alternative, especially if append throughput, independent writes, or concurrent segment production dominates.

The design must specify:
- how the current state is derived from segments;
- how deletion is represented;
- how conflicting additions/deletions are reconciled semantically;
- how manifests/indexes avoid a single hot mutable file;
- how compaction is triggered and made deterministic;
- how the full state is reconstructed from Git alone.

Do not use timestamp-based or last-record-wins semantics to resolve competing versions of one logical object.

### 4.3 Chunking and compression

Chunking within a bounded container may localize changes, but it must not turn into one tracked file per SPG object. Content-defined chunking and fixed-size chunks are both candidates for experiments, not selected design choices.

Pre-compressing blocks can reduce raw storage, but compressed bytes may have lower inter-version similarity. Independent compression may preserve unchanged blocks; a single compression stream may cause changes to affect subsequent bytes. Measure both rather than assuming one is better.

## 5. Preliminary experimental observation and evidence limitation

A prior exploratory session reported a two-commit synthetic Git experiment with 30,000 records of 192 bytes each (about 5.76 MB of record payload), followed by `git gc --aggressive`. Reported packfile sizes were approximately:

| Case | Reported packfile size |
|---|---:|
| One container, append 1% | 5,508,156 bytes |
| One container, delete 1%, compact | 5,454,076 bytes |
| One container, delete 1%, tombstones | 5,455,510 bytes |
| Immutable segment append | 5,509,012 bytes |
| Immutable segments with tombstones | 5,455,077 bytes |

The session also reported small deltas for the changed container versions (156 bytes for append and 671 bytes for deletion).

**Evidence status: unverified exploratory observation, not a reproducible result.** The fixture, generator, exact Git commands/configuration, repository object inventory, Git version output, raw command logs, and pack inspection were not preserved with the measurement. These numbers must not be used as acceptance evidence or as a basis for choosing a layout. Re-run the experiment from a committed fixture before relying on any quantitative conclusion.

The only defensible qualitative takeaway is that Git's documented delta mechanism makes this workload promising enough to benchmark. The measurements above are retained for traceability, not treated as validated findings.


## 5.1 Executed reference benchmark (2026-11-23)

The committed reference harness was executed five times with identical inputs. Each repetition created five independent repositories, each with a baseline commit and one changed-state commit, then ran `git gc --aggressive --prune=now`.

**Environment and fixture**

- Git: `git version 2.47.3`
- Python: `3.13.5`
- Platform: `Linux-6.18.57-x86_64-with-glibc2.41`
- Initial state: 30,000 fixed-size records × 192 bytes = 5,760,000 payload bytes
- Change: 300 additions or 300 deletions (1%); seed `20261123`
- Repository-local config: `core.bigFileThreshold=512m`, `pack.window=10`, `pack.depth=50`, `pack.compression=6`
- Repetitions: 5; total scenario executions: 25; one packfile per scenario repository

| Scenario | Median pack + index bytes | Pack bytes, min–max | Median delta representation bytes | Delta counts across runs | Median commit seconds | Median aggressive-GC seconds |
|---|---:|---:|---:|---:|---:|---:|
| Mutable append | 5,693,362 | 5,692,063–5,692,118 | 241 | 2, 1, 2, 2, 2 | 0.232285 | 0.478324 |
| Mutable delete, compact | 5,638,292 | 5,636,995–5,637,047 | 1,557 | 2, 1, 2, 2, 2 | 0.233173 | 0.467681 |
| Mutable delete, tombstones | 5,637,671 | 5,636,375–5,636,428 | 85 | 1, 1, 1, 1, 0 | 0.088241 | 0.295121 |
| Immutable segments, append | 5,693,602 | 5,692,192–5,692,195 | 85 | 1, 1, 1, 1, 1 | 0.039363 | 0.302137 |
| Immutable segments, tombstones | 5,637,823 | 5,636,470–5,636,472 | 100 | 2, 2, 2, 2, 2 | 0.035468 | 0.299487 |

The full aggregate, including the five-run ranges, delta-count observations, fixture parameters, and environment, is committed in [the benchmark results JSON](../benchmarks/git_binary_spg/results-2026-11-23.json).

**Interpretation**

- The append alternatives differ by 240 bytes in median pack-plus-index size. This is approximately 0.004% of the mutable-append result.
- The mutable compact-delete result is 621 bytes larger than the mutable tombstone result and 469 bytes larger than the immutable-segment tombstone result. These are approximately 0.011% and 0.008% respectively.
- All observed differences are negligible relative to the approximately 5.6 MB packed repository. This experiment does not identify a meaningful storage winner.
- Delta counts vary between repetitions for some scenarios, demonstrating that pack selection is not a stable semantic metric. Delta representation bytes must not be interpreted as the number of changed SPG bytes.
- The fixture uses fixed-size, high-entropy pseudorandom payloads and one container/segment stream. It does not model realistic variable-size SPG payloads, multi-shard placement, long histories, branches, compaction cycles, clone/fetch traffic, or semantic graph validation.

The retained final execution passed `git fsck --full` for all five scenario repositories. The harness also passed a 100-record CLI smoke run, Python bytecode compilation, and a check that rejects reusing a work directory containing prior scenario repositories.

**Evidence status:** reproducible narrow microbenchmark; not architecture-selection evidence. Keep bounded stable shards and immutable segments open. The broader benchmark in §6 remains necessary before selecting a physical layout.

## 6. Required reproducible benchmark

### 6.1 Dataset

Generate deterministic SPG-like records with:
- varied record sizes and realistic nested payloads;
- typed references between records;
- stable IDs and content hashes as separate fields where the fixture requires them;
- configurable payload entropy (repetitive, mixed, and high-entropy);
- explicit object counts from small fixtures through millions;
- deterministic generation seed and manifest of all inputs.

The benchmark must distinguish record payload bytes from container framing, indexes, manifests, and Git metadata.

### 6.2 Change workloads

Run each layout through:
1. append 0.01%, 1%, and 10% of records;
2. delete 0.01%, 1%, and 10%;
3. mixed add/delete at the same ratios;
4. delete records uniformly at random and in contiguous placement ranges;
5. repeated add/delete cycles;
6. compaction after configurable segment counts or tombstone ratios;
7. two branches independently adding disjoint records;
8. two branches adding the same identity with equal and unequal payloads;
9. delete/update and delete/reference cases, which must be surfaced to semantic merge rather than decided by byte storage.

### 6.3 Layout and serializer variables

Compare:
- mutable bounded shards;
- immutable segments plus manifest/index;
- chunked containers;
- fixed versus content-defined chunk boundaries;
- uncompressed, whole-container compression, and independently compressed blocks;
- several shard/segment sizes, all below and around the configured large-object threshold;
- stable order versus deliberately perturbed order as a negative control.

Pin the Git version and all relevant configuration, including `core.bigFileThreshold`, `pack.window`, `pack.depth`, compression settings, and GC/repack invocation.

### 6.4 Metrics

Measure separately:
- working-tree bytes;
- loose-object bytes before packing;
- packfile and index bytes after ordinary GC and after controlled repack;
- new reachable object bytes per commit;
- delta count, delta depth, and delta sizes where inspectable;
- full clone and incremental fetch bytes;
- checkout/materialization time;
- full SPG reconstruction time;
- lookup of one object and range/parallel reads;
- import/export and compaction time;
- CPU and peak memory;
- history growth over hundreds/thousands of commits;
- cost of retaining old versions and cost after unreachable-object pruning in a disposable test repository.

Report medians and tail values across repeated runs. A single `git gc --aggressive` result is not sufficient.

### 6.5 Correctness gates

Every benchmark variant must prove:
- exact reconstruction of the expected current object set;
- exact preservation of immutable object payloads;
- deterministic output for identical pinned inputs;
- no silent resolution of same-identity conflicting additions;
- deletion does not leave unresolved references;
- compaction preserves semantic state and object identity;
- clone from Git alone reconstructs the full state without the KV cache;
- semantic merge is performed independently of Git's byte-level delta behavior.

## 7. Architecture implications

1. **Git is a plausible durable history layer for binary SPG containers.** It stores whole objects or deltas; binary data is not inherently excluded from delta compression.
2. **Container size must be bounded.** The default 512 MiB threshold disables delta compression above the configured limit; choose benchmark sizes with headroom.
3. **Stable byte layout matters.** Stable object ordering, stable record encoding, and localized updates improve the opportunity for deltas.
4. **Deletion is not equivalent to history erasure.** Old states remain available through prior commits.
5. **Git delta compression is not semantic merge.** A clean pack/delta or textual file merge says nothing about SPG graph validity.
6. **KV remains reconstructible cache/state acceleration.** The Git repository must contain everything required to rebuild the SPG; no required payload may exist only in KV or an unavailable external store.

## 8. Current recommendation and unresolved decisions

**Recommendation for the next experiment:** benchmark bounded stable shards first, with immutable segments as the principal alternative. Keep both candidates open until the multi-commit, branch, compaction, and clone-reconstruction workloads have been measured.

Do not yet:
- choose a canonical binary format (CBOR, custom encoding, or another format);
- select a shard key that assumes an unresolved identity model;
- assume tombstones are smaller or safer than rewriting a shard;
- assume immutable segments minimize Git history;
- increase `core.bigFileThreshold` as a substitute for a sound container layout;
- use Git's byte-level merge as an SPG merge mechanism.

### Open questions

1. What is the stable placement key compatible with the selected identity/lineage model?
2. What shard size optimizes Git packing, checkout, random access, and parallel processing together?
3. Is immutable-segment append worth the manifest, tombstone, and compaction complexity?
4. Which compression/chunking strategy gives the best total cost across Git history and runtime access?
5. How does Git behave over realistic long histories and independent branches, not just two commits?
6. Which parts of the container/index should be rewritten on deletion, and which can remain append-only?
7. How should benchmark results influence the eventual ADR-014 decision without prematurely fixing the SPG serialization?

## 9. References

- [Git pack objects](https://git-scm.com/docs/git-pack-objects)
- [Git pack format](https://git-scm.com/docs/pack-format.html)
- [Git configuration](https://git-scm.com/docs/git-config.html)
- [Git repack](https://git-scm.com/docs/git-repack)
- [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](../RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md)
- [Git Representation and Semantic Merge](../RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md)
- [ADR-014](../../docs/adr/014-git-semantic-merge.md) — proposed; not accepted
