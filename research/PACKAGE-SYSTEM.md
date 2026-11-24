# LLMLang Package System: Static and Dynamic Packages

**Status:** Research proposal; design decisions remain open  
**Research area:** RT-12 — Libraries, packages, templates, and artifact reuse  
**Updated:** 2026-11-20\
**Scope:** Package identity and contents, compact indexes, index compression and sparse lookup, static archives, dynamic provider-built packages, dependency closure, multi-provider composition, Git repository discovery, and reproducibility.

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
  manifest.toml
  index.bin
  objects/
    <content-hash>...
  provenance.json
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

### 7.1 Git repository discovery by `ImplHash`

A publisher could generate `llmlang-exports.jsonl` from the public exports and implementation bindings of released packages. Each line maps a full `ImplHash` to a specific package release. The hash scheme identifies the canonicalization and digest algorithm. The file is derived discovery metadata outside the Package Content Root Hash. [Draft `ImplHash` definition](../draft/GLOSSARY.md#implementation-hash-implhash)

An illustrative JSONL row follows.

```jsonl
{"impl_hash":"<full ImplHash>","hash_scheme":"<scheme and version>","commit":"<full release commit ID>","package_path":"packages/example.llpkg","package_content_root":"<Package Content Root Hash>"}
```

The release job can update the file on the default branch once the package commit exists and retain rows for supported releases. GitHub REST Code Search can find candidate repositories with `filename:llmlang-exports.jsonl "<full digest>"`. A client reads the matching file and checks the full `impl_hash` field for equality. Search coverage depends on GitHub's default-branch index. A catalogue can also collect these rows with their repository URLs and retain all registered locations for each hash. [GitHub Code Search syntax and limits](https://docs.github.com/en/search-github/searching-on-github/searching-code)

The resolver retrieves the package at the recorded commit and path, verifies its Package Content Root Hash, and recomputes the requested `ImplHash` from the implementation and its hash-relevant dependencies using the declared scheme. On a match, it pins the verified source and exact `ImplHash` in the consumer's lockfile. If a candidate is unavailable or fails verification, the resolver can try another location for the same hash.

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


## 13. Optional derived-result cache indexes

A package may optionally carry indexes of previously computed results for validation, compilation, analysis, tests, and proofs. Their purpose is to let consumers discover reusable work without repeating actions. A package remains complete and usable when all cache material is omitted.

Possible layout:

```text
package/
  manifest.toml
  index.bin
  cache/
    validation.index
    compilation.index
    analysis.index
    tests.index
    proofs.index
  cache-artifacts/
    <artifact-hash>...
```

The exact partitioning (one unified action-result index or separate indexes by action kind) remains open.

### 13.1 Action Key, not bare object hash

A Content Hash identifies an immutable input object, but does not uniquely identify a validation or compilation result. Results may depend on dependency closure, action implementation, language/toolchain version, target, configuration, runtime, and other inputs.

The cache index therefore maps a canonical **Action Key** to a result record:

```text
ActionKey = H(
  action_kind,
  exact_input_hashes_and_dependency_closure,
  language_version,
  language_component_registry_digest,
  toolchain_identity,
  relevant_configuration,
  target_and_environment_inputs
)

ActionKey -> ResultRecord -> ArtifactHash(es)
```

A record identifies action kind, exact input hashes and relevant dependency closure, composite language version and exact component-registry digest, toolchain identity, action implementation identity where independently relevant, target/configuration/runtime inputs, result status and scope, output Artifact Hash values, dependency-completeness and determinism classification, and provenance where applicable.

### 13.2 Language version binding

Every cache result must state the **composite LanguageVersion** used to produce it and identify the exact ordered component registry used to interpret that tuple (for example, by a digest of `language-components.toml`). The registry file contains only ordered component identifiers; it contains no component versions. Its ordering is append-only: existing identifiers cannot be removed, renamed, or reordered, and new identifiers are appended only at the end. When a component is appended, old tuples may omit the new trailing coordinates, which are interpreted as zero.

The cache record must separately identify the **ToolchainIdentity** used to produce the result. LanguageVersion and ToolchainIdentity are not interchangeable: a toolchain patch can affect results without changing normative language semantics, and a language component can evolve without identifying the tool build that processed it. Both values, plus the registry digest, enter the Action Key whenever they can affect the result. A result from another relevant version or registry snapshot is a cache miss unless an explicit, validated compatibility rule establishes safe reuse. Numeric similarity or a friendly release label alone is not compatibility evidence.

### 13.3 Reuse and trust rules

A cache hit is eligible only when the Action Key matches exactly; all result-determining dependencies are captured; referenced artifacts pass Artifact Hash verification; result scope and target cover the requested action; and determinism and trust policies permit reuse.

A validation result can replace validation only for the exact semantic inputs, dependency closure, language/toolchain version, and validation profile it covers. Compilation additionally depends on target, backend, ABI, optimization/configuration, and relevant runtime/toolchain inputs. A bare flag such as “hash X was compiled” is insufficient.

Deterministic failures may be cached if fully keyed. Timeouts, resource exhaustion, transient infrastructure failures, and unavailable services must not be treated as reusable semantic outcomes. A cache record is a claim that an action ran, not proof that it was correct; verification evidence and producer trust remain separate.

### 13.4 Index and payload separation

Cache indexes are separate from semantic Object, Symbol, Export, and Dependency indexes. They reuse compact-index principles: canonical sorted keys (normally Action Key), binary search, deterministic streaming merge, independently compressed blocks for large indexes, and optional sparse lookup where justified.

A cache index may reference result payloads by Artifact Hash without embedding them. A package may include selected payloads in `cache-artifacts/`, or they may be fetched from local, team, or remote caches. Missing or evicted payloads are ordinary cache misses, not package corruption.

Identical Action Keys with identical result records may be deduplicated. Conflicting records for one Action Key are integrity/reproducibility diagnostics, not last-writer-wins. Equal output Artifact Hash values do not merge distinct Action Keys.

### 13.5 Optionality and package identity

Cache indexes and payloads are optional, evictable derived artifacts. Adding, removing, recompressing, or rebuilding them must not change semantic object hashes or logical package identity. A physical archive hash may change when cache material changes and must remain distinct from the logical package content root.

This extends the action-cache model in `research/SEMANTIC-COMPILATION-CACHE.md`; it does not create a second cache-key scheme.

## 14. Manifest and representation boundaries

The package manifest should be human-readable text, not a binary index. The current format recommendation is **TOML** (`manifest.toml`).

The manifest is expected to contain a relatively small amount of package-level metadata: package format/schema version, requested roots, dependency policy, and references to the package's index and optional cache indexes. The included-object set and per-object relationships belong in the machine index. Source-store snapshot identity belongs in provenance/delivery metadata, not in logical package identity. These fields do not justify a custom binary encoding. A text manifest also improves code review, diagnostics, Git diffs, and inspection with ordinary tools.

Use separate representations for separate purposes:

| Component | Proposed representation | Responsibility |
|---|---|---|
| `manifest.toml` | Human-readable TOML | Package metadata and logical package description |
| `index.bin` | Compact binary | Canonically ordered object, symbol, export, module, and dependency indexes |
| `cache/*.index` | Compact binary | Optional derived-result cache lookup indexes |
| `objects/<content-hash>` | Object-defined binary or canonical payload | Immutable object bodies; encoding follows the object format |
| `provenance.json` | Human-readable JSON (provisional) | Provider/source provenance and delivery attestations; signatures may use detached binary envelopes where appropriate |
| `INDEX.md` | Generated Markdown (optional) | Human browsing catalogue derived from the machine index; never authoritative |

Binary encoding is justified for indexes because they benefit from compact fixed-width identifiers, delta/prefix encoding, block compression, binary search, and streaming merge. It is not justified merely because the package is an archive or because its manifest is machine-readable.

The manifest must not duplicate the full index. It should identify the index format/schema and its location, while the index carries per-object lookup records. Optional cache indexes remain separate from the package's core object index and may be omitted without making the package incomplete.

### 14.1 Manifest parsing and logical identity

The parsed manifest should map to a typed logical manifest model. The logical package content root must be computed from a specified canonical projection/encoding of that model and the included semantic object identities—not from raw TOML bytes, whitespace, key order, comments, or line endings. This prevents harmless formatting changes from changing logical package identity.

A first reviewable candidate for the TOML schema, canonical projection, hash boundaries, and validation invariants is recorded in [Package Manifest and Content Identity](PACKAGE-MANIFEST-AND-IDENTITY.md), with an illustrative [manifest.toml fixture](examples/package/manifest.toml). Those proposals remain non-normative: the exact canonical encoding, digest algorithm, table schemas, and schema-evolution policy require review and executable validation. Delivery-only fields (for example, provider timestamps, source snapshot identifiers, transport locations, signatures, and archive compression choices) remain outside the logical content root.

A parser must reject unsupported required schema versions and malformed or ambiguous values. Unknown optional metadata may be preserved or ignored only under an explicit forward-compatibility rule; it must not silently alter the logical content projection.

### 14.2 Representation principle

Prefer the simplest representation that fits each component's access and integrity requirements:
- human-authored or routinely inspected metadata: a documented text format;
- large, sorted lookup structures: compact binary indexes;
- immutable semantic objects: their own canonical object encodings;
- provenance and attestations: a separately versioned representation with explicit trust semantics.

This is a format-boundary recommendation, not a final wire-format decision. TOML is the current candidate for the manifest; the exact schema and canonical logical projection remain open.


## 12. Logical index schema and merge prototype

A first executable logical-table proposal now exists in [Package Index Logical Schema](PACKAGE-INDEX-LOGICAL-SCHEMA.md), with tests in [Package Index Logical Model Prototype 01](PROTOTYPES/PACKAGE-INDEX-01/README.md).

The current candidate tables and primary keys are:

| Table | Primary key | Main purpose |
|---|---|---|
| Objects | `ContentHash` | Included immutable object membership and canonical kind/size metadata |
| Dependencies | `(source_hash, edge_id)` | Exact typed dependency edges, including explicit included/external state |
| Exports | `(module_id, name)` | Public export names mapped to exact object hashes |
| Modules | `module_id` | Module membership as a set of included object hashes |

Cross-table validation requires dependency sources, included dependency targets, module members, and export targets to exist in the appropriate tables. An external dependency edge does not imply that its target is included in the package.

The merge contract is deterministic: identical records with the same key are deduplicated; conflicting records with the same key are integrity errors. No last-writer-wins rule is permitted. For conflict-free inputs, the logical merge is intended to be commutative, associative, and idempotent. Provider availability locations belong in a separate non-identity overlay.

The executable prototype currently validates these rules in memory and exercises canonical ordering, logical digest stability, merge laws, and conflict handling. It does **not** implement a streaming k-way merge or binary `index.bin` encoding. Its canonical JSON digest is experimental and is not the final LLMLang encoding/hash contract.

This is a proposed logical schema, not a frozen format. Dependency taxonomy, Stable ID grammar, optional condition representation, empty-module policy, and the complete set of identity-bearing tables remain open.


## 13. Streaming index merge prototype

The logical index prototype now provides a lazy k-way merge for one already-sorted table at a time. It keeps one current record per input stream, deduplicates identical records across streams, and rejects conflicting or out-of-order records. The merge itself uses O(k) state for k input streams. Bounded-memory cross-table reference validation is implemented as a separate external-memory pass. A ZIP-based streaming archive writer/verifier is also available as an exploratory prototype; neither binary index encoding nor a normative archive format has been selected. See [Package Index Logical Schema](PACKAGE-INDEX-LOGICAL-SCHEMA.md) and [Package Index Prototype 01](PROTOTYPES/PACKAGE-INDEX-01/README.md).


## 14. External-memory cross-table validation prototype

The Package Index Prototype 01 now provides `validate_streamed_index`. It validates sorted Objects, Dependencies, Exports, and Modules streams, spools the rows to temporary JSONL files, and checks cross-table references with sorted merge joins. References whose ordering differs from their source table are externally sorted in bounded chunks: included dependency targets, module members, and export object hashes. Dependency sources and export-to-module references use their existing table order.

The validator checks that dependency sources are included objects; included dependency targets, module members, and export objects exist; and export module IDs exist. External dependency targets (`included=false`) are intentionally not required to be package members. It rejects unsorted or duplicate table keys. In-memory sorting is bounded by `max_records_in_memory`; temporary disk use is proportional to the input index and generated sort runs.

This is an exploratory local-filesystem implementation, not a finalized binary index or provider protocol. It assumes sorted input streams and uses JSONL temporary files. Disk-space policy, interruption recovery, and portable temporary-storage abstraction remain open. See [Package Index Logical Schema](PACKAGE-INDEX-LOGICAL-SCHEMA.md) and [Prototype 01](PROTOTYPES/PACKAGE-INDEX-01/README.md).


## 15. Dependency policy and exact closure prototype

Prototype 01 now includes a reference resolver for the three manifest policies. closure follows required edges transitively; roots_only includes only requested roots; closure_with_optional follows required and optional edges transitively. target and evidence edges are retained in the index but do not cause distribution traversal. The resolver derives every dependency row's included flag from the resulting object membership.

Conditional required/optional edges require an explicit boolean decision supplied by the caller, keyed by source hash and edge ID. The prototype does not interpret the condition expression itself; missing decisions fail closed when the edge is eligible for traversal. This keeps environment/feature selection out of implicit provider behavior until a typed condition language is defined.

The resolver reads exact objects and outgoing edges from one immutable snapshot identified by snapshot_id. It rejects missing exact hashes, hash substitution, missing edge metadata, malformed/duplicate edges, and detected snapshot-token changes. Cycles terminate and shared dependencies are deduplicated. The initial `package_closure.py` reference resolver retains its visited set and output index in memory. The integrated `package_provider.py` moves the traversal queue, visited object metadata, and dependency rows to a disk-backed SQLite database, emits sorted index iterators, and streams one object payload at a time into `package_archive.py`. It has a configurable SQLite page cache and bounded fetch batches, but is not a strict constant-memory guarantee: ZIP central-directory metadata, configured external-sort chunks, individual edge/module rows, and caller-supplied condition selections still consume memory. The provider stages the archive and checks the snapshot token again before publishing the destination. This remains an experimental adapter, not a normative protocol. See Package Index Logical Schema and Package Index Prototype 01.

## 16. Streaming package archive prototype

Prototype 01 now includes `package_archive.py`, a streaming writer and verifier using ZIP as a temporary research container. It parses the v1 TOML manifest, interprets `index.path` as the directory prefix for this prototype's per-table JSONL files, and verifies that all declared index tables are present. It recomputes the logical index hash using the identity prototype's canonical typed encoding; rows are externally sorted by canonical record bytes so the process does not materialize complete tables. It verifies that every manifest root is an included object and recomputes/compares the declared Package Content Root Hash. Object streams are copied in bounded 1 MiB chunks while recomputing SHA-256 and checking the declared size against the Objects table. Cross-table references are validated before publishing; the writer uses a temporary file and atomically replaces the destination only after success.

ZIP entry timestamps and permissions are fixed, compression is disabled, and entry ordering is deterministic. Tests verify byte-for-byte repeatability, object and size mismatch rejection, missing/out-of-order payload rejection, archive corruption detection, and failure atomicity. The verifier rechecks manifest syntax and schema version, index-table presence and logical hash, root membership, Package Content Root Hash, cross-table references, object membership, hashes, sizes, and unexpected/duplicate entries.

ZIP, JSONL, entry naming, and manifest placement are strictly prototype decisions, not a normative LLMLang archive or binary index format. Python's ZIP implementation retains central-directory metadata in memory, so the prototype streams object bytes but does not promise constant total memory for arbitrarily many archive entries. The manifest index path is interpreted as a directory prefix in this prototype, while the illustrative future manifest still uses `index.bin`; this is an explicit prototype-layout mismatch, not a normative format decision. The prototype does not yet validate cache-index payloads, provenance/signatures, or provider dependency closure. See [Package Index Prototype 01](PROTOTYPES/PACKAGE-INDEX-01/README.md).


## 17. Provider resource measurements and snapshot-adapter boundary

The disk-backed Provider now has a reproducible benchmark harness in `PROTOTYPES/PACKAGE-INDEX-01/benchmark_package_provider.py`. It generates four reachable graph shapes—chain, repeated diamond, high fan-out, and bounded high-degree DAG—and runs each measurement in a fresh subprocess. Each result reports object/edge counts, elapsed time, object throughput, peak traced Python allocations, process peak RSS, temporary-directory disk high-water size, archive size, and archive verification. The harness is exploratory: process RSS includes interpreter/runtime overhead, traced allocations do not include all native allocations, and CI hardware is not a controlled benchmark environment. Results must not be interpreted as a strict constant-memory proof or a performance guarantee.

### 17.1 Initial CI benchmark results

Two single-run CI measurements were taken on GitHub-hosted Ubuntu with Python 3.11.18: baseline run [44285720991](https://github.com/aivibeflow/LLMLang/actions/runs/44285720991), followed by run [44286164584](https://github.com/aivibeflow/LLMLang/actions/runs/44286164584) after adding the SQLite pending-queue index `(processed, hash)`.

| Graph shape | Objects | Edges | Before index | After index | Speedup |
|---|---:|---:|---:|---:|---:|
| Chain | 5,000 | 4,999 | 6.404 s | 3.072 s | 2.08× |
| Diamond | 5,000 | 6,249 | 6.917 s | 3.280 s | 2.11× |
| Fan-out | 5,000 | 4,999 | 8.041 s | 2.972 s | 2.71× |
| Many dependencies | 5,000 | 79,864 | 51.072 s | 30.032 s | 1.70× |

At 5,000 objects, temporary-directory high-water usage after the queue-index change was approximately 5.08 MB (chain), 5.75 MB (diamond), 5.06 MB (fan-out), and 46.52 MB (many-dependencies). Peak traced Python allocations during the build were approximately 2.17–2.21 MB for the 5,000-object cases. Process peak RSS was approximately 42–44 MB for chain/diamond/fan-out and 143.9 MB for many-dependencies. RSS includes the in-memory synthetic snapshot and subsequent archive verification; it is not an isolated Provider-only measurement. Traced allocations are measured around archive construction after the synthetic snapshot and manifest have already been created.

The queue index improved throughput across all four shapes. It adds roughly 0.5 MB of temporary SQLite/index overhead in these cases. The many-dependencies case remains substantially more expensive because it processes nearly 80,000 dependency rows and creates proportionally larger external-sort temporary data.

These are single-run CI observations, not controlled-hardware baselines: there are no repetitions, confidence intervals, or stable performance thresholds. They demonstrate the direction and current cost profile only. They do not prove constant memory or predict production Content Store performance.

CI also exercises 1,200-object chain and high-fan-out closures through the actual Provider and archive verifier, with deliberately small external-sort and SQLite cache settings. This is a scale regression test, not a maximum-capacity claim.

### 17.2 Toolchain Server Prototype 01 is not yet a Provider backend

The existing `TOOLCHAIN-SERVER-01` prototype has immutable entity payloads and content-addressed snapshot roots, but it is an in-memory workspace/lifecycle experiment. Its public API does not expose the complete snapshot object set, typed dependency edges, or streaming object payloads required by the package Provider. Those details are currently represented by private dictionaries and a generic Entity envelope; depending on them would couple Provider to an unstable implementation and invent dependency semantics not present in the prototype.

The prototype README also explicitly excludes a persistent database backend, crash recovery, cross-process locking, and a stable public storage contract. Therefore no direct adapter is implemented at this stage.

A backend-neutral read contract and standalone persistent SQLite prototype now exist in `PROTOTYPES/PACKAGE-INDEX-01/content_store.py`. `ContentStore.open_snapshot()` returns a live `ContentStoreSnapshot` lease exposing a stable `snapshot_id`, exact-hash `get_object`, ordered `get_dependencies`, and streaming `open_object`. The SQLite implementation uses append-only object/dependency rows and a WAL-pinned read transaction; a writer committing after the lease opens is invisible to that lease but visible to a newly opened lease. The package Provider consumes this adapter directly in integration tests. This validates the Provider-facing contract and a local persistence mechanism, but it does not yet integrate the Toolchain Server's semantic model: dependency rows are supplied by a semantic/indexing layer, and the current generic Entity prototype has no canonical dependency extractor. The SQLite database remains derived/reconstructible under ADR-014's proposed Git-authoritative direction.


### 17.3 Content Store snapshot read contract and SQLite prototype

The Provider-facing storage contract is now explicit and backend-neutral:

- `ContentStore.open_snapshot()` opens one read lease.
- A `ContentStoreSnapshot` exposes a stable `snapshot_id` for the lifetime of that lease.
- `get_object(exact_hash)` returns the exact requested hash, kind, and byte size; missing exact objects fail rather than resolving to a different revision.
- `get_dependencies(source_hash)` returns the complete, ordered outgoing typed edge set for that exact source object. An empty set is explicit; missing dependency metadata is an error.
- `open_object(exact_hash)` returns a binary stream for the exact immutable payload.
- All object payload and dependency-index writes are append-only and atomic for one object. Repeating identical content is idempotent; conflicting metadata or edge sets are rejected.

The SQLite prototype uses WAL mode and a read transaction pinned by its first metadata read. Its `snapshot_id` is a store UUID plus generation token; it is not a Semantic Snapshot root, Package Content Root Hash, or durable reopenable snapshot identifier. The live transaction is the actual consistency boundary. A writer may commit while a reader is active: the old reader continues to see its pinned generation, while a newly opened reader sees the later generation. The caller must close payload streams and then close the snapshot promptly; long-lived readers can delay WAL checkpoint progress and increase WAL disk use.

Dependency edges are not inferred from opaque bytes. A trusted semantic/indexing layer supplies the complete edge set when publishing an object. This preserves the boundary between storage and language semantics. The current generic Toolchain Entity prototype has no accepted SPG schema or dependency extractor, so the SQLite prototype is not yet a Toolchain Server adapter. It is a persistent contract prototype consumed directly by the package Provider integration tests.

The database is derived/reconstructible and does not become authoritative program state. The prototype has no garbage collector, backup/restore design, cross-process repository lease, crash-injection matrix, migration framework, or final hash/schema policy. SQLite WAL is a local implementation experiment, not a selected production database.

## Public-interface integration (2026-11-24; proposed)

Package publication should distinguish public name/catalog entries pointing to exact operation/interface-group revisions from provider bindings pointing to exact ImplHash. Interface-only packages may be considered for conditional design; executable resolution must close provider and evidence dependencies. Dynamic package delivery is not permission to resolve a mutable latest contract at runtime. Compare manifest pinning, authorized provider selection, reproducible multi-provider composition, and target-specific ABI mappings. Public export visibility does not confer execution authority.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## RT-36 follow-up: explicit assumptions (proposed)

Bind trust claims to exact provider artifacts and dependency snapshots; package signatures and content identity are distinct from conformance. Preserve open assumptions and conditional admission in evidence metadata without changing package identity semantics. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
