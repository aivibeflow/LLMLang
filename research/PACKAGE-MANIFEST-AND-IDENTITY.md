# Package Manifest and Content Identity — Initial Design

**Status:** Research proposal; not normative  
**Research area:** RT-12 — Libraries, packages, templates, and artifact reuse  
**Updated:** 2026-11-18  
**Related:** [Package System](PACKAGE-SYSTEM.md), [Semantic Compilation Cache](SEMANTIC-COMPILATION-CACHE.md), [Draft Glossary](../draft/GLOSSARY.md)

## 1. Purpose and scope

This document turns the package-format direction into a first reviewable proposal for:

1. a human-readable TOML package manifest;
2. the boundary between the manifest and binary indexes;
3. logical package-content identity independent of TOML formatting and physical archive representation;
4. validation rules and test cases for the proposal.

It deliberately does not freeze the final hash algorithm, binary index wire format, package release/version policy, or registry protocol. Read the [Draft Glossary](../draft/GLOSSARY.md) alongside this document when reasoning about semantic object hashes; `OpHash`, `ImplHash`, and `CCHash` identify typed semantic concepts, whereas Package Content Root Hash, logical index hash, and archive hash identify package-level projections/artifacts. They must not be substituted for one another. The glossary is proposed terminology, not a normative package-hash specification.

## 2. Representation boundary

Use each representation for the data and access pattern it serves:

| Component | Candidate representation | Authority |
|---|---|---|
| `manifest.toml` | Human-readable TOML | Authoritative package-level descriptor |
| `index.bin` | Compact binary | Authoritative machine lookup tables and package membership relations |
| `cache/*.index` | Compact binary | Optional, rebuildable/evictable derived-result lookup |
| `objects/<content-hash>` | Object-defined canonical payload | Immutable semantic object content |
| `provenance.json` | Human-readable JSON (provisional) | Provenance and delivery attestations |
| `INDEX.md` | Generated Markdown (optional) | Non-authoritative human browsing view |

The manifest must stay small. It identifies the package format/schema, selected roots and dependency policy, and the machine index. It must not duplicate per-object records, dependency tables, exports, or module membership already held in the index.

Binary encoding is justified for indexes because they need compact records, canonical sorting, binary search, streaming merge, and independently readable compressed blocks. It is not justified merely because the manifest is consumed by tools.

## 3. Candidate TOML schema, version 1

The following is an illustrative valid-shape example. Hash values are placeholders, not real object references.

```toml
format = "llmlang.package"
schema_version = 1

[package]
id = "pkg:example.math"
name = "example-math"
version = "0.1.0"
description = "Illustrative package manifest"

[content]
roots = [
  "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "sha256:2222222222222222222222222222222222222222222222222222222222222222",
]
dependency_policy = "closure"
content_root = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[index]
path = "index.bin"
format_version = 1
logical_hash = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

[cache]
indexes = [
  "cache/validation.index",
  "cache/compilation.index",
]
```

### 3.1 Top-level fields

| Field | Required | Meaning | Identity treatment |
|---|---:|---|---|
| `format` | Yes | Exact format discriminator | Domain/schema selection; not package content by itself |
| `schema_version` | Yes | Manifest schema version | Selects the typed parser and canonicalization rules |
| `package` | No | Human-facing package descriptor | Excluded from content root in v1 |
| `content` | Yes | Requested roots and dependency selection | Selected logical fields enter the content-root projection |
| `index` | Yes | Machine index location and format/integrity claims | Path and physical encoding excluded; logical index content committed |
| `cache` | No | Optional derived-result index references | Entirely excluded from package content identity |

### 3.2 Package descriptor

Candidate fields:
- `id`: stable package-lineage identifier, if the project adopts one;
- `name`: human-readable name;
- `version`: release label, not immutable identity;
- `description`: descriptive text.

These fields are useful for discovery and display, but changing a name, description, or release label must not change the identity of the same package contents. A future signing/publication policy may bind these fields in a separate publisher attestation.

### 3.3 Content fields

- `roots` is a non-empty list of exact, algorithm-tagged Content Hash values requested as package roots.
- `dependency_policy` is one of `closure`, `roots_only`, or `closure_with_optional`.
- Any feature selection or target profile that changes dependency resolution must be represented explicitly in the content-selection model before it can be used. Do not infer it from the host environment.
- `content_root` is a declared integrity value calculated from the canonical logical projection described below. It is a claim to verify, not an input to its own hash.

The actual included object set and package relationships belong in `index.bin`, not in a long manifest list. For `roots_only`, the index may describe dependency edges to objects that are intentionally not included; the membership table must make inclusion versus external reference unambiguous.

### 3.4 Index fields

