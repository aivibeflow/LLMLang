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
- dependency-closure digest and verification-key construction.

The prototype deliberately has no parser, compiler, persistence backend, LLM integration, proof engine, authorization system, or production-grade transaction protocol.

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

This is not merely an implementation detail. It demonstrates why provenance, lineage, ownership, and traceability must not be embedded in a deduplicated semantic value unless they truly affect its semantics.

## 5. Automated Tests

**Result: 10 tests passed.**

Coverage:
1. Three out of 100 callers change; 97 remain unchanged.
2. Identical semantic values deduplicate.
3. Different project provenance does not change semantic value identity.
4. Reading a stored payload cannot mutate the stored value.
5. Changing a hash-relevant dependency changes the dependent hash.
6. Rebuilding a dependency chain produces new hashes at each changed level.
7. Reverse transitive dependency traversal.
8. Disjoint snapshot edits merge.
9. Conflicting edits to the same selection key are reported.
10. Verification keys change when dependency closure or verifier identity changes.

Run locally:

```bash
cd PROTOTYPES/DEPENDENCY-GRAPH-01
python -m unittest discover -s tests -v
python -m src.semantic_graph
```

## 6. What the Prototype Demonstrates

Supported by this experiment:
- selective caller migration does not require mandatory Occurrence identity;
- immutable old and new function values can coexist;
- exact callee references make changed caller values hash differently;
- unchanged callers can be reused unchanged;
- snapshot selection distinguishes active versions from historical values;
- provenance can vary independently of semantic value identity;
- direct dependency changes propagate through rebuilt dependent values;
- snapshot merges can combine disjoint selection changes and report same-key conflicts.

## 7. What It Does Not Demonstrate

The prototype is intentionally small. It does not prove:
- that a real language frontend can extract a complete dependency graph;
- that dynamic dispatch, overload resolution, effects, or external bindings are modeled correctly;
- that business impact analysis can infer which three callers ought to change;
- that all transitive dependents should automatically be rewritten;
- that recursive dependency cycles can be canonically hashed;
- that the in-memory merge algorithm is sufficient for concurrent distributed updates;
- that verification evidence is sound or reusable in a real proof system;
- that storage, indexing, or hashing performance is acceptable at scale.

The three changed callers are supplied explicitly by the experiment. The graph does not infer business intent from reachability. That remains a separate requirement/context analysis problem.

## 8. Limitations and Known Simplifications

1. **Canonical form:** JSON is only a convenient prototype encoding. LLMLang still needs a canonical semantic IR and explicit language-version/domain separation.
2. **Cycles:** dependencies must point to already stored values. Recursive SCC/group hashing is not implemented.
3. **Dependency roles:** the prototype records relation and role but does not yet define a full relation taxonomy or dispatch semantics.
4. **Snapshot merge:** three-way merge is keyed by logical selection names; it does not validate ancestry, read/write sets, semantic invariants, or authority.
5. **RelationStore:** context-scoped relations are in-memory and minimally modeled.
6. **Verification:** only key construction is tested; no proof is run.
7. **Persistence:** no disk/database storage, garbage collection, indexing, or concurrent writes.
8. **Security:** hashes are integrity identifiers, not authorization controls.

## 9. Next Experiments

Recommended order:

1. Add a real graph serializer and reload snapshots from disk; verify deterministic hashes across processes.
2. Model interface hashes separately from implementation hashes and add binding snapshots.
3. Add requirement-to-value traceability with split/merge scenarios; prove that provenance changes do not rehash semantic values.
4. Add a dependency impact report that distinguishes historical dependents, active dependents, and potentially affected values.
5. Add concurrent proposal preconditions and stale-root rejection.
6. Define recursive-group hashing for mutually recursive definitions.
7. Benchmark hashing, reverse-index construction, and snapshot diff on larger synthetic graphs.

## 10. Conclusion

The core hypothesis passes its first executable test.

For the 100-caller scenario, content-addressed semantic values plus exact dependency references and immutable snapshots are sufficient to preserve 97 old callers while migrating three callers to a new function value. A mandatory Occurrence layer adds no value to this scenario.

The experiment also reveals an important modeling rule: **the historical value store, the selected snapshot, and the non-semantic provenance graph must remain distinct.**

This is evidence for continuing with a dependency-driven prototype, not a final decision to remove every form of stable identity from LLMLang.
