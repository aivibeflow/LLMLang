# Research Study 08: Context-Derived Occurrence Addressing

**Date:** 2026-11-16  
**Status:** Architectural exploration / proposed direction, not an accepted LLMLang decision  
**Question:** Can an Occurrence be computed as `H(ValueHash, ContextHash, Role, Slot)` and preserve independent evolution without introducing a global Stable Entity ID?

## 1. Executive conclusion

The proposed formula is useful for identifying an **immutable occurrence state**, but it does not by itself provide a stable identity for an occurrence across edits.

```text
OccurrenceStateHash = H(
    ValueHash,
    ContextHash,
    Role,
    Slot
)
```

If any input changes, the occurrence hash changes. That is correct for immutable content addressing. But a system still needs a way to select the successor occurrence as the current continuation of a prior occurrence.

The key finding is:

**A computed occurrence hash can replace a persistent identifier for an occurrence state. It cannot also provide continuity across changing states unless some other stable selector exists.**

That selector may be:
- a stable local slot within a parent/context;
- a snapshot-scoped mapping;
- an explicit lineage edge selected by a branch or project root;
- a persistent context token.

The first three can avoid a global Stable Entity ID. The fourth is effectively a scoped Stable ID, even if called ContextHash.

Preliminary recommendation:
1. Keep semantic values immutable and content-addressed.
2. Treat OccurrenceState as an optional immutable content-addressed record.
3. Do not use a mutable parent ValueHash as the sole continuity anchor for a child slot.
4. Resolve current occurrences through an immutable project snapshot and a context-local slot mapping.
5. Introduce a stable slot key only where independent lifecycle, ownership, or governance requires it; document that it is a scoped identity mechanism.
6. Keep lineage explicit and many-to-many. Never infer continuity solely from equal content, source specification, role, or a display name.

This is a research result, not an accepted change to LLMLang-CONCEPT.md.

## 2. Definitions

### 2.1 Semantic Value

An immutable semantic object:

```text
ValueHash = H(
    domain = "LLMLANG/VALUE/v1",
    canonical_semantics,
    hash_relevant_dependencies
)
```

The same canonical semantic value may be referenced by many occurrences. Provenance that does not affect semantics is excluded from this hash.

### 2.2 Occurrence State

An immutable contextual record saying that a value occupies a role in a particular context:

```text
OccurrenceStateHash = H(
    domain = "LLMLANG/OCCURRENCE-STATE/v1",
    ValueHash,
    ContextStateHash,
    Role,
    SlotDescriptor
)
```

An occurrence state describes one fact at one point in the immutable graph. A later state is a new object.

### 2.3 Slot

A selector for a contextual position in a parent or scope. A slot is not automatically stable. It can be:
- snapshot-local (valid only inside one project root);
- derived from immutable parent state and a semantic slot descriptor;
- persistent within a local scope (therefore a scoped identity);
- explicitly replaced or split through lineage.

### 2.4 Context

The context must be defined by purpose. At least three meanings must not be conflated:

- **Context state:** immutable content hash of the contextual facts. Changes when those facts change.
- **Context scope:** a logical scope such as a project, module, requirement, or workflow. May have a persistent local key.
- **Snapshot:** immutable root selecting the current graph state.

A single field called ContextHash that mixes these meanings creates ambiguity.

### 2.5 Lineage

Explicit immutable relations between values, occurrence states, slots, and decisions. Examples:
- `supersedes`
- `derived_from`
- `split_into`
- `merged_from`
- `replaced_in_slot`
- `moved_from`
- `satisfies`

Lineage records history; a snapshot or branch head selects current state.

## 3. The formula under test

The initial proposal is:

```text
O = H(V, C, R, S)
```

where:
- `V` = ValueHash;
- `C` = ContextHash;
- `R` = Role;
- `S` = Slot.

This is deterministic only if all inputs have canonical representations and their semantics are stable. Domain separation and a versioned encoding are required. A robust conceptual encoding is:

```text
H(
  "LLMLANG/OCCURRENCE-STATE/v1" ||
  encode(ValueHash) ||
  encode(ContextStateHash) ||
  encode(Role) ||
  encode(SlotDescriptor)
)
```

Do not concatenate ambiguous variable-length strings without typed, length-delimited encoding.

The formula has an immediate consequence: it computes a state address, not a timeless occurrence identity. If the value changes from V0 to V1, then O0 and O1 differ. That is expected. The missing operation is not hashing; it is resolving which O1, if any, continues O0 in a particular accepted snapshot.

## 4. Four candidate architectures

### A. Fully derived occurrence state

```text
O = H(ValueHash, ContextStateHash, Role, SlotDescriptor)
```

All inputs are immutable state facts. Any change creates a new occurrence hash.

**Advantages**
- Fully content-addressed.
- No persistent occurrence identifier.
- Identical contextual facts deduplicate.
- Easy to verify and cache exact occurrence states.

**Disadvantages**
- Cannot follow an occurrence through edits without lineage or a selector.
- If ContextStateHash includes the full parent state, any parent edit changes all descendant occurrence hashes.
- A move changes context and therefore address, even if the semantic value is unchanged.
- Current-state lookup requires a snapshot or explicit graph traversal.

**Assessment:** good immutable state identity; insufficient as the only continuity mechanism.

### B. Stable local slot plus changing value

```text
SlotKey = H(ParentScopeKey, SlotDefinition)
OccurrenceStateHash = H(SlotKey, ValueHash, Role, ContextStateHash)
```

The SlotKey remains constant while the value changes.

**Advantages**
- Straightforward independent evolution.
- Two equal values can occupy different slots and evolve separately.
- A value edit does not change the slot selector.
- Rename and movement can be represented separately from value changes.

**Disadvantages**
- ParentScopeKey or SlotKey must remain stable.
- If the key survives arbitrary edits, it is a scoped Stable ID in substance.
- If SlotDefinition uses a name, ordinal, or path, rename/reorder/move can break continuity.
- If SlotKey is derived from a mutable parent hash, parent edits cascade into the key.

**Assessment:** practical when scoped identity is genuinely needed. Do not describe it as identity-free.

### C. Snapshot-scoped slot mapping

```text
ProjectRoot R0:
  slot S -> OccurrenceState O0

ProjectRoot R1:
  slot S -> OccurrenceState O1
```

The slot selector is meaningful only inside a pinned project root or branch context. The accepted root commits to the mapping.

**Advantages**
- No global permanent occurrence ID is needed.
- The current state is unambiguous inside a snapshot.
- Branches can map the same local slot to different occurrence states.
- The same value can be shared across many slots.
- Rebase and merge are explicit changes to snapshot mappings.

**Disadvantages**
- A slot reference outside its snapshot is incomplete.
- Comparing slots across snapshots requires lineage or a local continuity rule.
- If a slot must survive independently of its parent/snapshot, a stronger identity mechanism becomes necessary.

**Assessment:** strongest default for a content-only architecture. It makes the scope of identity explicit and avoids promising global continuity.

### D. Structural address (parent + path)

```text
Address = (ProjectRoot, ParentOccurrence, ChildSelector)
```

**Advantages**
- Natural for tree-shaped regions.
- No separately allocated global ID.
- A reference can be resolved by traversing a pinned snapshot.

**Disadvantages**
- Parent changes may invalidate descendant paths.
- Numeric indexes are unstable under insertion/reordering.
- Names are unstable under rename and may collide.
- A semantic selector may become a slot key and thus reintroduce scoped identity.
- General SPGs are graphs, not necessarily trees; a node can have multiple incoming relations.

**Assessment:** useful as a navigation address, not a general persistent identity model.

## 5. ContextHash: the critical design trap

The formula is only as stable as the definition of ContextHash.

### 5.1 ContextHash includes the full parent content hash

```text
ContextHash = ParentValueHash
O = H(ValueHash, ParentValueHash, Role, Slot)
```

A parent edit changes ParentValueHash, which changes O even if the child value, role, and logical slot are unchanged.

