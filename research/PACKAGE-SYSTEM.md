# LLMLang Package System: Static and Dynamic Packages

**Status:** Research proposal; design decisions remain open  
**Research area:** RT-12 — Libraries, packages, templates, and artifact reuse  
**Updated:** 2026-11-18  
**Scope:** Package identity and contents, compact indexes, index compression and sparse lookup, static archives, dynamic provider-built packages, dependency closure, multi-provider composition, and reproducibility.

## 1. Problem and goals

LLMLang needs a distribution mechanism for reusable functions, interfaces, contracts, types, tests, implementations, and other semantically related SPG objects. A consumer must be able to inspect what a package contains without downloading or parsing every object. It must also be possible to retrieve only selected objects and their required dependencies.

The system should support both:

- **Static packages:** prepared artifacts that can be published, mirrored, cached, and downloaded as archives.
- **Dynamic packages:** archives constructed by a provider in response to a request for exact object Content Hashes, using the provider's local content store and dependency metadata.

The two modes should produce the same logical package/content model. Dynamic packaging is a materialization strategy, not a second incompatible package format.

Primary goals:

1. Discover package contents cheaply and deterministically.
2. Address immutable objects by exact Content Hash.
3. Resolve required transitive dependencies without silently substituting revisions.
4. Support compact indexes suitable for binary search, streaming merge, and partial retrieval.
5. Avoid loading or decompressing an entire large index for a small lookup.
6. Support offline transfer through archives.
7. Make package construction reproducible against a consistent content-store snapshot.
8. Keep content integrity separate from publisher trust, provenance, and licensing.

Non-goals for this research: selecting the final hash algorithm, final binary wire format, registry protocol, signature scheme, or package versioning policy.

## 2. Terminology and boundaries

| Term | Proposed meaning |
|---|---|
| Package | Logical distribution unit describing and grouping related immutable objects |
| Module | Logical organization boundary within a package |
| Artifact | A concrete serialized or archived representation of a package |
| Package Index | Compact machine-readable description of package contents and relationships |
| Human Index | Generated human-readable catalogue derived from the machine index |
| Content Store | Storage of immutable objects addressed by Content Hash |
| Library | Reusable semantic component role; not necessarily a distinct package mechanism |
| Registry | Service for publishing, discovering, resolving, and retrieving packages or objects |
| Provider | A service or local process that exposes a content store and can answer object/package requests |
| Lockfile | Consumer-side record of exact resolved identities and dependency selections |

Package is initially best treated as a distribution-level concept referencing SPG objects, not as a semantic node that changes program meaning. Whether it also needs a first-class SPG representation remains open (see LL-010).

A package can contain multiple modules, public exports, internal objects, several implementations of an interface, and the specifications/contracts needed to describe those implementations. Public exports must be distinguishable from package-internal objects.

## 3. Package identity and content model

Use content-addressed object identity as the basis for integrity and exact retrieval:

- Every immutable object has a Stable ID where lineage is meaningful and a Content Hash for the exact immutable revision.
- A Stable ID may identify multiple revisions; a Content Hash identifies one exact content value.
- Dependencies refer to exact Content Hash values, not mutable names or version labels.
- Human-facing versions such as `1.2.0` may remain useful release labels, but must not replace immutable identity in a resolved dependency graph.
- A package may have descriptive identity and release metadata, but its content identity must be derived from a canonical description of its roots and included objects.
- Compression, archive layout, transport metadata, and provider timestamps must not change object Content Hash values.

A package may contain roots and a closure of required dependencies. It may also carry optional dependencies, test evidence, proofs, provenance, and human-readable documentation. The index must identify what is present and how it relates, without duplicating complete object bodies.

The package content model should distinguish:
- requested roots;
- included objects;
- required dependency edges;
- optional or feature-selected dependency edges;
- public exports;
- module membership;
- verification/evidence objects;
- provenance and delivery metadata.

A dependency edge must have an explicit kind and resolution policy. A reference in the semantic graph is not automatically a request to distribute its target: descriptive, evidentiary, optional, target-specific, and mandatory dependency relations must not be conflated.

## 4. Compact binary indexes

### 4.1 Requirements

The machine index should be optimized for discovery and exchange rather than for human editing. It should:

