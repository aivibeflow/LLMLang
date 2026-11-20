# Research Study 07: Stress-Testing Content-Only Identity

**Date:** 2026-11-16  
**Status:** Architectural exploration / proposed direction, not an accepted LLMLang decision  
**Question:** Can content hashes plus specification-anchored lineage replace persistent Stable Entity IDs under independent evolution, specification changes, branching, merging, and requirement splitting?

## 1. Executive conclusion

The content-only model survives basic versioning and branching scenarios, but the stress tests reveal an important boundary:

**A content hash identifies an immutable semantic value. It does not, by itself, identify a continuing independently managed lineage.**

A permanent Stable Entity ID is not necessarily required. However, if LLMLang needs to recognize "this is the same independently managed artifact, now in a new state", it must retain some continuity mechanism. Possible mechanisms are:

1. a predecessor/successor lineage graph;
2. a specification anchor plus a stable role/slot within that specification;
3. a context/occurrence object with its own content address;
4. a mutable selection binding in a snapshot or project manifest.

These mechanisms are not equivalent.

A source specification hash alone is not a universal substitute for Stable ID. One requirement can produce many artifacts; one artifact can satisfy several requirements; requirements can split, merge, or be replaced; and multiple independently managed artifacts can derive from the same requirement.

**Preliminary recommendation:** keep content hashes as the only addresses for immutable semantic states. Do not reintroduce a global permanent ID by default. Add explicit lineage and, only where required, a content-addressed Occurrence / ArtifactSlot object that represents independent lifecycle or governance. Use specification references as provenance and traceability, not as an assumed one-to-one identity key.

This is a research conclusion, not an accepted change to LLMLang-CONCEPT.md.

## 2. Terminology

- **Value hash:** hash of canonical semantic content and hash-relevant semantic dependencies.
- **Lineage edge:** historical relationship such as supersedes, derived_from, split_from, or merged_from.
- **Specification anchor:** exact hash of a requirement/specification node, optionally pinned to its accepted specification root.
- **Occurrence:** an addressable contextual use of a semantic value, where independent lifecycle, ownership, or governance is required.
- **Project root:** immutable root hash of an accepted project snapshot.
- **Head:** mutable pointer to the current accepted project root.

The word "entity" is potentially ambiguous in this model. Some things currently called entities may be reusable semantic values; others may be contextual occurrences, governance records, or historical events. The schema should distinguish these categories rather than forcing one identity model onto all of them.

## 3. Scenario A: Two identical entities must evolve independently

### Initial state

Two requirements independently call for the same operation:

~~~text
Value H0 --derived_from--> Spec A
Value H0 --derived_from--> Spec B
~~~

The operation's canonical semantic content is identical, so both references resolve to H0.

Now the owners make different changes: the A-side operation changes its contract; the B-side operation changes its error behavior.

### What works

The immutable value graph can represent both outcomes:

~~~text
          ┌--> H1
H0 -------┤
          └--> H2
~~~

No collision or overwrite occurs. Both histories remain available.

### What is missing

The system needs to know which successor belongs to which independently managed context. A bare supersedes edge from H0 is ambiguous because H0 has two successors.

Specification anchors may disambiguate branches if each branch has a distinct, stable source requirement and the artifact is unambiguously associated with that requirement. But this assumption is often false:
- one requirement may produce multiple operations, tests, types, and proofs;
- one operation may implement several requirements;
- a requirement may be moved or decomposed;
- multiple requirements may be merged into one;
- an implementation may be retained while its original requirement is superseded.

### Occurrence solution

Represent independently managed contexts explicitly:

~~~text
Occurrence OA { value: H0, governing_spec: Spec A, role: ... }
Occurrence OB { value: H0, governing_spec: Spec B, role: ... }
~~~

After independent edits:

~~~text
OA0(value=H0) --supersedes--> OA1(value=H1)
OB0(value=H0) --supersedes--> OB1(value=H2)
~~~

The occurrence is itself immutable and content-addressed. Its hash commits to its value reference and the context facts that define the occurrence. It is not a global random Stable ID.

### Finding

Content-only identity works if shared values are allowed to be shared. Independent lifecycle requires distinct contextual occurrences or another explicit branch selector.

A source-spec hash can be one component of occurrence context, but should not be assumed sufficient.

## 4. Scenario B: A specification changes, but the implementation remains valid

### Initial state

~~~text
Spec S1
  └--> Implementation I1
~~~

S1 is revised into S2. The change is editorial or relaxes a condition that I1 already satisfies.

### Correct behavior

- S1 remains immutable and addressable.
- S2 receives a new hash.
- I1 remains the same semantic value and keeps its hash.
- Historical derived_from(I1, S1) remains true.
- The system re-evaluates whether I1 satisfies S2.
- If verified, a new evidence record records verification of (I1, S2, verifier identity, configuration, assumptions, environment).