This creates a Merkle cascade. It may be correct if the child occurrence semantically depends on the exact parent state. It is wasteful and misleading if the parent hash is included only to locate the child.

**Rule of thumb:** include a dependency in the hash only if changing that dependency changes the meaning of the object being hashed.

### 5.2 ContextHash is a stable opaque token

If ContextHash is preserved across parent edits, it can preserve occurrence continuity. But it now performs the function of a persistent identifier.

This can be acceptable if it is:
- scoped to a project/module/parent rather than global;
- created only for independently managed slots;
- not confused with the content hash;
- not treated as an authorization capability;
- explicitly versioned and governed.

But the architecture should say plainly: this is a scoped stable identity token.

### 5.3 ContextHash is the source specification hash

A requirement hash is an exact provenance anchor, not a guaranteed slot identity:
- one requirement can yield multiple operations, tests, proofs, or implementations;
- one artifact can satisfy multiple requirements;
- a requirement can split or merge;
- an artifact can remain valid after the source requirement changes.

Adding Role helps distinguish kinds, but two artifacts can share the same requirement and role. A SlotDescriptor is still needed.

### 5.4 ContextHash is the project root

This provides excellent snapshot-relative resolution, but any new accepted root changes the context. It is therefore a snapshot selector, not a persistent occurrence key.

This is often a feature: old references remain resolvable against old roots, and new roots select new states.

## 6. Slot design and stability

The SlotDescriptor is the most consequential part of the formula.

| Slot representation | Stability | Main problem |
|---|---|---|
| Display name | Low | Rename and collisions |
| Array/list index | Low | Insertions and reordering |
| Parent content hash + index | Low | Parent edit and index changes |
| Source requirement hash | Medium for provenance, low for continuity | Split/merge and many-to-many mapping |
| Role + source requirement hash | Better classification | Multiple artifacts of same role |
| Semantic selector | Depends on semantics | May be hard to define or canonicalize |
| Explicit local slot declaration | High within its scope | It is a scoped identity object |
| Snapshot-local generated handle | High within one snapshot only | Cannot be used outside that snapshot |

A slot descriptor should express *which semantic position is meant*, not merely how it happens to be displayed or serialized.

If the system cannot derive a unique semantic selector, it should not guess. It should require an explicit slot declaration or keep the mapping snapshot-local.

## 7. Stress tests

### Scenario 1: Two identical values in independent contexts

Initial state:

```text
Slot A -> Value V0
Slot B -> Value V0
```

The semantic value is deduplicated: both slots reference V0. The occurrences remain distinct because their slot/context differs.

After independent edits:

```text
Slot A -> V1
Slot B -> V2
```

All four architectures can represent the values. Only B or C can resolve the two current slots without searching ambiguous lineage. A requires an explicit mapping or a unique branch-scoped lineage rule.

**Result:** content deduplication and independent lifecycle are separate concerns.

### Scenario 2: Parent edit, child unchanged

Initial:

```text
Parent P0
  Slot S -> O0(V0)
```

Parent changes to P1, but the child's meaning and slot are unchanged.

- A with ContextHash=P0 changes O0 to O1 because the parent hash changed.
- B changes only if its slot key depends on P0.
- C creates a new root mapping; it may point to the same O0 if occurrence semantics are unchanged.
- D may invalidate the path if it is structurally anchored to P0.

**Result:** a parent hash must not be included merely because the parent contains the child. Use a parent dependency hash only when the child occurrence's meaning actually depends on that exact parent state.

### Scenario 3: Rename

A slot or artifact display name changes, but semantics and ownership remain the same.

If name is part of SlotDescriptor, the occurrence hash changes. This may be correct for a name-bearing semantic value, but wrong if the name is merely a label.

Separate:
- semantic name (part of value when observable);
- display alias (presentation metadata);
- slot selector (contextual position).

A rename can then update an alias or create a new semantic value while preserving a scoped slot selector. Whether it is the same managed occurrence is a lineage/decision question.

**Result:** names must not silently serve as identity.

### Scenario 4: Move between parents

An artifact moves from Parent A to Parent B.

