# Research Study 06: Content-Addressed Entity Identity and Specification-Anchored Lineage

**Date:** 2026-11-16  
**Status:** Architectural exploration / proposed direction, not an accepted LLMLang decision  
**Question:** Can LLMLang use hashes of entity content as the primary and possibly only entity addresses, while using references to source specifications when a more stable relationship is needed?

## 1. Executive summary

This study investigates a more radical alternative to the Stable Entity ID + Content Hash split proposed in Research Study 05.

The alternative is:

- Every semantic entity state is an immutable value addressed by a cryptographic hash of its canonical semantic content and hash-relevant references.
- Editing an entity creates a new immutable state with a new hash. The old state remains addressable.
- Relationships between versions are explicit graph edges such as `supersedes`, `derived_from`, `refines`, or `implements`.
- A reference to the exact source specification (or exact requirement node within it) can anchor provenance and explain why an entity exists.
- A project snapshot/root identifies the currently accepted graph. A mutable project head points to the current accepted root; it is not the identity of any entity.

This model may eliminate the need for a separate persistent Stable Entity ID. It is not equivalent to simply hashing an editable record in place: it changes the semantic model from identity-oriented mutable entities to immutable content-addressed values and graph relationships.

**Preliminary conclusion:** LLMLang should seriously consider a content-addressed value model as its default semantic core. A source-specification reference is a promising lineage anchor, but it must not automatically be mixed into the entity's semantic content hash. The distinction between semantic content, provenance, and contextual occurrence must be explicit.

This is a research conclusion, not an accepted change to `LLMLang-CONCEPT.md`.

## 2. The proposed model

### 2.1 Entity state is the addressable object

Define an entity state as:

```text
EntityState = {
    kind,
    canonical_semantic_content,
    hash_relevant_edges
}
EntityHash = H(domain, canonical_encode(EntityState))
```

The hash identifies the exact canonical state. It does not identify a mutable object that persists independently of its state.

For example:

```text
H1 = hash(Operation {
    input: Integer,
    output: Integer,
    contract: x > 0
})

H2 = hash(Operation {
    input: Integer,
    output: Integer,
    contract: x >= 0
})
```

If the contract changes, H1 and H2 differ. Both versions remain valid immutable objects. There is no need to mutate H1 or preserve its address while changing its content.

### 2.2 Versions are graph nodes, not mutable rows

An edit produces a new state and may record a relationship to the prior state:

```text
H1 --superseded_by--> H2
```

The edge is historical/provenance information. It need not be part of the semantic content hash of H2.

A branch is naturally represented by multiple successors:

```text
       H2
      /
H1 --
      \
       H3
```

A merge produces a new state H4 with explicit parent/proposal provenance:

```text
H2 ----\
        > H4
H3 ----/
```

This avoids requiring a mutable identity record to represent branches. The graph itself records history.

### 2.3 The accepted project root identifies the current graph

An accepted snapshot is itself content-addressed:

```text
ProjectRoot = H(
    specification_root,
    design_root,
    implementation_root,
    other_semantic_roots
)
```

A mutable project-head pointer selects the currently accepted root:

```text
project_head -> ProjectRootHash
```

The pointer is mutable; the root and all objects reachable from it are immutable. Historical roots remain addressable.

This is similar to the distinction in IPFS between immutable CIDs and mutable IPNS pointers. IPNS is a useful analogy for the project head, not a reason to introduce mutable entity IDs.

## 3. What does the source specification reference provide?

A source specification reference can provide a stable explanation of origin without acting as the identity of the implementation/design entity.

For example:

```text
OperationState H_impl_1 {
    semantic_content: ...
    provenance: {
        derived_from: SpecNodeHash H_spec_17
    }
}
```

The specification reference points to an exact immutable specification node, not merely a mutable textual path or display name.

This gives several useful properties:

1. **Stable provenance:** H_spec_17 continues to identify the exact source requirement even after the specification evolves.
2. **No name collision:** the reference is a cryptographic content address, not a user-chosen symbol.
3. **Auditable derivation:** a reviewer can inspect the exact requirement from which an implementation or design element was derived.
4. **Version-aware traceability:** a newer requirement has a different hash and can be related to the earlier requirement using explicit evolution edges.
5. **No separate global identity allocation:** the origin reference can anchor lineage for many derived artifacts.

A specification root hash alone may be insufficient if the source is one particular requirement. Prefer a direct hash reference to the exact specification node, optionally accompanied by the specification root/snapshot in which it was accepted.