- use canonical ordering by key;
- support binary search;
- support deterministic streaming merge of sorted indexes;
- avoid duplicating full object contents or verbose documentation;
- use fixed-width encodings for fixed-size identifiers where practical;
- use compact encodings for lengths, offsets, enums, and repeated values;
- permit independent access to logical tables;
- carry format and schema version information;
- support integrity checks for index blocks and tables;
- permit rebuilding derived lookup structures from canonical index data.

Candidate logical tables:

| Table | Key | Value |
|---|---|---|
| Object Index | Content Hash | Object kind, encoded size, storage/block reference, flags |
| Symbol Index | Stable ID | Available revisions and corresponding Content Hashes |
| Export Index | Symbol ID | Public export metadata and object reference |
| Dependency Index | (Object Hash, dependency key) | Dependency kind, target Content Hash, conditions |
| Module Index | Module ID | Object membership or ranges |
| Package Metadata | Package ID / canonical package key | Release labels and descriptive metadata |

The final table set and key schemas depend on the canonical SPG object model and dependency taxonomy. This proposal does not freeze them.

### 4.2 Canonical order and merge semantics

Each table is independently sorted by a specified canonical byte ordering. The ordering must be part of the format contract, not a locale-sensitive string comparison.

Merge should be a streaming operation over sorted inputs:

- Equal Content Hash values represent the same immutable object and are deduplicated after metadata consistency checks.
- The same Stable ID with different Content Hash values represents distinct revisions in one logical lineage; both may be retained.
- Distinct package releases remain distinct package records.
- Conflicting claims about the same Content Hash (for example, incompatible object kind or canonical size) are integrity errors, not last-writer-wins updates.
- The result must be deterministic regardless of input index order.
- Merge must not require object bodies to be downloaded or materialized.

For multi-provider composition, the merged index may also retain source/provider locations as non-semantic availability metadata. Provider location must not affect object identity.

### 4.3 Human-readable index

A file such as `INDEX.md` may be generated from the machine index. It is a browsing aid, not the authoritative source and not a second manually maintained catalogue. The machine index remains canonical.

## 5. Compression and sparse lookup

### 5.1 Why whole-file compression is insufficient

Compressing the entire index as one stream can reduce storage and transfer size, but it makes random lookup expensive: locating one record may require decompressing a large prefix or the entire index. This conflicts with selective retrieval and remote-provider workflows.

The preferred candidate for large indexes is **independently compressed blocks**:

- Each table is divided into sorted blocks.
- Each block can be decompressed independently.
- Block boundaries preserve global key ordering.
- A block directory records key ranges or boundary keys, offsets, compressed and uncompressed sizes, codec, and integrity information.
- The reader loads the small directory first, locates a candidate block, decompresses only that block, and performs an in-block binary search.

Block sizes should be benchmarked against real workloads. A range such as hundreds to a few thousand records per block is an experiment starting point, not a normative constant.

### 5.2 Sparse index

A sparse index stores a sample key (normally the first key in a block) and the block's location. Lookup becomes:

1. Binary-search the sparse directory for the greatest boundary key not greater than the target.
2. Read and decompress the corresponding data block.
3. Binary-search the records within that block.
4. Verify the exact key and return the record or a not-found result.

A sparse directory may itself be kept uncompressed or lightly compressed for fast startup. For very large indexes, a multi-level sparse directory or a B-tree-like directory may reduce memory and remote I/O.

The sparse index is a derived acceleration structure. It must be rebuildable from the canonical sorted table and block metadata. Its absence or corruption must not make the package's contents unrecoverable.

### 5.3 Do we always need it?

No. A sparse index should not be mandatory for every package.

| Workload | Suggested representation |
|---|---|
| Small package index | Read the entire index; ordinary in-memory binary search |
| Medium index | Independently compressed blocks and a compact block directory |
| Large or remote index | Block compression plus sparse lookup; optionally hierarchical |
| Sequential merge or full scan | Stream sorted blocks; sparse lookup is unnecessary |

Thresholds must be selected from measured index sizes, memory budgets, latency, and lookup patterns. The format should allow the representation to omit a sparse index when its overhead exceeds its benefit.

### 5.4 Compression choices

Keep codec identity explicit and versioned. A conservative initial format could support:

- `none` for minimal CPU cost and small tables;
- Zstandard for a practical compression/throughput balance.

LZ4 may be evaluated as an additional fast codec. Do not mandate a codec before benchmarking.