- `path` is a relative archive path. It is a locator, not identity.
- `format_version` selects the binary index schema.
- `logical_hash` is a declared digest of the canonical logical index tables, independent of compression, block layout, sparse lookup structures, and physical file bytes.

The logical index digest must cover all identity-bearing index tables and their canonical records. The initial table candidates are object membership, dependency edges, public exports, and module membership. Evidence/proof associations should be included only when the package model explicitly defines them as part of the distributed logical content.

### 3.5 Optional cache fields

Cache index references are optional and evictable. Their presence, absence, paths, compression, and payload availability must not affect the package content root. A missing cache artifact is a cache miss, not package corruption.

## 4. Parsing and validation rules

The v1 candidate parser should:

1. Require UTF-8 TOML and exactly one value for every key.
2. Reject duplicate TOML keys, malformed tables, invalid field types, and invalid hash spellings.
3. Reject unsupported `format` or `schema_version` values.
4. Reject an empty root list and duplicate roots; root order is semantically irrelevant.
5. Accept only the declared dependency-policy values.
6. Require safe relative paths for archive entries; reject absolute paths, parent traversal, and path collisions.
7. Require the referenced index to exist and match its declared format version.
8. Recompute the logical index hash and compare it with `index.logical_hash`.
9. Recompute the package content root and compare it with `content.content_root`.
10. Fail closed if a required object or exact required dependency is absent or mismatched.

For v1, unknown keys in identity-bearing tables should be rejected rather than silently ignored. An extension mechanism can be added later with explicit namespace, version, and hash-inclusion rules. Unknown descriptive extensions must never be allowed to smuggle unrecognized identity-bearing fields into a package.

## 5. Logical package identity

### 5.1 Three different digests

Keep these values distinct:

- **Object Content Hash:** identifies the canonical content of one immutable semantic object.
- **Package Content Root Hash:** identifies the logical package selection and its identity-bearing index relationships.
- **Package Archive Hash:** identifies the exact physical archive bytes, including encoding, compression, paths, cache payloads, provenance, and signatures.

Also distinguish the **Index Logical Hash** from a physical hash of `index.bin`. Reblocking or recompressing an index may change its physical bytes without changing its logical tables.

### 5.2 Proposed hash construction

The proposed construction has two stages:

```text
IndexLogicalHash =
  H(domain = "llmlang.package-index.logical.v1",
    canonical(identity-bearing index tables))

PackageContentRootHash =
  H(domain = "llmlang.package-content-root.v1",
    canonical({
      roots,
      dependency_policy,
      explicit_resolution_inputs,
      IndexLogicalHash
    }))
```

Here `H` is a domain-separated, algorithm-tagged digest operation. The final digest algorithm and exact canonical typed encoding remain open. The canonical encoding is an internal hash preimage representation; it does not turn `manifest.toml` into a binary file or require storing a second binary manifest.

The logical index tables must commit to:
- the exact set of included object Content Hash values;
- typed dependency edges, including exact target hashes and conditions relevant to the selected package;
- public export mappings;
- module membership;
- any additional package relationship explicitly designated identity-bearing by the final package model.

For `roots_only`, unresolved external dependency references remain represented as external edges and are not falsely counted as included objects.

### 5.3 Canonicalization rules

The v1 candidate rules are:

- Treat roots as a set: reject duplicates, then sort by canonical algorithm-tagged digest bytes.
- Sort every identity-bearing index table by its specified canonical key bytes.
- Sort set-valued fields and dependency records by canonical typed keys; preserve order only where the schema explicitly defines order as meaningful.
- Encode values with explicit type tags, lengths, and domain separation; do not rely on locale, platform integer width, TOML text order, or host endianness.
- Normalize identifiers and strings only according to an explicitly specified field-level rule. Do not apply broad Unicode normalization implicitly.
- Exclude file paths and physical offsets from logical index records.
- Exclude the declared `content_root` and `index.logical_hash` values from their own preimages; recompute them from the underlying logical data.

### 5.4 Fields excluded from Package Content Root Hash

The following are excluded in the v1 candidate because they describe naming, delivery, optimization, or trust rather than the selected logical package contents:

- package name, description, release version, and stable package-lineage label;
- raw TOML bytes, comments, whitespace, key ordering, and line endings;
- index path, block size, compression codec, offsets, sparse directories, and physical index bytes;
- optional cache indexes and cache artifact payloads;
- archive timestamps, provider identity, source-store snapshot identifier, transport URLs, and delivery locations;
- provenance documents, signatures, and attestations;
- archive container format and physical archive bytes.

Exclusion from the content root does not mean these fields are unimportant or untrusted. Provenance and publisher attestations should be verified under a separate trust policy; the archive hash can commit to the complete delivered artifact.

