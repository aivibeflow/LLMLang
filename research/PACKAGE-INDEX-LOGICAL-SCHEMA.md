# Package Index Logical Schema and Merge — Prototype 01

**Status:** Research proposal; logical model is executable, wire format is not normative  
**Research area:** RT-12 — Libraries, packages, templates, and artifact reuse  
**Updated:** 2026-11-18  
**Related:** [Package System](PACKAGE-SYSTEM.md), [Package Manifest and Content Identity](PACKAGE-MANIFEST-AND-IDENTITY.md), [Package Identity Prototype 01](PROTOTYPES/PACKAGE-IDENTITY-01/README.md)

## 1. Scope

This proposal defines a first logical schema for the four identity-bearing package-index tables and a deterministic merge contract. It deliberately does not define byte offsets, integer widths, compression frames, block directories, sparse indexes, or a final digest algorithm.

The schema is designed around these constraints:

- exact immutable object hashes are the object identity;
- table keys are explicit and unique;
- each table has one canonical key order;
- records can be merged as sorted streams;
- metadata conflicts are errors, never last-writer-wins;
- optional external dependencies are distinguishable from included objects;
- the logical digest is independent of physical index layout.

## 2. Shared scalar conventions

| Type | Logical form | Validation |
|---|---|---|
| ContentHash | Algorithm-tagged digest string, initially `sha256:<64 lowercase hex>` in the prototype | Parse and validate algorithm and digest length; final algorithm registry remains open |
| StableID | Opaque, non-empty, case-sensitive identifier | No implicit Unicode normalization; grammar remains a separate decision |
| ObjectKind | Versioned enum/string identifier | Unknown required kinds fail closed |
| Size | Non-negative integer byte count | Must fit the eventual format's declared range |
| Boolean | `true` / `false` | No truthy coercion |
| Conditions | Canonical typed condition value | No host/environment inference; condition language remains open |

All key comparisons are over canonical typed key bytes, not locale-aware strings. For the current prototype, UTF-8 byte ordering is used for string fields and parsed digest bytes are used for hashes. This is an experiment, not the final wire contract.

## 3. Logical tables

### 3.1 Objects

One row per included immutable object.

| Field | Required | Meaning |
|---|---:|---|
| `hash` | Yes | Exact Content Hash; primary key |
| `kind` | Yes | Versioned object-kind identifier |
| `size` | Yes | Canonical object payload size in bytes |

**Primary key:** `hash`.

Two rows with the same hash must be byte-for-byte equivalent as logical records. A different kind or size for the same hash is an integrity conflict. Storage path, archive offset, compression codec, and provider location are not logical object fields.

### 3.2 Dependencies

One row per dependency edge declared by an included source object.

| Field | Required | Meaning |
|---|---:|---|
| `source_hash` | Yes | Included object that declares the edge |
| `edge_id` | Yes | Stable edge key within the source object |
| `kind` | Yes | Dependency classification, initially `required`, `optional`, `target`, or `evidence` |
| `target_hash` | Yes | Exact target Content Hash |
| `included` | Yes | Whether target object is included in this package |
| `condition` | No | Canonical condition for conditional edges |

**Primary key:** `(source_hash, edge_id)`.

The source must be included. If `included=true`, the target must also be present in Objects. If `included=false`, the edge is an explicit external reference and the target must not be counted as package membership merely because it appears here. Whether a given dependency kind is allowed to be external depends on the package dependency policy and is not fully enforced by this prototype.

### 3.3 Exports

One row per public export name in a module.

| Field | Required | Meaning |
|---|---:|---|
| `module_id` | Yes | Owning module Stable ID |
| `name` | Yes | Public export name, case-sensitive |
| `object_hash` | Yes | Exact object implementing/declaring the export |

**Primary key:** `(module_id, name)`.

The module and referenced object must exist. An export name cannot be duplicated within one module. The same object may be exported by multiple modules or under multiple names if the language-level module rules permit it.

### 3.4 Modules

One row per module.

| Field | Required | Meaning |
|---|---:|---|
| `module_id` | Yes | Module Stable ID; primary key |
| `members` | Yes | Set of included object Content Hash values |

**Primary key:** `module_id`.