Additional encodings may improve compression and search locality:

- prefix compression for sorted identifiers;
- delta encoding for offsets and monotonic numeric fields;
- dictionary encoding for repeated object kinds or strings.

These are independent of the outer block codec and should be evaluated with representative data.

### 5.5 Integrity and identity

The index should distinguish:
- logical table content;
- physical block representation;
- sparse lookup metadata;
- transport/archive metadata.

Object Content Hash values apply to canonical object content, not compressed bytes. If the index itself has a canonical logical digest, it should be defined independently of codec and block layout, or the format must explicitly distinguish logical-index identity from physical-index artifact hash.

## 6. Dynamic packages

### 6.1 Request model

A consumer can ask a provider to construct a package from exact root hashes:

```text
PackageRequest {
    roots: [ContentHash, ...]
    dependency_policy: closure | roots_only | closure_with_optional
    target?: TargetProfile
    features?: [FeatureID, ...]
    max_size?: Integer
    format?: PackageFormat
}
```

The minimum viable request needs only `roots` and a dependency policy. Target, feature, size, and output-format parameters should be added only with precise semantics.

### 6.2 Provider resolution algorithm

A provider:

1. Pins a consistent snapshot of its Content Store and dependency metadata.
2. Checks that every requested root hash exists and that the stored bytes match the requested hash.
3. Reads each root's dependency metadata.
4. Resolves required transitive dependencies recursively.
5. Applies the explicit dependency policy and any target/feature conditions.
6. Requires the exact dependency Content Hash recorded by the parent object.
7. Deduplicates shared dependencies.
8. Detects missing objects, invalid metadata, and unsupported dependency conditions.
9. Builds the package manifest and compact index.
10. Writes the selected object bodies and metadata into the archive.
11. Computes and returns the logical content root/hash and delivery metadata.

Example:

```text
A -> X, C
B -> X
C -> Y

Requested roots: A, B
Closure: A, B, C, X, Y
```

Shared dependency X is included once.

If A requires B@hash-1 and the provider has only B@hash-2, resolution fails. The provider must not silently substitute a newer or “compatible-looking” revision. Compatibility substitution, if ever supported, is a separate evidence-backed resolution operation and must be visible to the consumer.

### 6.3 Dependency policies

- `closure`: include roots and all required transitive dependencies. Recommended default.
- `roots_only`: include only requested roots; dependencies remain external and must be resolvable by the consumer.
- `closure_with_optional`: include required closure plus explicitly selected optional dependencies.

Optional, target-specific, and feature-dependent dependencies require explicit rules. The provider must not guess feature choices or silently omit an unresolved required dependency.

### 6.4 Snapshot consistency and determinism

A dynamic package must be built against one consistent snapshot. Otherwise the provider could read a root from one store state and a dependency from another, producing a mixed result.

For a fixed request and fixed content-store snapshot:
- logical included object set and dependency graph are deterministic;
- canonical manifest and logical index are deterministic;
- the logical content root/hash is deterministic;
- timestamps, provider identity, transport details, and signatures do not affect logical content identity.

The physical archive may differ because of compression, archive timestamps, or signing. Keep logical content identity separate from physical artifact hash and delivery metadata.

### 6.5 Suggested archive layout

```text
dynamic-package/
  manifest.bin
  index.bin
  objects/
    <content-hash>...
  provenance.bin
```

The manifest records format version, requested roots, included objects, dependency policy, exact dependency edges, hash algorithm identifiers, and snapshot identity. The index describes the archive's objects. Provenance records provider and source information and may carry signatures/attestations. Delivery-only values such as CreatedAt should not be included in the logical content root.

## 7. Provider and consumer interaction

A possible protocol can evolve around these operations:

| Operation | Purpose |
|---|---|
| Query | Check whether exact hashes exist and obtain compact metadata |
| GetIndex | Retrieve a complete or partitioned index |
| Resolve | Obtain dependency closure and resolution diagnostics without downloading bodies |
| BuildPackage | Materialize a dynamic package from roots and a policy |
| GetObject | Retrieve one exact object |
| GetPackage | Retrieve a prebuilt static package |

The consumer should be able to compare provider indexes with its local index, determine which exact objects are missing, and request only those objects or a dynamic closure. The provider may accept a set of hashes already held by the consumer, but the response must remain verifiable and must not omit dependencies the consumer does not actually possess.

