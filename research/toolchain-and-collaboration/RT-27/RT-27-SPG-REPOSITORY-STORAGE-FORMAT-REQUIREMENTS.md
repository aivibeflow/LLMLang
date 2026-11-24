# RT-27 — SPG Repository Storage Format Requirements

**Status:** Research requirements; no storage format or physical layout selected  
**Date:** 2026-11-23  
**Priority:** P0  
**Related:** [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](../RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md), [Git Representation and Semantic Merge](../RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md), [ADR-017 — Default object format for agent interaction through MCP](../../../docs/adr/017-mcp-agent-object-format.md)

> This document records the requirements and evaluation criteria for the canonical repository/on-disk representation of SPG. It is not an accepted format decision. ADR-017's JSON decision applies only to MCP-facing object exchange and does not constrain this storage format.

## 1. Purpose and scope

Define requirements for storing a potentially very large SPG in Git while supporting efficient reconstruction, cache-aware loading, parallel processing, version history, and safe semantic integration.

The format is evaluated independently from the MCP-facing object representation, the in-memory SPG model, semantic identity and the final Content Hash algorithm, semantic diff and three-way merge rules, and the implementation of the KV/cache subsystem.

The repository representation is authoritative and must remain sufficient to reconstruct the committed SPG without relying on the continued existence of a local KV store.

## 2. Mandatory requirements

### R-STORE-001 — Complete reconstruction from Git

Git must contain all data required to reconstruct the complete committed SPG state, including object payloads and the metadata/index information required to locate and interpret them.

A KV store, cache, local database, or other acceleration layer may be used during normal operation, but it may be absent, empty, evicted, or lost. The Toolchain must be able to rebuild it from the Git repository alone, subject only to explicitly declared external immutable dependencies.

A design that stores indispensable SPG payloads only in a non-Git KV store, external database, or untracked local directory does not satisfy this requirement.

### R-STORE-002 — No one-file-per-object layout

The working-tree representation must not create one independently tracked file for every SPG object.

The SPG may contain millions of independently addressable objects even in a relatively small repository. The storage format must aggregate many objects into a bounded number of container files/segments or another layout that avoids a file-count proportional to the number of SPG objects.

This does not prohibit Git's internal object database from containing many blobs; it prohibits a working-tree/repository layout that materializes every SPG object as its own tracked file.

### R-STORE-003 — Cache lookup before payload deserialization

The format must expose enough per-object metadata to identify an object and obtain its Content Hash without reading and deserializing its full payload.

The loading path must be able to:
1. locate the object's record and read its identifying metadata;
2. obtain the object's Content Hash;
3. check whether that exact hash is already available in the cache;
4. on a cache hit, skip reading and deserializing the object's payload;
5. on a cache miss, read, decode, and validate the payload, including checking that its actual canonical content agrees with the recorded hash.

The cache key must be the Content Hash (with any required algorithm/profile identity), not merely the logical/object ID.

The physical format may implement this through record headers, a side index, block indexes, or another mechanism. Metadata lookup must not require deserializing the payload it is intended to avoid.

The trust and integrity relationship between record metadata, payload bytes, Git object integrity, and cached values must be specified. A cache hit must not permit incorrect or forged metadata to cause a different payload to be treated as the cached object.

### R-STORE-004 — Deterministic physical serialization

Within the same storage-format version and explicitly identified serialization profile, serializing the same logical SPG state must produce byte-for-byte identical repository output.

This is a requirement on the complete physical representation, not merely on individual object encodings. It applies to record ordering and framing, field/element ordering wherever the format permits multiple encodings, record placement, indexes and offset tables, manifests, padding and alignment, compression blocks and their metadata, and any other bytes written to the repository. Parallel serialization must produce identical output regardless of thread count, task scheduling, or completion order.

Determinism must not depend on process or machine, hash-map iteration order, incidental traversal order, cache hit/miss state, timestamps, nondeterministic compressor metadata, or other environmental state. The serialization profile must specify or constrain any implementation or compressor behavior that can affect output bytes.

This requirement is independent of semantic canonicalization and Content Hash calculation. Content Hash may be computed from a canonical semantic representation; it is not required to be the hash of the serialized bytes, and the physical serialization does not need to be the mechanism used to calculate Content Hash.

The byte-identity guarantee applies within one format version and serialization profile. It does not require byte-identical output across different format versions or profiles; version changes and migrations must be evaluated separately.

The purpose includes reproducible builds and avoiding spurious Git changes: unchanged logical state must not cause container files or blobs to change merely because serialization order, placement, parallel execution, or compression output varied. This is important for useful Git diffs, delta compression, and limiting repository-history growth.

### R-STORE-005 — No ordinary text merge of SPG containers

Ordinary line-oriented Git text merge must not be treated as a safe way to merge SPG container contents.

