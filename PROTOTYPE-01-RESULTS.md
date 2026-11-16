# Prototype 01 Results: Dependency-Driven Content Addressing

**Status:** Experimental result, not a normative LLMLang decision  
**Date:** 2026-11-16  
**Prototype:** `PROTOTYPES/DEPENDENCY-GRAPH-01/`

## 1. Objective

Test whether a content-addressed semantic value graph with explicit dependencies and immutable project snapshots can represent selective evolution without a mandatory Occurrence identity.

The central scenario: 100 caller definitions initially reference `calculate_tax@H0`; a new rule applies to only three callers, which are moved to `calculate_tax@H1`.

## 2. Implementation

The prototype uses only the Python standard library.

Implemented:
- deterministic JSON canonicalization and SHA-256 value hashes;
- immutable semantic value records;
- exact hash-relevant dependency references;
- content-store deduplication;
- reverse dependency queries;
- snapshot-scoped active dependency queries;
- immutable snapshot roots and parent references;
- three-way snapshot merge for disjoint edits and explicit same-key conflicts;
- separate context-scoped relation storage for provenance/traceability;
- dependency-closure digest and verification-key construction;
- deterministic disk serialization and reload;
- schema-version and document-checksum validation;
- atomic file replacement;
- cross-process hash and snapshot-root reproducibility tests.

The prototype deliberately has no parser, compiler, persistence database, LLM integration, proof engine, authorization system, or production-grade transaction protocol.

## 3. Experiment: 100 Callers, Three Migrations

### 3.1 Setup

1. Create immutable function value `calculate_tax@H0`.
2. Create 100 distinct caller values, each with a hash-relevant `calls -> H0` dependency.
3. Create a baseline snapshot selecting H0 and all 100 callers.
4. Create `calculate_tax@H1`.
5. Rebuild only callers 001, 002, and 003 with a dependency on H1.
6. Create a candidate snapshot selecting H1 and the 100 caller selections (three new values, 97 old values).

### 3.2 Measured result

| Metric | Result |
|---|---:|
| Initial caller count | 100 |
| Changed caller values | 3 |
| Unchanged caller values | 97 |
| Active dependents of H0 in candidate snapshot | 97 |
| Active dependents of H1 in candidate snapshot | 3 |
| Historical stored dependents of H0 | 100 |
| H0 remains stored | Yes |
| H1 stored | Yes |
| Distinct semantic values in store | 105 |

Changed keys:
- `caller_001`
- `caller_002`
- `caller_003`

The 105 values are H0 + 100 original callers + H1 + 3 replacement caller values.

### 3.3 Interpretation

The selective migration works exactly as hypothesized.

No caller identity record is needed to preserve the old and new caller versions. The snapshot selects the intended version for each caller key. Old immutable values remain available and are not rewritten.

A key distinction emerged during implementation:
- The global content store retains all historical values. Its reverse dependency query therefore finds all 100 old callers still depending on H0.
- The candidate snapshot selects only 97 of those old callers. Its active dependency query therefore finds 97 callers on H0 and three on H1.

Thus **historical dependency graph** and **currently selected project graph** are different views. Impact analysis must state which view it traverses.

## 4. Important Design Finding: Provenance Must Be External

An initial implementation attempt attached non-hash-relevant provenance edges directly to the immutable semantic value record. That caused a canonicalization consistency failure: two semantically identical values with different provenance metadata had the same hash but different stored records.

The implementation was corrected:
- SemanticValue stores only hash-relevant dependencies.
- RelationStore stores non-semantic relations separately and scopes them to a project/context.

This demonstrates why provenance, lineage, ownership, and traceability must not be embedded in a deduplicated semantic value unless they truly affect its semantics.

## 5. Persistence Experiment

### 5.1 Format

The persisted document is deterministic JSON with:
- a format identifier;
- an explicit schema version;
- all immutable semantic values and their hash-relevant dependencies;
- context-scoped relations;
- immutable snapshots, selections, and parent roots;
- a SHA-256 checksum over the complete payload.

Values are emitted in hash order, relations in tuple order, and snapshots in root-hash order. The serializer uses the same canonical JSON encoding as the prototype's hash function.

### 5.2 Reload validation

Loading reconstructs semantic values through the ordinary ContentStore insertion path. It therefore recomputes each semantic value hash rather than trusting the serialized hash field.

The loader also checks:
- document checksum;
- format identifier and supported schema version;
- dependency availability and acyclic reconstruction order;
- every recomputed semantic value hash;
- every snapshot root hash;
- that every selected value exists in the reconstructed store.

Missing dependencies and dependency cycles are rejected. Unknown schema versions are rejected rather than guessed or silently upgraded.

File writes use a temporary file in the destination directory, flush and fsync it, then atomically replace the destination. This protects readers from observing a partially written file on filesystems that provide atomic same-filesystem replacement. It is not a multi-writer transaction protocol.