If context is the parent hash, the occurrence hash changes. This is correct for a contextual occurrence, but does not say whether the move preserves lifecycle continuity.

Represent explicitly:

```text
O1 --moved_from--> SlotA
O2 --moved_to--> SlotB
O2 --continues_from--> O1  // only if the move is accepted as continuity
```

The continuity relation is a semantic decision, not a hash result. If the target scope has independent ownership, policy may require a new occurrence without continuity.

**Result:** movement and identity continuity must be separate.

### Scenario 5: Requirement split

S1 is replaced by S2a and S2b. An artifact formerly associated with S1 may:
- satisfy both new requirements;
- satisfy only one;
- split into two artifacts;
- be replaced entirely.

A formula based on S1 cannot determine the correct successor slot. The accepted traceability mapping must express the decision.

**Result:** source requirement hash is provenance, not an identity key.

### Scenario 6: Requirement merge

S1a and S1b are consolidated into S2. A single artifact may combine earlier artifacts. A one-parent occurrence lineage is insufficient.

**Result:** lineage must support many-to-many transformations; occurrence addressing must not encode a false one-to-one source relationship.

### Scenario 7: Duplicate slot descriptors

Two siblings have the same ValueHash, Role, and SlotDescriptor under the same context.

Then their OccurrenceStateHash values collide by construction—not due to a cryptographic collision, but because the logical input tuples are identical.

If the system intends two independent occurrences, the slot descriptors were not sufficiently discriminating. It must:
- define distinct semantic slots;
- add an explicit local discriminator;
- or represent the two as one shared occurrence with two references, if that is the intended semantics.

Do not append arbitrary list positions just to force uniqueness unless ordering is semantic and stable.

**Result:** uniqueness is a modeling requirement, not something a hash function can manufacture.

### Scenario 8: Two branches independently edit the same slot

Both branches start at root R0 and slot S -> O0. Branch A maps S -> O1; branch B maps S -> O2.

The branch roots preserve both choices. A merge must resolve the write/write conflict or prove the changes compatible. If O1 and O2 have identical content, their value hash may deduplicate, but proposal and approval histories remain distinct.

**Result:** snapshot mapping + compare-and-swap head is sufficient for current-state selection; no global occurrence ID is required.

### Scenario 9: One value serves multiple requirements

One implementation value V satisfies requirements S1 and S2. There may be:
- one shared occurrence with two traceability edges;
- two contextual occurrences that independently govern use in each subsystem.

The correct representation depends on lifecycle and ownership, not on the number of provenance edges.

**Result:** do not bake a single source spec into ValueHash or assume one occurrence per requirement.

## 8. Hash dependency and graph cycles

The OccurrenceStateHash formula can introduce cycles if ContextStateHash includes a parent or graph root that itself includes the occurrence.

Example:

```text
ProjectRootHash -> OccurrenceHash
OccurrenceHash -> ContextHash
ContextHash -> ProjectRootHash
```

This is a recursive hash equation. It cannot be solved by ordinary one-pass Merkle hashing.

Possible strategies:
1. Make context an independently addressable acyclic object that does not include the occurrence being hashed.
2. Hash a parent/scope descriptor that excludes the child occurrence reference.
3. Use a snapshot manifest that maps slot keys to occurrence hashes, while occurrence hashes do not include the root manifest hash.
4. For genuinely recursive semantic groups, define an explicit SCC/group hashing strategy or a canonicalization procedure. Do not accidentally rely on hash fixed points.