## 6. Dynamic package determinism

For a fixed request and fixed content-store snapshot, the provider must produce the same logical index tables and Package Content Root Hash, regardless of:
- traversal order during dependency closure;
- order of roots in the request;
- local object storage layout;
- index block size or compression codec;
- archive timestamps or provider-specific delivery metadata.

The provider must not resolve a required dependency to a different hash. A missing exact dependency is a resolution failure, not permission to choose a newer version.

The source snapshot identifier is recorded in provenance for audit/reproduction, but is not itself part of logical package identity. If two snapshots contain exactly the same selected logical objects and relationships, they should yield the same Package Content Root Hash.

## 7. Required invariants

| ID | Invariant | Validation |
|---|---|---|
| PMI-001 | TOML formatting changes do not change Package Content Root Hash | Parse and hash semantically equivalent TOML fixtures with different whitespace, comments, and key order |
| PMI-002 | Reordering roots does not change Package Content Root Hash | Permute root list |
| PMI-003 | Reordering records in an unordered index table does not change its logical hash | Permute table records |
| PMI-004 | Adding or removing an included object changes Package Content Root Hash | Mutate membership set |
| PMI-005 | Changing an identity-bearing dependency edge or exact target hash changes Package Content Root Hash | Mutate dependency table |
| PMI-006 | Changing an export or module membership changes Package Content Root Hash | Mutate corresponding index records |
| PMI-007 | Changing package name, description, or release label alone does not change Package Content Root Hash | Mutate descriptive metadata |
| PMI-008 | Changing index compression, block boundaries, sparse directory, or physical path does not change logical hashes | Re-encode identical logical tables |
| PMI-009 | Adding, removing, or changing cache indexes does not change Package Content Root Hash | Mutate optional cache references |
| PMI-010 | Changing provenance, signatures, timestamps, or provider snapshot metadata does not change Package Content Root Hash | Mutate provenance only |
| PMI-011 | A declared logical hash mismatch is rejected | Corrupt the declared digest |
| PMI-012 | Missing or hash-mismatched required dependencies fail resolution | Provider negative fixtures |
| PMI-013 | Duplicate roots, duplicate keys, unsafe paths, and unsupported schema versions are rejected | Parser adversarial fixtures |
| PMI-014 | Equivalent static and dynamic materializations have the same Package Content Root Hash | Build both from the same roots and snapshot |

## 8. Open decisions

1. Final digest algorithm, digest spelling, and migration strategy.
2. Exact canonical typed encoding used for hash preimages.
3. Whether package-lineage IDs are needed and how they evolve.
4. Whether license/publication policy metadata belongs in a separate descriptor or attestation.
5. Exact identity-bearing index table schemas and dependency-condition model.
6. Whether feature and target selection are represented directly in the manifest or through a referenced, separately hashed resolution profile.
7. Forward-compatible extension mechanism.
8. Whether `Package Content Root Hash` should be a Merkle root over table roots rather than a single digest over the combined logical index.

## 9. Current recommendation

Adopt this as the first reviewable research candidate:

- TOML manifest, kept small and human-readable;
- binary index as the authoritative per-object and relationship catalogue;
- optional cache indexes outside logical package identity;
- separate Object Content Hash, Index Logical Hash, Package Content Root Hash, and Package Archive Hash;
- hash the parsed typed model and canonical logical index records, never raw TOML or physical archive bytes;
- keep the exact canonical encoding and final digest algorithm open pending implementation and benchmark evidence.

## 10. Executable prototype evidence

An initial executable model is available in [Package Identity Prototype 01](PROTOTYPES/PACKAGE-IDENTITY-01/README.md), with its [implementation](PROTOTYPES/PACKAGE-IDENTITY-01/package_identity.py) and [tests](PROTOTYPES/PACKAGE-IDENTITY-01/test_package_identity.py).

The prototype implements a narrow TOML v1 candidate parser, explicit typed canonical encoding, domain-separated SHA-256 digests, logical index hashing, and package-root verification. It exercises PMI-001–PMI-014 and additional canonical-encoding/parser checks. The focused run completed **18 tests successfully**, and Python bytecode compilation passed.

The evidence is deliberately bounded:
- PMI-012 currently verifies stale-index-hash rejection after a dependency target changes; provider-side missing-object and transitive-closure resolution are not implemented.
- PMI-014 compares equivalent logical inputs; it does not run independent static and dynamic builders.
- PMI-010 verifies the architectural separation of provenance sidecars from identity inputs; it does not parse or verify signatures.
- The prototype's SHA-256 choice, typed encoding, and table shapes are experimental and are not accepted as normative.

This is a research proposal, not a normative LLMLang package specification.