~~~text
S2 --supersedes--> S1
I1 --derived_from--> S1
I1 --satisfies--> S2
Evidence E2 verifies (I1, S2, verifier/config/environment)
~~~

The satisfies edge is a claim or relation whose verification state is carried by evidence. It is not automatically true because the graph contains the edge.

The implementation's value hash should not change merely because the specification changed. Its relationship to the current specification and its verification evidence may change without any implementation semantic edit.

### Finding

This scenario is handled cleanly by content hashes plus explicit typed relations and evidence. A permanent Stable ID provides no essential benefit here.

## 5. Scenario C: Two branches independently change the same starting value and then merge

### Initial state

Project root R0 references value H0. Two proposals start from R0: branch A produces H1; branch B produces H2.

~~~text
       H1
      /
H0 --
      \
       H2
~~~

The branches are immutable. Project roots RA and RB commit to their respective graph snapshots.

### Merge behavior

If changes are semantically compatible, a merge creates a new value H3:

~~~text
H1 --\
      > H3
H2 --/
~~~

The merge provenance records both parents or both source Change Sets. The accepted project root R3 references H3 and the updated graph.

If changes conflict, the merge is not accepted. A conflict-resolution proposal creates a new candidate. It does not rewrite H1 or H2.

If both branches produce identical canonical content, both produce the same value hash. The graph can deduplicate the value. Their proposal histories and approvals remain separate records.

### Atomic acceptance

The accepted project head must advance conditionally:

~~~text
CAS(project_head, expected=R0, new=R3)
~~~

If the head has moved since the merge baseline was prepared, acceptance fails as stale and the candidate must be rebased and revalidated.

This matches the immutable-object / mutable-head separation used by content-addressed systems. IPNS describes mutable pointers to immutable CIDs; Git similarly distinguishes immutable object hashes from refs that select commits.

### Finding

Branching and merging are natural in a content-addressed graph. Stable Entity IDs are not required to preserve branch history. Exact baseline hashes and an atomic project-head update are essential.

## 6. Scenario D: One requirement splits into two requirements

This scenario is particularly important for specification-anchored identity.

### Initial state

~~~text
Spec S1
  └--> Artifact I1
~~~

A requirement is found to contain two independent responsibilities. It is replaced by S2a and S2b:

~~~text
       ┌--> S2a
S1 ----┤
       └--> S2b
~~~

The existing implementation I1 may satisfy both new requirements, only one, need to be split into I1a and I1b, or become obsolete.

### Why source specification cannot be the sole identity

If the artifact's identity is simply its source specification hash, a split creates an ambiguous mapping:
- Should I1 now belong to S2a or S2b?
- Should I1 be duplicated?
- Does it acquire two identities?
- If it is split, which child is the continuation of the old artifact?

There is no universally correct answer from hashes alone. This is a semantic decision that must be represented.

### Correct graph representation

~~~text
S1 --split_into--> S2a
S1 --split_into--> S2b

I1 --derived_from--> S1
I1 --satisfies--> S2a
I1 --satisfies--> S2b
~~~

If the implementation is split:

~~~text
I1 --split_into--> I1a
I1 --split_into--> I1b

I1a --satisfies--> S2a
I1b --satisfies--> S2b
~~~

The split relation is not a one-to-one version transition. It is an explicit graph transformation with potentially one-to-many lineage. If a child is not a semantic continuation but a newly extracted artifact, its relation should be derived_from or extracted_from, not a falsely strong identity-preservation claim.

### Finding

Specification hashes provide exact historical anchors, but they do not define stable artifact identity through requirement decomposition. Explicit many-to-many lineage is required.

## 7. Scenario E: Two requirements merge into one

The reverse case is equally important:

~~~text
S1a --\
       > S2
S1b --/
~~~

An implementation may combine two earlier artifacts:

~~~text
I1a --\
       > I2
I1b --/
~~~

A model that assumes one source specification per artifact cannot represent this faithfully. The artifact may have multiple origins and satisfy a consolidated requirement.

Use typed many-to-many provenance and traceability edges. Do not force a single primary source merely to obtain a stable identifier.

## 8. Scenario F: Same requirement, multiple independently managed artifacts

One requirement may be implemented by multiple components, platform-specific backends, alternative algorithms, or test/proof artifacts:

~~~text
             ┌--> Implementation A
Requirement S┤
             ├--> Implementation B
             ├--> Test T
             └--> Proof P
~~~

The source specification hash alone cannot identify each artifact. A role/type discriminator is needed at minimum. Even (SpecHash, Kind) is insufficient if there are two operations or two tests of the same kind.

A context/slot key could be:

~~~text
ArtifactSlot = H(
    parent_context,
    source_spec_hash,
    artifact_role,
    local_discriminator
)
~~~

However, a local discriminator must not be an unstable display name or list position. It must be a semantic slot definition or an explicit creation/decision fact.

If the slot is renamed or moved, the system must decide whether it is the same slot or a new one. That is a continuity decision; no hash function can infer it from content alone.

## 9. Three distinct concepts

### 9.1 Value

A reusable immutable semantic value:

~~~text
ValueHash = H(canonical_semantics, semantic_dependencies)
~~~

Equal canonical values share an address. This is the natural unit for deduplication, exact references, and verification cache inputs.

### 9.2 Occurrence / artifact slot

A value's role in a particular context, when independent lifecycle, ownership, or governance is required:

~~~text
OccurrenceHash = H(
    value_hash,
    context_hash,
    role,
    semantic_slot_definition
)
~~~

The occurrence is also immutable. Its next state is another occurrence hash linked through lineage.

The occurrence model should be optional. Do not create one for every value by default.

### 9.3 Lineage

A relation between immutable states or occurrences:
- supersedes: one state takes the place of another in a particular context;
- derived_from: historical derivation;
- split_into: one source produces multiple successors;
- merged_from: one successor combines multiple sources;
- refines: a specification/design refinement relation;
- implements: implementation relationship;
- satisfies: requirement conformance claim;
- replaces_in_context: explicit contextual replacement.

Lineage is a graph, not necessarily a chain. It can branch, merge, split, and cross specification boundaries.

## 10. Does lineage quietly recreate Stable Entity ID?

It can, if implemented carelessly.

If the system says "follow supersedes to find the current version of this artifact", it needs to know which branch/context to follow. With multiple successors, there is no unique current state.

Possible selectors:
- the current Project Root;
- a parent/slot in the current snapshot;
- a specification/role context;
- an explicit governance binding;
- a branch head or proposal head.

These are contextual selection mechanisms, not immutable identity.

If a permanent artifact key is introduced and survives every edit, it may be a Stable Entity ID under another name. That is not automatically bad, but the architecture should acknowledge the equivalence instead of claiming that identity has disappeared.

The strongest content-only design avoids a global persistent entity ID, while allowing a content-addressed occurrence/slot where the domain needs continuity. Its current state is selected from a pinned project snapshot or context.

## 11. External research and implementation precedents

### 11.1 IPFS / IPNS

IPFS content addressing makes changed content receive a new CID. IPNS provides a mutable name/pointer that can be updated to select a new CID. This supports the separation between immutable content and mutable current selection.

Reference: https://docs.ipfs.tech/concepts/ipns/

### 11.2 Nix content-addressed store

Nix explicitly constrains which references can participate in content-addressed store objects. Its documentation explains that a direct self-reference would require finding a hash fixed point, which is computationally infeasible; it uses a sentinel/rewrite strategy for supported self-reference cases. This is a practical warning for LLMLang's recursive graph hashing.

References:
- https://nix.dev/manual/nix/2.34/store/store-object/content-address.html
- https://manual.determinate.systems/store/store-object/content-address

### 11.3 W3C RDF Dataset Canonicalization

Graph canonicalization with anonymous nodes requires graph-aware algorithms; local sorting is not enough for symmetric structures. LLMLang should not assume canonical graph hashing is trivial.

Reference: https://www.w3.org/TR/rdf-canon/

### 11.4 Lore: hash plus context

The Lore project describes a fragment address as a pair of content hash and context. Equal hashes under different contexts can share payload while retaining distinct version-control histories and deletion scopes. This is a useful analogy for LLMLang's possible separation of reusable semantic value from independently managed occurrence.

Reference: https://github.com/EpicGames/lore/blob/main/docs/explanation/system-design.md

### 11.5 IPFS Merkle DAGs and offline branching

IPFS architecture emphasizes content-addressed links, permanent caching, offline object creation, and network partition/merge. These are useful properties for a graph-first development environment where agents may work on independent snapshots.

Reference: https://github.com/ipfs/specs/blob/main/ARCHITECTURE.md

## 12. Proposed rules emerging from the scenarios

The following are research proposals, not accepted normative rules:

1. A semantic value MUST be immutable and addressed by the hash of its canonical semantic representation.
2. A semantic edit MUST create a new value hash.
3. Equal canonical semantic values SHOULD resolve to the same value hash, regardless of provenance.
4. Provenance MUST be represented separately from semantic content unless it changes semantics.
5. A source specification reference MUST identify an exact immutable specification node, not a mutable path or display name.
6. Provenance and conformance MUST be distinct relations.
7. A specification change MUST NOT silently rewrite historical provenance.
8. Verification evidence MUST be bound to exact hashes of all relevant inputs and verifier/configuration/environment identities.
9. Branches MUST remain independently addressable until an explicit merge.
10. A merge MUST create a new candidate state and preserve its parent/proposal provenance.
11. Acceptance MUST update the project head conditionally against the expected baseline root.
12. One-to-many and many-to-one evolution MUST be represented explicitly; lineage MUST NOT assume a single predecessor or successor.
13. Occurrence/context identity SHOULD be introduced only when independent lifecycle, ownership, or governance requires it.
14. A contextual occurrence MUST itself be immutable and content-addressed.
15. A mutable current-artifact selector MUST be scoped to a project snapshot, branch, or explicit context.
16. A context-local LLM handle MUST resolve to an exact hash within a pinned snapshot and MUST NOT be treated as a persistent identity.
17. Hash algorithms, canonicalization versions, and domain separation MUST be explicit in the persistent address format.
18. Hash possession MUST NOT grant authorization.

## 13. Revised architecture recommendation

Prefer a three-level model:

**Level 1 — Semantic values (always):**
- immutable content-addressed values;
- typed semantic dependencies;
- exact historical references;
- deduplication by canonical content.

**Level 2 — Occurrences / artifact slots (only when needed):**
- contextual role and governance boundary;
- links to semantic values;
- optional independent lifecycle;
- content-addressed occurrence states;
- no global random ID unless an implementation requirement proves it necessary.

**Level 3 — Snapshot and selection (always for accepted project state):**
- immutable Project Root;
- mutable Project Head / branch head;
- snapshot-scoped mapping from contextual slots to current occurrence/value hashes;
- atomic compare-and-swap acceptance.

Specification references are provenance anchors and traceability inputs. They do not define a unique artifact identity by themselves.

## 14. Remaining questions before adopting the model

1. Which SPG node kinds are pure values, and which represent independently managed occurrences?
2. Does every implementation artifact need an occurrence, or only artifacts with independent ownership/lifecycle?
3. Should an occurrence's contextual key derive from its parent slot, source specification, role, and explicit creation decision?
4. How should occurrence continuity be reviewed when its role or parent changes?
5. Can a requirement be split or merged without mandatory human review of the resulting traceability map?
6. Which relations are semantic hash dependencies versus provenance-only edges?
7. How are current occurrences selected when several successors exist in a branch?
8. What is the canonical representation for recursive values and mutually recursive groups?
9. What are the exact conflict semantics when two branches edit the same occurrence but produce identical values?
10. Is a separate immutable Change/Decision event graph needed to make provenance complete without embedding it into semantic values?

## 15. Recommended next experiment

Before changing the concept document, model one small example end-to-end:

- one requirement creates two operations and one test;
- the two operations initially have identical canonical semantics;
- one operation is independently changed;
- the requirement is split into two requirements;
- both implementation branches are checked against the new requirements;
- one branch is merged while the other remains independent;
- a verification result is reused only if all exact inputs still match.

The prototype should compare:
- pure value hashes plus lineage;
- value hashes plus occurrence hashes;
- Stable Entity ID plus Content Hash.

Measure graph complexity, number of persistent identifiers, references that must be rewritten, ambiguity in current-state selection, and LLM context/token cost.

Do not choose a permanent-ID-free model until this experiment has an unambiguous representation for every state transition.

## 16. References

- IPFS IPNS: https://docs.ipfs.tech/concepts/ipns/
- Nix content-addressed store: https://nix.dev/manual/nix/2.34/store/store-object/content-address.html
- Determinate Nix content-addressed store reference: https://manual.determinate.systems/store/store-object/content-address
- W3C RDF Dataset Canonicalization: https://www.w3.org/TR/rdf-canon/
- Epic Games Lore system design (hash + context): https://github.com/EpicGames/lore/blob/main/docs/explanation/system-design.md
- IPFS architecture: https://github.com/ipfs/specs/blob/main/ARCHITECTURE.md

## 17. Final assessment

The stress tests support a more precise statement than "hashes replace Stable IDs":

**Hashes replace mutable entity addresses. Lineage and contextual occurrence replace the continuity functions that Stable IDs used to provide, but only where those functions are actually needed.**

A specification hash is a durable provenance anchor, not a universal identity key. It can anchor an artifact's origin, but one requirement may create many artifacts, one artifact may serve many requirements, and requirements may split or merge.

The preferred direction is therefore:
- content-addressed semantic values as the universal base;
- explicit many-to-many lineage;
- specification hashes as exact provenance/traceability anchors;
- optional content-addressed occurrences for independent lifecycle/governance;
- immutable project roots and mutable snapshot-scoped heads.

This architecture can eliminate a global Stable Entity ID from the semantic core without pretending that independent continuity, ownership, or contextual selection cease to exist.