Membership is a set: duplicates are invalid and values are sorted canonically for hashing/serialization. Every member must exist in Objects. Empty modules are permitted only if the package model explicitly allows them; the prototype permits them pending a semantic decision.

## 4. Cross-table invariants

1. Object hashes are unique.
2. Dependency edge keys are unique per source.
3. Every dependency source is an included object.
4. An included dependency target exists in Objects.
5. External dependency targets do not imply inclusion.
6. Module IDs are unique and module members exist in Objects.
7. Export keys are unique; export module and object references exist.
8. Every package root is an included Object row (enforced by the package identity layer).
9. All record fields are schema-checked; unknown fields fail closed in this prototype.
10. No physical locator, compressed size, block offset, sparse-key sample, provider URL, or timestamp belongs in these logical records.

## 5. Canonical table order

The proposed order is lexicographic over typed key tuples:

| Table | Canonical key |
|---|---|
| Objects | parsed `hash` (algorithm identifier, then digest bytes) |
| Dependencies | `(source_hash, edge_id)` |
| Exports | `(module_id, name)` |
| Modules | `module_id` |

For this prototype, the canonical ordering function is explicit and shared by validation, digest calculation, and merge. A production format must specify byte-level encodings and ordering in its versioned schema.

## 6. Deterministic merge contract

Given two or more valid indexes:

1. Validate each input independently before merging.
2. Merge each table in canonical key order (a k-way streaming merge is the intended implementation).
3. If a key occurs once, retain its row.
4. If the same key occurs in multiple inputs with identical logical records, retain one row.
5. If the same key occurs with different logical records, fail with a conflict identifying table and key.
6. Validate the merged cross-table references.
7. Produce the same logical result and logical digest regardless of input index order or merge grouping.

No input is preferred by recency, source order, provider priority, or timestamp. A conflict is not resolved by last-writer-wins. Provider availability/source locations, if needed, belong in a separate non-identity overlay that can retain multiple locations for one object hash.

### 6.1 Streaming and memory

The executable prototype uses in-memory lists for clarity. It proves only the record-level semantics. The intended scalable implementation holds one current row per input stream and advances the stream with the smallest key. Equal-key rows are compared before advancing. This gives memory proportional to the number of input streams plus output buffering, excluding the output itself.

### 6.2 Merge associativity

For valid, conflict-free inputs, merge should be associative, commutative, and idempotent at the logical-index level:

- `merge(A, B) = merge(B, A)`
- `merge(merge(A, B), C) = merge(A, merge(B, C))`
- `merge(A, A) = A`

Conflicting inputs must fail regardless of grouping/order. The prototype tests these properties on fixtures.

## 7. Logical digest boundary

The logical index digest commits to the four normalized tables and their complete logical records. It excludes:

- binary serialization choices and schema-independent physical layout;
- compression codec and compressed bytes;
- block and sparse directories;
- file paths, offsets, and storage locations;
- provider availability overlays;
- archive timestamps, signatures, and provenance;
- optional cache indexes and cache payloads.

The existing Package Identity Prototype 01 supplies an experimental domain-separated digest function. This new prototype does not standardize or replace it; it uses the same logical principle and must be reconciled with the identity prototype before any final hash contract is accepted.

## 8. Deliberately unresolved

- Final hash algorithms, canonical typed encoding, and algorithm agility.
- Exact grammar and lifecycle of Stable IDs and edge IDs.
- Full dependency taxonomy and policy-specific closure validation.
- Whether empty modules are valid.
- Whether export names need a language/namespace discriminator.
- Whether dependency conditions need their own typed table or referenced condition objects.
- Additional identity-bearing tables for proofs, tests, implementation bindings, or package-level semantic metadata.
- Binary wire format, version negotiation, checksums, block compression, sparse directory, and benchmarks.
- Provider availability overlay and trust/provenance semantics.

## 9. Prototype exit criteria

The logical schema prototype is useful if it demonstrates:

- schema and cross-reference validation;
- canonical ordering and duplicate-key rejection;
- exact-record deduplication;
- conflicting-record rejection;
- deterministic merge under input permutation and grouping;
- digest stability under input ordering;
- digest change when identity-bearing records change.

Passing these tests does not establish production readiness or a final binary index specification.