## 4. Do not automatically include provenance in the semantic content hash

There are two different questions:

- Are these two entity states semantically identical?
- Did these two entity states originate from the same specification or process?

Those questions should not be answered by one hash unless LLMLang deliberately wants provenance to affect semantic identity.

Consider two operations with identical canonical semantics, derived independently from two different requirements:

```text
H_semantic = H(kind, canonical_semantics, semantic_edges)
```

If provenance is included:

```text
H_contextual = H(H_semantic, source_spec_hash)
```

Then identical semantic content from different source requirements receives different contextual hashes.

That may be desirable for separately governed artifacts, but it defeats content deduplication and conflates meaning with history.

Recommended separation:

| Data | Included in semantic EntityHash? | Purpose |
|---|---:|---|
| Entity kind | Yes | Type/domain separation |
| Canonical semantic payload | Yes | Exact meaning/state |
| Hash-relevant semantic edges | Yes | Commit to dependencies |
| Source specification reference | Normally no | Provenance/traceability |
| `supersedes` / `derived_from` history | Normally no | Lineage |
| Display label / alias | No | Human presentation |
| Source location | No | Navigation |
| Author / timestamp | No | Audit metadata |
| Authorization / approval | No | Governance |

If a source-specification reference changes the actual meaning or constraints of the entity, it is not merely provenance: it must be represented as a semantic edge and included in the relevant hash. The classification must be based on semantics, not on the field's name.

## 5. The important consequence: equal hashes mean equal canonical values, not necessarily the same independently managed occurrence

Suppose two different requirements independently call for the same operation:

```text
SpecNode A -> Operation with canonical content X
SpecNode B -> Operation with canonical content X
```

Both operations produce the same semantic content hash if provenance is excluded.

This is not a cryptographic collision. It is intentional content equality.

There are two possible interpretations:

### 5.1 Value semantics (recommended default)

The two references point to one shared immutable semantic value. Their different origins are recorded as separate provenance edges:

```text
SpecNode A --derives--> H_X
SpecNode B --derives--> H_X
```

If the operations are truly identical and have no independent mutable lifecycle, sharing is beneficial. It enables deduplication and avoids artificial identity.

### 5.2 Independently managed occurrences

Sometimes two identical definitions must evolve independently because they occupy different architectural roles, have different ownership, or are governed by different policies.

In that case, the graph needs an explicit occurrence/context object. For example:

```text
Occurrence {
    semantic_value: H_X,
    source_spec: H_spec_A,
    role: ...
}
```

The occurrence can be addressed by its own content hash. If two occurrences have identical semantic value, origin, and role, they are equal under this model. If they still must be distinct, the model needs an explicit distinguishing fact (for example, a distinct parent slot, scope, or creation event).

**Important:** A system cannot both erase every distinguishing fact and still distinguish two otherwise identical occurrences. A hash does not solve that logical problem; it only makes the chosen canonical distinction addressable.

The default should be value semantics. Add occurrence identity only where independent lifecycle or governance is a real requirement.

## 6. Does this solve versioning?

It solves a different and arguably cleaner versioning problem:

- No object is overwritten.
- Every state has a permanent immutable address.
- Old versions never become ambiguous.
- Branches and merges are represented by graph topology.
- A snapshot identifies an exact accepted state of the project.
- Reproducible references can always target exact historical content.

However, it does not make all references automatically follow the newest version.

A reference to H1 must continue to mean H1. If a consumer should use H2, a new consumer state or a mutable selection/pointer must explicitly refer to H2.

This is intentional. A reference that silently changes its target is not an immutable content reference.

For LLM interaction, the development engine may resolve a short-lived handle such as `@e17` to a specific hash within a pinned project snapshot. The handle is a context-local convenience, not a persistent identity.

## 7. Specification evolution and lineage

A specification node is itself an immutable content-addressed value.

When a requirement changes:

```text
Spec Hs1 --superseded_by--> Spec Hs2
```

An implementation derived from Hs1 does not magically become derived from Hs2. It remains linked to the exact source requirement Hs1 until it is reviewed, adapted, or revalidated against Hs2.

A later implementation can record:

```text
Implementation Hi2 {
    derived_from: Hs1,
    satisfies: Hs2
}
```

The two relations mean different things:

- `derived_from`: historical origin;
- `satisfies`: current claimed/verified relationship.

A `satisfies` edge must carry an explicit validation/verification state and evidence. It must not be treated as proof merely because the edge exists.