Multiple providers may serve different subsets of the content graph. The consumer can merge their sorted indexes, retain provider availability metadata, and resolve object locations. Conflicting content claims for the same hash are integrity failures.

The protocol must distinguish metadata-only resolution from object transfer. This permits planning, auditing, and cache checks without downloading object bodies.

## 8. Trust, provenance, and licensing

Content addressing proves that retrieved bytes match a requested digest; it does not prove who published them, whether they are safe, or whether redistribution is licensed.

Publisher identity, signatures, attestations, revocation, licensing, and retention policies are separate concerns. Provenance should identify the provider and source snapshot, but must not change the semantic identity of included objects.

A provider is not trusted to assert successful verification on behalf of the consumer. Verification evidence must be bound to exact input hashes, assumptions, target profiles, and tool versions, and independently checked according to the relevant LLMLang evidence policy.

## 9. Design vectors

| Vector | Index representation | Dynamic delivery | Advantages | Costs and risks |
|---|---|---|---|---|
| A — Minimal | One compact sorted index, optionally whole-file compressed | Provider returns a simple archive | Simple implementation and format | Poor random access for large indexes; whole-file decompression |
| B — Blocked | Per-table sorted blocks, independently compressed, block directory; sparse directory when worthwhile | Provider builds closure archives | Good balance of random access, sequential merge, and compression | More format and recovery complexity |
| C — Hierarchical | Blocked tables plus multi-level sparse/B-tree-like lookup | Provider supports partitioned index and selective block/object retrieval | Scales to very large and remote indexes | More metadata, protocol complexity, and consistency concerns |

**Current recommendation for investigation:** Vector B is the most balanced candidate. Vector A remains appropriate for small packages. Vector C should be justified by measured large-index or remote-query workloads rather than adopted pre-emptively.

## 10. Risks and unresolved questions

1. Canonical encoding and hash algorithm agility remain foundational dependencies.
2. The exact dependency taxonomy must distinguish required, optional, target-specific, feature-selected, descriptive, and evidentiary edges.
3. The package content root must be defined without accidentally including delivery-only metadata.
4. Stable ID and package identity lifecycle are not settled.
5. Index table schemas depend on the final SPG object and symbol model.
6. Block sizing, compression codecs, and sparse-index sampling need benchmarks.
7. The format must define corruption detection, partial-download validation, and safe recovery.
8. Dynamic providers need snapshot isolation and resource limits.
9. Multi-provider conflict, availability, and trust policies remain open.
10. Registry protocol and package versioning should not be frozen by this report.

## 11. Proposed experiments and exit criteria

- Generate synthetic and representative indexes at several sizes and key distributions.
- Compare uncompressed, whole-file compressed, and independently compressed block layouts.
- Measure index bytes per object, compression ratio, cold-start time, random lookup latency, sequential scan throughput, and peak memory.
- Compare no sparse index, one-level sparse index, and hierarchical sparse index across local SSD and remote/range-read scenarios.
- Measure merge throughput and memory for two and many indexes, including duplicates and conflicting metadata.
- Prototype dynamic closure resolution with shared dependencies, missing dependencies, hash mismatch, cycles, optional dependencies, and target/feature conditions.
- Test that a provider cannot mix store snapshots during one build.
- Verify deterministic logical manifests and roots across repeated builds and different physical codecs.
- Test partial retrieval and reconstruction from a subset of blocks/objects.

Exit criteria:
- A canonical logical package-content model is defined.
- Exact-hash dependency closure and failure behavior are specified.
- Index lookup, merge, and integrity invariants are testable.
- Benchmarks justify block and sparse-index policies.
- Static and dynamic packages share one logical content model.
- Trust and provenance claims are explicitly separated from content integrity.

## 12. Current conclusion

A compact binary index is justified by the need for fast discovery, binary search, streaming merge, and selective retrieval. Independently compressed blocks are a strong candidate for large indexes because they preserve local random access. A sparse index is useful when the main index is too large or remote to load and scan, but it should be optional and derived rather than mandatory.

Dynamic packages are a natural extension of content-addressed storage: a provider materializes the exact dependency closure for requested roots from a consistent local snapshot. This capability should share the same package manifest and index model as static packages.

This report is exploratory. Its recommendations are not normative LLMLang requirements until reviewed and explicitly accepted.