### 5.3 Results

Automated tests verify:
1. semantic hashes survive save/reload;
2. snapshot roots survive save/reload;
3. closure digests survive save/reload;
4. provenance relations survive save/reload;
5. serialization is byte-for-byte deterministic for equivalent stores built in different insertion orders;
6. checksum validation detects payload tampering;
7. unsupported schema versions are rejected;
8. snapshots referencing absent values are rejected;
9. a separate Python process reloads the file and obtains identical value hashes, closure digest, and snapshot root.

The cross-process test uses a fresh interpreter process. It is a practical reproducibility check on the same runtime/platform, not yet a cross-Python-version or cross-platform canonicalization guarantee.

## 6. Automated Tests

The original 10 semantic graph tests remain, with 7 persistence tests added.

Run locally:

```bash
cd PROTOTYPES/DEPENDENCY-GRAPH-01
python -m unittest discover -s tests -v
python -m src.semantic_graph
```

## 7. What the Prototype Demonstrates

Supported by these experiments:
- selective caller migration does not require mandatory Occurrence identity;
- immutable old and new function values can coexist;
- exact callee references make changed caller values hash differently;
- unchanged callers can be reused unchanged;
- snapshot selection distinguishes active versions from historical values;
- provenance can vary independently of semantic value identity;
- direct dependency changes propagate through rebuilt dependent values;
- snapshot merges can combine disjoint selection changes and report same-key conflicts;
- graph values and snapshots can be serialized and reloaded without changing their hashes in the tested environment;
- corruption, unsupported schema versions, and missing selected values are rejected.

## 8. What It Does Not Demonstrate

The prototype does not prove:
- that a real language frontend can extract a complete dependency graph;
- that dynamic dispatch, overload resolution, effects, or external bindings are modeled correctly;
- that business impact analysis can infer which three callers ought to change;
- that all transitive dependents should automatically be rewritten;
- that recursive dependency cycles can be canonically hashed;
- that the in-memory merge algorithm is sufficient for concurrent distributed updates;
- that verification evidence is sound or reusable in a real proof system;
- that storage, indexing, or hashing performance is acceptable at scale;
- that the file format is stable across future schema versions, runtimes, or platforms.

The three changed callers are supplied explicitly by the experiment. The graph does not infer business intent from reachability. That remains a separate requirement/context analysis problem.

## 9. Limitations and Known Simplifications

1. **Canonical form:** JSON is only a convenient prototype encoding. LLMLang still needs a canonical semantic IR and explicit language-version/domain separation.
2. **Cycles:** semantic values must be reconstructible from already available dependencies. Recursive SCC/group hashing is not implemented.
3. **Dependency roles:** the prototype records relation and role but does not yet define a full relation taxonomy or dispatch semantics.
4. **Snapshot merge:** three-way merge is keyed by logical selection names; it does not validate ancestry, read/write sets, semantic invariants, or authority.
5. **RelationStore:** context-scoped relations are minimally modeled and currently persisted through a private in-memory collection.
6. **Persistence format:** version 1 is a prototype interchange format. There is no migration framework, locking, concurrent writer coordination, database indexing, garbage collection, or recovery journal.
7. **Atomicity:** atomic replacement protects a single file from partial replacement where supported; it does not provide compare-and-swap or multi-process transaction isolation.
8. **Verification:** only key construction is tested; no proof is run.
9. **Security:** hashes detect accidental or deliberate content changes only when the expected checksum/root is trusted. They are not signatures, authorization controls, or proof of origin.

## 10. Next Experiments

Recommended order:

1. Model interface hashes separately from implementation hashes and add binding snapshots.
2. Add requirement-to-value traceability with split/merge scenarios; prove that provenance changes do not rehash semantic values.
3. Add a dependency impact report that distinguishes historical dependents, active dependents, and potentially affected values.
4. Add concurrent proposal preconditions and stale-root rejection.
5. Define recursive-group hashing for mutually recursive definitions.
6. Benchmark hashing, reverse-index construction, snapshot diff, serialization, and reload on larger synthetic graphs.
7. Define whether a persistent store should be append-only object files, a transactional database, or a content-addressed filesystem layout.

## 11. Conclusion

The initial 100-caller hypothesis passed its first executable test: 97 old callers can remain unchanged while three move to a new callee value.

The persistence extension adds a second positive result: in the tested environment, graph values, snapshots, closure digests, and context relations survive deterministic serialization and reload, including reload from a fresh Python process. The loader rejects tested corruption and unsupported schema versions rather than accepting unverified state.

The experiment also reinforces a key separation: **the historical value store, the selected snapshot, and the non-semantic provenance graph must remain distinct.**

These results justify continuing the prototype. They do not establish a final LLMLang identity model, a stable storage format, or a production persistence architecture.
