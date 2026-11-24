# Research Scenario 91 — Versioned Content Addresses and Digest Migration

**Status:** Evidence-linked prior-art comparison; no LLMLang encoding, digest, or migration policy selected
**Research areas:** RT-05 semantic identity, RT-06 dependencies, RT-11 cache identity, RT-15 repository interoperability, RT-18 evolution
**Updated:** 2026-11-19

## 1. Question and scope

How should a persistent content address communicate its digest algorithm and artifact representation, and how can a store move to a new digest without confusing byte identity, semantic identity, or logical lineage?

[Scenario 90](RESEARCH-SCENARIO-90-RUNTIME-HASHING-DETERMINISM-AND-PERSISTENT-IDENTITY.md) separates runtime table hashes, iteration order, stable fingerprints, and secure digests. This scenario narrows the persistent-addressing question. [LL-004](../../../TODO.md#ll-004--choose-canonical-encoding-and-hash-algorithm-policy) owns encoding, domain separation, digest representation, and migration. [LL-005](../../../TODO.md#ll-005--define-hash-relevant-dependency-edges-and-cycles) owns semantic dependency edges and recursive components. [RT-24](../../toolchain-and-collaboration/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) explicitly leaves the canonical schema and hash envelope unresolved.

This comparison does not select a canonical SPG encoding, hash algorithm, identity model, SCC construction, signature system, or migration schedule. It distinguishes existing systems' representations and migration choices from LLMLang's unresolved semantic requirements.

## 2. Prior-art comparison

### Git: repository-wide object format plus a compatibility mapping

Git's hash-function transition changes object names and the hash references embedded in objects. A SHA-256 repository stores a bidirectional SHA-256/SHA-1 object-name mapping locally; lookups can accept either form, and `git fsck` can verify the mapping. The design goal is staged repository-by-repository migration and eventual ability to discard compatibility metadata. It also records limits: the formats are not mixed within one repository, and compatibility translation can be expensive at server boundaries.

This is a migration architecture for an interconnected object graph, not just a longer digest string. Compatibility metadata and protocol behavior have storage and operational costs. The Git document's stated design also makes clear that old signed payloads and ancillary references (such as notes) need separate consideration.

Source: [Git hash-function transition](https://git-scm.com/docs/hash-function-transition.html).

### OCI: explicit algorithm-tagged digest and typed, sized descriptor

An OCI descriptor carries a digest string with an algorithm component, plus a required `mediaType` and raw byte `size`. The digest is over the targeted bytes; consumers can verify the fetched content and expected size. OCI permits algorithms and encodings to be identified in the digest representation and allows canonicalization of underlying content where implementations define it.

The descriptor therefore communicates more than a bare digest, but the media type does not itself define a canonical semantic encoding. Re-serializing semantically equivalent structured data may change byte-level identity unless a canonical representation is agreed separately.

Source: [OCI Image Specification — Content Descriptors and Digests](https://github.com/opencontainers/image-spec/blob/main/descriptor.md).

### IPFS CIDv1: versioned, typed address with a self-describing multihash

CIDv1 encodes a CID version, a multicodec content-type code, and a multihash that records hash function and digest length. A text form adds a multibase prefix; that base is a transport/string encoding of the same binary identifier. CIDv0 remains a constrained legacy shape with implicit version, codec, and SHA-256 multihash.

This makes format version, content type, hash function, and string encoding distinct fields. CID describes the addressed bytes/content format, not LLMLang's semantic equivalence rules. It is a useful precedent for extensible self-description, not evidence that every semantic field should be part of one artifact ID.

Source: [IPFS CID specification](https://specs.ipfs.tech/cid/).

## 3. Identity layers LLMLang must keep distinct

| Layer | Question answered | Candidate inputs that still need definition |
|---|---|---|
| Canonical representation | Which byte sequence denotes this typed artifact? | Schema/version, type tag, field order, integer/string encodings, normalization, unknown-field policy |
| Semantic content identity | Which immutable semantic value is addressed? | Artifact kind, semantic version/domain tag, canonical payload, hash-relevant dependency closure |
| Digest suite | How are canonical bytes reduced to an address? | Algorithm identifier, digest length, encoding, deprecation/verification policy |
| Logical lineage/occurrence | Which evolving operation or selected graph occurrence is this? | Explicit lineage/selection relation; not inferred from digest equality |
| Trust/evidence | Who authorized or verified this object? | Signatures/attestations, issuer, assumptions and trust roots; a digest alone is not authentication |

Changing the hash algorithm changes digest bytes even when canonical payload and semantics are unchanged. Changing canonicalization or a semantic version/domain tag may change what is being addressed, even if the digest algorithm is fixed. Reusing a digest prefix as a substitute for those other version dimensions would conflate independent migrations.

## 4. Migration alternatives for a semantic artifact store

| Candidate | Mechanism | Benefits | Costs and failure modes | Questions to discriminate |
|---|---|---|---|---|
| **D-A Algorithm-tagged addresses, one active suite** | Each address contains an algorithm identifier; stores may import/verify older suites while writers emit the configured current suite. | Simple new-object policy; addresses are self-describing; old objects remain verifiable. | Same semantic payload has multiple addresses; references/roots need explicit conversion; old-suite readers may not understand new tags. | Can consumers preserve exact references while resolving aliases? Which suites are mandatory for long-term reads? |
| **D-B Dual-address records and verified mapping** | Keep old and new digests in a mapping tied to the same canonical bytes/object record; validate both against payload. | Supports gradual migration and mixed clients; history and references need not change at once. | Mapping becomes trusted state requiring completeness, tamper detection, garbage collection, and migration tooling; duplicate byte verification cost. | Can mapping be deterministically regenerated? How is partial migration represented and audited? |
| **D-C New store/schema epoch with bulk readdressing** | A new repository or store epoch uses a new digest suite and rewritten references; migration is an explicit snapshot operation. | Clear boundary and simpler invariants within each epoch. | Expensive rewrite, large churn, interrupted migration/recovery, external links and signatures may break. | Can snapshots coexist, and what is the atomic cutover/recovery protocol? |
| **D-D Stable semantic name plus replaceable digest locator** | Logical/lineage ID remains stable while versioned content digests are stored as immutable locators. | Separates continuity from bytes; can support digest refresh without changing a logical name. | Requires explicit lifecycle and authorization rules; risks mutable name-to-content indirection or conflation with stable entity IDs. | Which objects have lineage, who may update bindings, and how are historical selections pinned? |

These approaches can be combined. Git is an existence proof for local compatibility mappings in a graph store; OCI and CID provide self-describing address formats. None settles whether LLMLang's canonical semantic object IDs should change when only the digest suite changes.

## 5. Interaction with recursive semantic dependencies

For a DAG, re-addressing under a new digest suite can be defined bottom-up if every dependent reference is part of canonical bytes. For mutually recursive operations, directly embedding each other's final digest creates a circular construction problem. The existing [recursive identity experiment](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md) compares keyed and structural group encodings and observes that structural addressing can deduplicate symmetric members.

An algorithm migration must therefore state whether it rehashes:

1. each member payload with external references left as old-suite IDs;
2. a canonical group envelope and derives member selectors;
3. a stable semantic envelope whose digest suite is a separately replaceable locator; or
4. both old/new groups plus a verified mapping.

These are not equivalent. The migration fixture should record member addresses, group address, callers, exact reference bytes, symmetry behavior, and whether lineage/selection survives. LL-005's acyclic initial model may reduce this problem, but does not determine cross-version references or later SCC introduction.

## 6. Discriminating research and falsifiers

No LLMLang migration implementation or performance experiment has been run. A matched future study should:

1. Encode the same typed artifact with two candidate digest suites while holding canonical bytes fixed; verify that algorithm-tagged addresses differ but payload identity can be reconciled.
2. Change schema version, artifact kind/domain, canonical field ordering, and semantic content independently; test whether addresses separate or intentionally alias each case.
3. Simulate a graph migration with shared dependencies, recursive groups, signed references, partial client support, interruption, rollback, and garbage collection.
4. Tamper with compatibility mappings and verify that payloads independently reproduce both claimed digests; reject ambiguous or incomplete aliases.
5. Distinguish same bytes/different media type from same semantics/different serialization and from same lineage/different semantic version.
6. Measure reference rewrite volume, migration peak storage, read amplification, and verification cost on realistic package and operation graphs.

The dual-address candidate weakens if a mapping cannot be independently regenerated and audited. Bulk epoch migration weakens if external consumers require old addresses to remain stable. A stable semantic locator weakens if authority over rebinding cannot be made explicit and immutable history preserved. Algorithm tagging alone is insufficient if artifacts with distinct domains can collide at the interpretation layer.

## 7. Provisional synthesis for LL-004/LL-005

Evidence supports treating digest-suite identification, canonical representation version, artifact/domain type, and logical lineage as independently modeled dimensions. Git, OCI, and CID demonstrate different mechanisms for compatibility, self-description, typing, and versioning; they do not determine LLMLang's semantic envelope. No option is ranked or selected.

Before RFC drafting, LL-004 needs fixtures for canonical bytes, domain separation, digest tags, and read/write compatibility. LL-005 needs a graph fixture that applies those same address rules to DAG edges and recursive groups. Follow-up work should decide migration guarantees together with identity lifecycle and RT-24 repository merge; selecting a cryptographic algorithm alone would leave these contracts underspecified.

## 8. References

- [Git hash-function transition](https://git-scm.com/docs/hash-function-transition.html)
- [OCI Image Specification — descriptor and digest](https://github.com/opencontainers/image-spec/blob/main/descriptor.md)
- [IPFS CID specification](https://specs.ipfs.tech/cid/)
- [LL-004 — canonical encoding and hash algorithm policy](../../../TODO.md#ll-004--choose-canonical-encoding-and-hash-algorithm-policy)
- [LL-005 — hash-relevant dependency edges and cycles](../../../TODO.md#ll-005--define-hash-relevant-dependency-edges-and-cycles)
- [Scenario 90 — runtime hashing and persistent identity](RESEARCH-SCENARIO-90-RUNTIME-HASHING-DETERMINISM-AND-PERSISTENT-IDENTITY.md)
- [RT-05 recursive identity experiment](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)
- [RT-24 canonical representation and merge](../../toolchain-and-collaboration/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md)