A text merge can produce syntactically valid JSON/JSONL/JSON-sequence data while violating SPG identity, reference, graph, or cross-object invariants. Textual conflict resolution without semantic understanding is therefore unsafe.

SPG changes must be integrated through semantic merge over complete, imported states with explicit conflict handling and whole-graph validation. If the semantic merge engine cannot establish a unique valid result, it must report a conflict or fail closed; it must not silently choose a side.

Git's physical merge result, including a clean file-level merge, is not proof of semantic correctness.

## 3. Desired capabilities

### R-STORE-006 — Parallel processing within a single file (SHOULD)

The format should support independent processing of different records or blocks in the same container file by multiple threads.

Prefer:
- unambiguous record and block boundaries;
- independently addressable byte ranges;
- locating a record without sequentially decoding all preceding records;
- independent decoding/deserialization of separate records or blocks;
- independent cache checks for records;
- deterministic assembly of results regardless of worker count or completion order.

The format should not require one file per object to achieve parallelism.

### R-STORE-007 — Independent or seekable compression blocks (SHOULD)

Compression should be evaluated together with random access and parallel processing.

Prefer a design in which a block can be decompressed independently, or in which a seek table/index enables efficient access to compressed regions. Evaluate the trade-off between compression ratio, CPU cost, random access, parallel decompression, and Git delta-compression effectiveness across file versions.

A single continuous compression stream may improve compression ratio but can prevent efficient independent access to records. Independent compression blocks may improve access and parallelism but may reduce cross-record compression opportunities.

No compression algorithm or block size is selected by this requirement.

### R-STORE-008 — Efficient Git history for changing containers (SHOULD)

The format should preserve Git's ability to store successive versions efficiently, including when objects are added or removed.

The expected workload includes adding and removing SPG object records; modification of an existing immutable object's payload is not the normal update operation. The design must nevertheless define how changed object versions, references, and removals are represented.

The research must measure Git packfile/delta-compression behavior on representative generated repositories rather than assuming that binary files are stored as complete independent copies or assuming that every binary layout delta-compresses well.

Evaluate at least:
- small changes to a few records;
- append-only additions;
- record deletions/tombstones;
- insertion of records into the middle of a container;
- reordering or relocation of records;
- compaction/repacking;
- changes affecting 0.01%, 1%, and 10% of objects.

Use stable ordering, placement, and deterministic serialization where possible. Measure repository growth and checkout/reconstruction cost.

## 4. Semantic and operational constraints

### R-STORE-009 — Physical layout must not define semantic identity

Object identity, Content Hash, lineage, occurrence/selection identity, and snapshot identity are separate semantic concerns. The physical location of a record, its segment number, byte offset, or Git blob ID must not silently become its SPG semantic identity.

The final identity model and hash envelope remain unresolved and are owned by the relevant identity/SPG research.

### R-STORE-010 — Explicit object update and deletion semantics

The format must represent additions, removals, and any supported object-version transitions unambiguously.

If immutable segments, append-only records, or tombstones are used, the format must define how the active state is reconstructed, how duplicate or superseded records are recognized, how conflicting concurrent changes to the same semantic object are detected, how deletion interacts with references and graph invariants, and how compaction preserves the exact reconstructed semantic state.

A generic last-record-wins rule must not resolve concurrent semantic updates unless a separate, explicit semantic rule proves that outcome valid.

### R-STORE-011 — Bounded operational complexity

The format must avoid unbounded growth in the number of active container files, indexes, manifests, or tombstones. If it uses immutable segments, it must define deterministic compaction/repacking and quantify its effects on repository size and history.

Compaction must preserve semantic content and identities. It must not require rewriting one file per object or make ordinary Git history prohibitively expensive.

### R-STORE-012 — Recoverable and verifiable indexes

Indexes, manifests, offset tables, and directory structures are permitted and may be used to provide efficient lookup, random access, cache-first metadata access, and parallel processing. An index is not required to be embedded in the same container as the records.

Any index or other lookup structure required for efficient operation must either be stored in Git or be deterministically rebuildable from Git-resident data. Rebuilding it from the repository must produce the same logical index and, within the same format version and serialization profile, the same serialized bytes.

The repository must remain reconstructible if all local indexes and KV state are deleted. Index corruption or mismatch must be detected; the implementation must have a defined rebuild or explicit failure path.

## 5. Candidate formats and layouts to evaluate

The research must compare complete storage designs, not only serialization syntax. Candidate families include:

1. **Bounded JSON containers:** sharded JSON arrays or object maps.
2. **JSON Text Sequences:** records separated by RFC 7464 record separators, with a separately defined canonical SPG profile and optional index.
3. **JSONL/NDJSON:** one JSON record per line, with explicit constraints for large or multiline values.
4. **Bounded binary containers:** for example, deterministic CBOR records with record headers, indexes, and stable placement.
5. **Immutable segments:** append-only or immutable JSON-sequence/binary segments plus a Git-resident manifest/index and explicit tombstones.
6. **Chunked containers:** fixed-size or content-defined chunks within a bounded number of repository files, including independently compressed blocks.
7. **Protocol Buffers (Protobuf):** schema-based binary records. Evaluate wire-format compactness, schema evolution and unknown-field handling, deterministic serialization constraints, and whether record metadata can be accessed without decoding the message payload. A Protobuf message alone does not provide a container/index strategy; evaluate it inside bounded, indexed containers.
8. **FlatBuffers:** schema-based binary buffers designed for direct field access without fully deserializing the entire object. Evaluate verifier and schema-evolution costs, buffer layout/alignment, access to object ID and Content Hash before payload traversal, record framing, and whether multiple records can be independently indexed and processed in parallel. FlatBuffers likewise requires an explicit multi-record container and indexing strategy.
9. **Other structured stores:** alternatives such as SQLite or SSTable-like layouts may be considered, but must satisfy Git recoverability, semantic merge, cache-first metadata access, and operational constraints.

For every candidate, evaluate metadata lookup before payload decoding, cache-hit cost and bytes read, random access and parallelism, serialization/deserialization throughput and memory use, schema evolution and compatibility costs (for schema-based formats), compression ratio and CPU cost, Git packfile size across realistic commit histories, checkout/clone/import/full rebuild costs, index/manifest update contention, merge conflict behavior and recovery, compaction cost and long-term history growth, and implementation complexity in Rust, Go, and C++.

No candidate is selected by this requirements document.

## 6. Required experiments and acceptance evidence

The comparative study must include reproducible workloads with realistic object counts, object-size distributions, reference density, and update patterns. Include a million-object-scale workload or justify a smaller proxy with a scaling argument.

At minimum, report:
- total working-tree file count and total Git object count;
- repository size before and after git gc/pack;
- incremental history growth per change set;
- cache-hit path latency and bytes read per object;
- cache-miss decode throughput;
- single-thread versus multi-thread throughput and scaling;
- peak memory use;
- random-access latency for records in early, middle, and late file positions;
- clone/checkout and cold-cache rebuild time;
- compaction time, temporary disk space, and history impact;
- behavior under concurrent additions, removals, and conflicting updates.

Test at least cache hit rates of 0%, 50%, 90%, and 99%, and mutation rates of 0.01%, 1%, and 10%.

The experiments must verify that cache hits avoid payload deserialization, not merely that deserialization is faster. They must also verify identical semantic results across thread counts and task schedules.

For each candidate, serialize an unchanged logical SPG state repeatedly under the same format version and serialization profile, including with different thread counts and task schedules. Verify byte-for-byte identical complete repository output. Then measure, for representative small and large mutations, the number of changed working-tree files and Git blobs, changed byte ranges/locality, Git diff churn, incremental packfile growth, and delta-compression effectiveness. Include index/manifest changes and compression metadata in these measurements. Evaluate cross-version/profile migration separately; do not conflate migration rewrites with same-version determinism.

## 7. Current research position

The following are constraints or hypotheses, not format decisions:

- One tracked file per SPG object is excluded.
- Full SPG recoverability from Git is mandatory; KV is optional acceleration and may be empty or lost.
- Cache lookup must happen before payload deserialization and must permit skipping payload reads on a hit.
- Parallel processing within one container file is desirable, not mandatory at this stage.
- Ordinary text merge is not a safe SPG merge strategy.
- Git's binary delta compression may be effective for stable, similar container layouts, but effectiveness depends on the actual byte-level change pattern and must be measured.
- JSON Text Sequences, bounded deterministic binary containers (including CBOR, Protobuf, and FlatBuffers as encoding candidates), and immutable/chunked segments remain candidates; none is selected.

## 8. Related ownership

- This document owns the requirements and evaluation plan for the physical SPG repository/storage representation.
- RT-24 owns the candidate semantic import/export, typed diff, three-way merge, and conflict contract. Its semantic validation requirements apply regardless of the physical format.
- Git Representation and Semantic Merge owns the broader Git integration and repository-level semantic merge direction.
- ADR-017 owns only the default MCP-facing JSON object representation; it does not select the repository storage format.
- Identity Studies 05–08 and SPG research own unresolved semantic identity and Content Hash definitions.

## References

- [RFC 7464 — JSON Text Sequences](https://www.rfc-editor.org/rfc/rfc7464)
- [Git pack format](https://git-scm.com/docs/pack-format)
- [Git pack-objects](https://git-scm.com/docs/git-pack-objects)
- [Git attributes](https://git-scm.com/docs/gitattributes)