This distinction is especially important when a requirement is revised but the implementation happens to remain valid. The implementation's semantic hash need not change if its own semantics did not change; its verification/traceability evidence may need to be refreshed.

## 8. Hashing graph references and dependency closure

The semantic hash should commit to typed, hash-relevant dependencies:

```text
EntityHash =
    H(
        domain_separator,
        entity_kind,
        canonical_semantic_payload,
        sorted(
            edge_kind,
            target_entity_hash
        )
    )
```

Only dependencies that affect the entity's semantic state should be included.

For example:
- An implementation that depends on a public specification should include the relevant specification hash.
- A consumer that depends only on a provider's public specification should not change its semantic hash merely because the provider changes an internal implementation while preserving the same specification.
- A provenance-only `derived_from` relation should normally not alter the semantic hash.
- A test or proof result should be a separate evidence object tied to exact input hashes and tool identities, not silently embedded as a mutable property.

The hash-relevant dependency graph must be acyclic or use a formally specified canonical group/SCC hashing construction. Ordinary provenance and history edges can be cyclic or multi-parent only if their representation does not recursively participate in the semantic hash.

## 9. Canonicalization is a prerequisite

Hash-based addressing is only deterministic if semantically equal values serialize identically.

The canonicalization contract must define:
- field ordering;
- set versus sequence semantics;
- normalization of numbers, strings, and identifiers;
- treatment of absent/default values;
- typed edge ordering;
- encoding version;
- hash algorithm identifier;
- domain separation;
- treatment of unordered and symmetric graph structures;
- treatment of recursive structures and cycles.

The W3C RDF Dataset Canonicalization specification is a useful warning and reference: canonicalizing graphs with anonymous nodes is not equivalent to sorting JSON fields. Symmetric or structurally indistinguishable nodes require graph-aware canonical labeling, and pathological inputs can make canonicalization expensive. See https://www.w3.org/TR/rdf-canon/.

The canonical encoding and hash algorithm must be versioned. If the canonicalization rules change, LLMLang must not silently reinterpret old hashes. The algorithm/version identifier must be part of the address format or its domain-separated input.

## 10. Name collisions versus cryptographic hash collisions

Removing names eliminates collisions caused by two authors independently choosing the same symbol in a namespace. It does not mathematically eliminate hash collisions.

The system should:
- use a modern cryptographic hash (initially SHA-256 is a reasonable candidate);
- retain the complete digest in persistent references;
- include the algorithm and hash-domain/version identifier;
- verify stored content against its claimed hash when reading/importing;
- compare canonical content if a duplicate digest is encountered;
- never use a shortened display digest as the authoritative key.

Domain separation prevents a value of one type or purpose from being confused with another merely because the same byte payload is used.

A cryptographic hash provides computational collision resistance, not a proof that collisions are impossible.

## 11. Comparison of the three identity architectures

| Property | Stable ID + Content Hash | Content hash only | Content hash + specification-anchored lineage |
|---|---|---|---|
| Exact immutable state address | Yes | Yes | Yes |
| Stable address across edits | Stable ID | No | No; lineage is stable through history |
| Immutable history | Requires version model | Natural | Natural |
| Same content deduplication | Separate storage layer | Natural | Natural if provenance excluded |
| Independent identical entities | Stable IDs distinguish them | Need explicit occurrence/context | Need explicit occurrence/context |
| Rename collision | Avoided if names are aliases | Avoided | Avoided |
| Provenance | Separate links | Optional links | First-class source-spec links |
| Version branch/merge | Requires identity-aware rules | Graph-native | Graph-native |
| Mutable current pointer | Usually needed | Needed at project/snapshot level | Needed at project/snapshot level |
| Risk of identity/content conflation | Moderate | High if semantics are underspecified | Manageable with separate provenance |

## 12. Potential architecture for LLMLang

A promising minimal model has four concepts:

1. **Content-addressed semantic value** — immutable entity state, addressed by its full hash.
2. **Typed semantic edge** — a reference to another exact value, included in the hash only if semantically relevant.
3. **Provenance/lineage edge** — source specification, predecessor, derivation, supersession, or merge history.
4. **Accepted graph root/head** — immutable snapshot hash plus a mutable pointer selecting the current accepted snapshot.

No permanent Stable Entity ID is required in this model.

Illustrative representation:

```text
SpecNode Hs1 = hash(canonical_spec_requirement)

Operation H1 = hash(canonical_operation_state)

Lineage:
    H1 --derived_from--> Hs1

Revision:
    Operation H2 = hash(canonical_revised_operation_state)
    H2 --supersedes--> H1
    H2 --derived_from--> Hs1

Specification update:
    SpecNode Hs2 = hash(canonical_revised_requirement)
    Hs2 --supersedes--> Hs1

Traceability:
    H2 --satisfies--> Hs2
    Evidence E2 verifies (H2, Hs2, verifier/configuration)
```

The example intentionally allows the historical origin to remain Hs1 while current conformance is evaluated against Hs2.

## 13. Consequences for the Change model and development engine

The content-only model changes how Change proposals should be represented:

- A proposal targets an exact hash in a pinned baseline snapshot.
- Preconditions compare expected hashes, not mutable entity IDs.
- An edit produces a candidate hash.
- A merge produces a new candidate graph root.
- Acceptance atomically advances the project head from the expected old root to the new root.
- Approval binds to the exact candidate root, baseline root, policy, and evidence.
- A stale proposal is rebased by constructing a new candidate; the previous candidate remains immutable.
- Context-local aliases are resolved against the pinned snapshot and must not silently survive into a different snapshot without re-resolution.

This aligns naturally with optimistic concurrency and immutable graph snapshots.

## 14. Benefits

Potential benefits:
- No separately allocated permanent identity for every semantic entity.
- Versioning becomes immutable by construction.
- Exact historical references are straightforward.
- Same canonical content can be deduplicated.
- Name and namespace collisions cease to be identity problems.
- Branching and merging become graph operations.
- Source specification links provide durable provenance.
- Hash-based cache keys and verification inputs become natural.
- LLM-facing context can use compact local handles while persistent storage retains full hashes.

## 15. Risks and unresolved questions

1. **Independent identical occurrences:** Which entity kinds need independent lifecycle or authorization despite identical semantic content?
2. **Occurrence address:** If needed, should an occurrence be scoped by parent hash, source-spec hash, role, or an explicit creation event?
3. **Specification anchor:** Should provenance point to a requirement node hash, a specification root hash, or both?
4. **Origin versus current conformance:** Which relations are mandatory: `derived_from`, `supersedes`, `refines`, `implements`, `satisfies`?
5. **Specification change:** How are affected entities discovered when a requirement's hash changes?
6. **Hash dependency classification:** Which edges affect semantic value hashes and which are provenance-only?
7. **Cycles:** What canonical group hashing scheme, if any, is required for recursive semantic entities?
8. **Canonicalization:** Which graph canonicalization algorithm and limits are acceptable for symmetric structures?
9. **Partial edits:** How are local handles and patches resolved safely when the underlying snapshot changes?
10. **Hash agility:** How are algorithm/canonicalization upgrades migrated without invalidating historical references?
11. **Security:** How are untrusted imported objects validated, and how are authorization decisions kept separate from hash possession?
12. **Human navigation:** What generated views make hash-addressed graphs usable without turning aliases into hidden identity?

## 16. Research references

- IPFS, IPNS and mutable pointers to immutable CIDs: https://docs.ipfs.tech/concepts/ipns/
- IPFS immutability and immutable objects: https://docs.ipfs.tech/concepts/immutability/
- IPFS architecture, Merkle DAGs and naming: https://github.com/ipfs/specs/blob/main/ARCHITECTURE.md
- Nix content-addressed store objects and reference constraints: https://nix.dev/manual/nix/2.34/store/store-object/content-address.html
- Nix derivations and references to not-yet-realized outputs: https://nix.dev/manual/nix/2.34/store/derivation/
- W3C RDF Dataset Canonicalization 1.0: https://www.w3.org/TR/rdf-canon/
- IPLD Data Model and content-addressed links: https://ipld.io/docs/data-model/

## 17. Preliminary recommendation

Investigate and prototype **content-addressed immutable semantic values with specification-anchored provenance**, rather than assuming every entity needs a permanent Stable Entity ID.

The default semantic address should be the hash of canonical semantic content and hash-relevant dependencies. Provenance, source specification, predecessor, supersession, approval, and verification should be represented as typed links or separate evidence records, and excluded from the semantic hash unless they alter meaning.

Use value semantics and deduplication by default. Introduce a separately addressable occurrence/context object only when two otherwise identical values genuinely require independent lifecycle, ownership, or governance.

Do not yet remove the Stable ID model from the concept document. First test the content-only architecture against concrete scenarios: rename, identical requirements, independent evolution, requirement revision, branch/merge, recursive types, and incremental verification.
