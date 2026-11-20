# Research Study 05: Name-Free Semantic Entities and Hash-Based Addressing

**Date:** 2026-11-16  
**Status:** Architectural exploration / proposed direction, not an accepted LLMLang decision  
**Question:** Can LLMLang eliminate entity names and use hashes/opaque identifiers instead?

## 1. Executive conclusion

LLMLang can eliminate names as the primary identity and reference mechanism. It should seriously consider a name-free semantic core in which graph entities are addressed by stable opaque identifiers and immutable states are addressed by content hashes.

However, it should **not** replace every identifier with the current Content Hash.

The correct separation is:

- **Stable Entity ID** — identifies the logical entity across edits.
- **Content Hash** — identifies one exact immutable state of that entity.
- **Human-readable labels / aliases** — optional metadata or namespace bindings for people, generated views, external APIs, and debugging.

The language core can be name-independent without becoming human-hostile. Names can be projections over the graph rather than the source of identity or truth.

## 2. Why direct Content Hash references are not enough

Suppose an operation has state hash H1. An edit changes its contract and body, producing state hash H2.

If all incoming references point directly to H1, then editing the operation appears to create a new entity and every reference must be rewritten. That breaks the desired continuity of logical identity and makes ordinary edits resemble delete-and-create operations.

A Content Hash answers: which exact immutable state? It does not answer: which logical entity across its lifetime?

Therefore, references to mutable logical entities should normally target Stable Entity IDs. A snapshot or immutable historical reference may target a specific Content Hash.

## 3. Three address spaces

| Address | Purpose | Mutable? |
|---|---|---|
| Stable Entity ID | Persistent identity across versions | No |
| Content Hash | Exact immutable entity state | No; a new state gets a new hash |
| Human alias/name | Optional lookup and display binding | Yes |

Illustrative references:

~~~text
EntityRef(StableID: "e_7f3...")
StateRef(ContentHash: "sha256:...")
Alias("billing.transfer") -> StableID("e_7f3...")
~~~

The alias is a lookup convenience. It is not the identity of the target.

## 4. What can be removed from the semantic core?

Potentially removable as mandatory semantic constructs:

- declaration names used only to identify entities;
- variable/function/type names as identity keys;
- names embedded in graph edges;
- path-derived identity;
- textual symbol matching as the primary reference mechanism;
- requirement IDs that are meaningful only as manually assigned labels, provided stable opaque IDs replace them.

What should remain available as optional or specialized metadata:

- display labels and descriptions;
- external API names and serialization field names;
- user-facing command names;
- source-language projection names;
- diagnostic labels;
- namespace aliases and import aliases;
- human-readable requirement identifiers where useful for discussion and audit.

Some names are themselves observable behavior. An exported function name, JSON property, database column, CLI command, or protocol field can be part of an external contract. These cannot be erased from semantics merely because internal graph identity is opaque. They should be modeled as explicit external bindings.

## 5. Name-free language representation

A name-free program can be represented as a typed graph of references:

~~~text
Operation {
    id: EntityID(0x...),
    inputs: [
        EntityRef(0x...),
        EntityRef(0x...)
    ],
    body: [
        Call(EntityRef(0x...)),
        Read(EntityRef(0x...))
    ]
}
~~~

The canonical machine representation need not contain human-chosen symbol names. The compiler resolves references through IDs and typed edges.

A human-readable rendering can assign temporary aliases, such as x17. Those aliases are local presentation handles. They need not be stored in the semantic graph or included in its Content Hash.

An LLM-facing protocol can use short handles within a context window, while the engine maintains the mapping to full Stable IDs. This reduces repeated token cost without making short handles globally meaningful.

## 6. Hashes are not necessarily token-efficient

A cryptographic hash such as SHA-256 is 256 bits. Its hexadecimal representation is 64 characters, which can cost more tokens than a short meaningful name or local handle.

Therefore:
- do not transmit full hashes repeatedly when a session-local handle can safely refer to them;
- use compact binary IDs internally where practical;
- expose abbreviated hashes only for display, never as an unchecked unique identity;
- resolve local handles through an explicit context manifest;
- include the full identity in durable serialized artifacts and validation boundaries.

Optimize the protocol representation, not identity guarantees by truncating hashes.

## 7. Stable ID design options

### Option A: Random opaque ID

Generate a sufficiently strong random ID at entity creation.

Advantages: independent of name, path, and content; naturally survives rename and movement; simple identity semantics.

Disadvantages: not content-addressed; requires persistent allocation and collision handling; deterministic reconstruction from source is harder.

### Option B: Hash of creation event / origin

Derive Stable ID from an immutable creation event, project namespace, and creator nonce.

Advantages: deterministic if the creation event is retained; independent of later mutable content.

Disadvantages: creation-event identity and entity identity become coupled; imports, forks, copies, and merges need explicit rules; a hash does not automatically solve duplicate logical entities.

### Option C: Content Hash as entity ID

Use the hash of current canonical content as the only identity.

Advantages: simple content addressing and deduplication of identical immutable objects.

Disadvantages: every semantic edit changes identity; incoming references and provenance become difficult to preserve; distinct entities with identical content can collapse unless extra context is added; rename and history become awkward; identity and state are conflated.

**Preliminary assessment:** Option C is unsuitable as the sole identity model. Option A or B is more compatible with the current Stable ID / Content Hash distinction.