Nix documents the practical difficulty of self-references in content-addressed store paths: a direct self-reference would require finding a hash fixed point, so Nix uses a sentinel/rewrite strategy for supported cases. This is a useful warning, not a ready-made LLMLang design. See [Nix content-addressing documentation](https://nix.dev/manual/nix/2.34/store/store-object/content-address.html).

## 9. Canonicalization and deterministic hashing

A content-addressed occurrence requires:
- a versioned canonical encoding;
- explicit hash algorithm identifier;
- domain separation between Value, OccurrenceState, SlotDescriptor, Snapshot, and Evidence;
- typed, length-delimited fields;
- deterministic ordering for sets and unordered edges;
- explicit distinction between absent, null, empty, and default values;
- a defined Unicode and numeric normalization policy;
- a rule for unknown extension fields;
- a policy for hash algorithm migration.

Graph canonicalization is not equivalent to sorting serialized nodes by their current names. Symmetric anonymous graph nodes can require graph-aware canonical labeling. W3C RDFC-1.0 is a useful reference for the general difficulty and for denial-of-service considerations in canonicalization. It should not be assumed to be LLMLang's direct algorithm. See [W3C RDF Dataset Canonicalization](https://www.w3.org/TR/rdf-canon/).

## 10. Security and authorization

Neither ValueHash nor OccurrenceStateHash is an authorization token.

Knowing a hash must not grant:
- read access to a private project;
- mutation rights;
- ownership;
- permission to replace a slot;
- permission to accept a proposal.

A slot mapping can be private even if the underlying semantic value is deduplicated. Authorization should be evaluated against project/scope policy and the operation being performed.

This is particularly important if identical semantic values are shared across projects or tenants.

## 11. Relation to Lore's hash-plus-context design

Epic Games' Lore separates:
- a content hash, which identifies payload bytes;
- a context tag, which tracks the logical file identity across content changes and moves;
- a partition, which is the access boundary;
- a revision/root, which selects an immutable repository snapshot.

Lore's context is a stable per-file identifier, not a value derived from the current content hash. The pair (hash, context) allows equal payloads to be deduplicated while maintaining separate histories and scopes.

This is a strong precedent for separating payload identity from contextual lifecycle. But it is not evidence that a fully derived `H(ValueHash, ContextHash, Role, Slot)` eliminates stable identity. Lore preserves continuity with a persistent context token. LLMLang can choose a narrower, snapshot-local or parent-local form of this mechanism, but should state the trade-off explicitly.

Reference: https://github.com/EpicGames/lore/blob/main/docs/explanation/system-design.md

## 12. Proposed architecture for a first LLMLang prototype

The following is a research proposal only.

### 12.1 Always present

**Semantic Value**

```text
ValueHash = H(canonical semantic content + semantic dependencies)
```

### 12.2 Optional when independent lifecycle/governance is needed

**Occurrence State**

```text
OccurrenceStateHash = H(
    ValueHash,
    ContextStateHash,
    Role,
    SlotDescriptor
)
```

ContextStateHash must not automatically be the full parent or project root hash. It should contain only context facts that are semantically relevant to this occurrence state.

### 12.3 Always present for accepted project state

**Snapshot mapping**

```text
ProjectRoot = H(
    canonical graph snapshot,
    slot-to-occurrence/value mappings,
    relevant policy/configuration references
)

ProjectHead = mutable pointer to ProjectRoot
```

A slot lookup is conceptually:

```text
resolve(ProjectRoot, Scope, SlotDescriptor)
    -> OccurrenceStateHash | ValueHash | NotFound | Ambiguous
```

The lookup must be deterministic. Ambiguous is a real result; it must not be silently resolved by display name or list order.

### 12.4 Optional local slot key

If an artifact needs continuity across multiple snapshots independently of its parent content, introduce:

```text
SlotKey = H(
    "LLMLANG/SLOT/v1",
    ScopeKey,
    SlotDeclaration
)
```

This is a scoped stable selector. It should be created only for independently managed slots. If ScopeKey itself needs to survive arbitrary edits, it too is a scoped identity and should be acknowledged as such.

### 12.5 Lineage and acceptance

A change proposal records:
- baseline ProjectRoot;
- read set and write set of slot mappings;
- candidate occurrence/value hashes;
- explicit lineage decisions;
- verification evidence;
- approval digest.

Acceptance conditionally advances ProjectHead from the expected baseline root. A stale head requires rebase and revalidation.

## 13. Prototype comparison matrix

| Property | A: fully derived | B: stable local slot | C: snapshot mapping | D: structural path |
|---|---|---|---|---|
| Immutable state addressing | Yes | Yes | Yes | Via snapshot |
| Independent identical occurrences | With distinct context/slot | Yes | Yes | If paths differ |
| Survives value edit as same selector | No | Yes | Within explicit mapping | Maybe |
| Survives parent edit | Only if context excludes parent hash | If key is independent | New root can remap | Often no |
| Survives move | No, unless context excludes location | Yes if slot key retained | Through explicit remapping | Usually no |
| Global Stable ID required | No | No, but local stable key | No | No |
| Hidden scoped identity risk | Low | Explicit | Medium | Medium |
| Current state unambiguous | Needs selector | Yes | Yes within root | Yes within root |
| General SPG suitability | High as state hash | High for managed slots | High | Limited |

## 14. Preliminary design rules

These are proposed research rules, not normative LLMLang requirements:

1. ValueHash identifies immutable semantic content, not a continuing managed artifact.
2. OccurrenceStateHash identifies one immutable contextual state, not a timeless occurrence.
3. A change to any hash-relevant input creates a new hash.
4. ContextStateHash MUST NOT include parent/project state merely to encode containment.
5. SlotDescriptor MUST NOT default to display name, ordinal, or mutable path.
6. A slot selector MUST have an explicit scope.
7. If a slot selector survives arbitrary value and parent edits, it is a scoped stable identity mechanism and MUST be described as such.
8. Current occurrence resolution MUST be relative to a pinned snapshot, branch, or explicit scope.
9. A snapshot mapping MUST be immutable and included in the ProjectRoot hash.
10. A move MUST be distinct from a value edit; continuity across the move MUST be explicit.
11. Lineage MUST support split, merge, and multiple successors.
12. Equal ValueHash MUST NOT imply equal Occurrence or equal governance identity.
13. Hash references MUST NOT imply authorization.
14. Canonicalization and hash algorithm versions MUST be part of the address contract.
15. Recursive hash dependencies MUST be rejected or handled by a documented SCC/canonicalization strategy.

## 15. Recommended next experiment

Implement a minimal executable model with:
- two identical values in separate slots;
- two project roots sharing one parent;
- independent edits to one slot;
- a parent edit that leaves the child unchanged;
- a move from one parent scope to another;
- a requirement split and a merge;
- two branches editing the same slot;
- a duplicate slot descriptor;
- a snapshot merge with stale-head detection.

Compare A, B, and C using the same test cases. Record:
- number of distinct hashes and slot keys;
- which references change after each edit;
- whether current-state resolution is unique;
- how many explicit lineage decisions are needed;
- how many descendant hashes are invalidated;
- serialized bytes and approximate LLM token cost;
- complexity of authorization and merge conflict detection.

Do not adopt a single scheme based only on elegance of the formula. Measure the cost of continuity, invalidation, and ambiguity.

## 16. References

- Epic Games Lore system design: https://github.com/EpicGames/lore/blob/main/docs/explanation/system-design.md
- Nix content-addressed store objects: https://nix.dev/manual/nix/2.34/store/store-object/content-address.html
- W3C RDF Dataset Canonicalization: https://www.w3.org/TR/rdf-canon/
- IPFS/IPNS mutable naming over immutable content: https://docs.ipfs.tech/concepts/ipns/

## 17. Final assessment

The formula `H(ValueHash, ContextHash, Role, Slot)` is a sound candidate for an immutable **OccurrenceStateHash**, provided all fields are canonical and hash-relevant. It is not a complete solution for persistent occurrence continuity.

The cleanest content-only default is:

- **ValueHash** — what the semantic value is;
- **OccurrenceStateHash** — what value occupies what role/slot in what immutable context state;
- **ProjectRoot** — which complete mapping is current in a particular accepted snapshot;
- **Lineage** — how states and slots were transformed;
- **optional SlotKey** — a scoped stable selector only where independent lifecycle/governance requires continuity.

This avoids a global Stable Entity ID in the semantic core, but it does not abolish identity as a domain requirement. It confines identity to the scopes where the system actually needs it.

**The decisive distinction is not “hash versus ID”. It is “immutable state address versus continuity selector versus snapshot-relative current-state selection”.**