## 8. Identity and deduplication are different

Two entities can have identical content but different logical identities. Two independent services may expose identical operations but evolve independently or have different ownership and authorization policies.

Content-addressed storage may deduplicate immutable state blobs, but the semantic graph must not assume equal state hashes imply equal logical entity identity.

Conversely, one logical entity can have many immutable states over time.

Storage deduplication and semantic identity must remain separate layers.

## 9. Cycles, recursion, and references

A name-free graph still needs a rigorous model for recursive structures.

Mutually recursive operations cannot be assigned naïve recursive Content Hashes if each hash includes the other's final hash. The current LLMLang concept already recognizes that hash-relevant dependencies must be acyclic or grouped under a canonical root.

Possible approaches:
- stable-ID references in entity state, with separate dependency-root hashing;
- canonical strongly connected component objects whose internal references use stable local indices;
- group-level hashing for mutually recursive declarations.

This must be specified before a hash-only syntax is implementable.

## 10. External names and ABI boundaries

Names cannot disappear where the outside world observes them:
- exported function and type names;
- JSON / Protobuf / database field names;
- HTTP routes;
- CLI commands;
- environment variable names;
- plugin registration keys;
- foreign-function interface symbols.

Model these as explicit bindings:

~~~text
ExternalBinding {
    target: EntityID(...),
    namespace: "json",
    external_name: "customer_id",
    compatibility_policy: ...
}
~~~

The external name is semantic interface data and may be included in the relevant interface Content Hash. It is not the internal identity of the entity.

Renaming an external binding can be a breaking API change even when the target Stable ID is unchanged.

## 11. Human interaction and debugging

A pure hash dump is not an adequate human interface.

The development engine should provide generated, context-local views:
- short aliases for active entities;
- descriptions and purpose summaries;
- relationship paths;
- source locations as navigational metadata;
- grouped views by component, layer, or responsibility;
- stable links to entity history and exact states.

A developer may see an entity handle, a generated label such as “transfer funds”, its kind and layer, current state hash, and callers. The label is a view; the actual reference is the handle mapped to Stable ID, while exact state is separately identified by Content Hash.

The UI should support name-free operations even if it renders friendly labels. Absence of a label must never make an entity unaddressable.

## 12. Security and correctness implications

Opaque IDs and hashes can reduce accidental name collisions and make references unambiguous, but they do not automatically provide authorization or trust.

Required rules:
- every operation validates entity existence and expected state;
- a hash is not a capability or permission;
- possession of an ID does not grant read/write authority;
- aliases must be namespace-scoped and collision-checked;
- abbreviated hashes must never be accepted where full identity is required unless resolved against a trusted manifest;
- hash algorithm identifiers and domain separation are mandatory;
- importing, forking, and merging graphs must define identity preservation and remapping rules.

## 13. Proposed invariants

1. Every semantic entity has an opaque Stable Entity ID independent of mutable labels and source locations.
2. Every immutable semantic state has a Content Hash.
3. Internal graph references target Stable IDs or exact immutable state references, never unqualified human names.
4. Human-readable names are optional aliases/metadata unless explicitly part of an external interface contract.
5. Removing or changing an alias does not change the target Stable ID.
6. Changing semantic content creates a new state hash while preserving Stable ID.
7. Equal Content Hashes do not imply equal logical entity identity.
8. A Content Hash cannot be used as a substitute for authorization.
9. Context-local short handles are valid only within their explicit mapping scope.
10. External names are modeled as observable interface bindings and checked for compatibility.
11. The system remains fully operable when no human-readable alias exists.
12. Hashes are computed over canonical typed structures and hash-relevant dependencies, not rendered text.

## 14. Open questions

1. Should Stable Entity IDs be random, derived from immutable creation events, or allocated by a project-scoped ID service?
2. What is the identity behavior when a repository is forked or copied?
3. When imported graphs contain the same Stable ID but divergent histories, how are they reconciled?
4. Should human aliases live in SPG metadata, a separate name-binding graph, or an external index?
5. Which alias/binding changes are presentation-only, and which are part of external API semantics?
6. Should source DSL allow explicit aliases, or should aliases be generated by the development engine?
7. How should recursive strongly connected components be canonically hashed?
8. What is the compact LLM protocol for referring to thousands of entities without sending long hashes repeatedly?
9. How are local handles invalidated when context is refreshed or a proposal is rebased?
10. Which debugging and audit views are mandatory when names are absent?

## 15. Preliminary recommendation

Adopt a **name-free semantic core**, not a hash-only identity model.

- Stable opaque IDs identify logical entities.
- Content Hashes identify immutable states.
- Typed graph edges carry references.
- Human-readable names are optional aliases and generated presentation.
- External names remain explicit interface bindings where observable.
- The LLM protocol uses short context-scoped handles mapped to full IDs/hashes.

This preserves the benefits of name independence—unambiguous references, safe renames, less textual coupling, graph-native editing—without conflating identity with state or making every edit rewrite the entire graph.

This recommendation is a research conclusion, not an accepted change to LLMLang-CONCEPT.md.

## 16. Internal baseline and related studies

- LLMLang-CONCEPT.md
- TOKEN_EFFICIENCY.md
- RFC-REQUEST-CHANGE.md
- RFC-DEVELOPMENT-ENGINE.md
- RESEARCH-SCENARIO-01-RENAME-IDENTITY.md
- RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md
