# RT-24 Identity Architecture Decision Matrix

**Status:** Research decision record; no final identity architecture selected  
**Date:** 2026-11-18  
**Scope:** Reconciliation of Research Studies 05–08, the Draft Glossary, RT-03, package identity, and the current semantic-graph prototype

## 1. Purpose

This record compares the identity alternatives against concrete lifecycle, merge, and semantic-model scenarios. It is intended to prevent the identity decision from being made implicitly by prototype data structures or hash implementation details.

It does **not** adopt a normative LLMLang identity model, canonical SPG schema, hash envelope, or language semantic profile.

Read this document together with the [Draft Glossary](../../../draft/GLOSSARY.md), [Study 05](../../semantic-representation/RT-05/RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md), [Study 06](../../semantic-representation/RT-05/RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md), [Study 07](../../semantic-representation/RT-05/RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md), [Study 08](../../semantic-representation/RT-05/RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md), [RT-03 Core Language Semantics](../../language-design/RT-03/CORE-LANGUAGE-SEMANTICS.md), [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md), [Semantic Dependency Index](../../semantic-representation/RT-06/SEMANTIC-DEPENDENCY-INDEX.md), and [Package Manifest and Identity](../../packages-and-ecosystem/RT-12/PACKAGE-MANIFEST-AND-IDENTITY.md).

## 2. Identity dimensions that must not be conflated

| Dimension | Question answered | Candidate representation |
|---|---|---|
| Semantic value identity | Which exact immutable semantic value is this? | Domain-separated Value/Content Hash |
| Logical continuity | Is this the continuing managed artifact across edits? | Stable Entity ID, scoped selector, or explicit lineage plus context |
| Occurrence state | Which value occupies which role/slot in which immutable context state? | OccurrenceStateHash |
| Current selection | Which value/occurrence is selected in this accepted project state? | Snapshot-scoped selection mapping |
| Historical relation | How did values/occurrences evolve, split, merge, or move? | Typed immutable lineage/provenance edges |
| Human navigation | What label should a person or LLM see? | Alias, generated handle, source location |
| Conformance identity | Which operation contract and admissibility predicate are required? | `OpHash` and `CCHash` |
| Concrete implementation identity | Which exact implementation artifact is pinned? | `ImplHash` |
| Discovery result identity | Which finite set did a particular search return? | Optional `CandidateSetHash` |
| Verification/evidence identity | Which exact claim, inputs, assumptions, and verifier are evidenced? | Separate evidence identity/digest |
| Package identity | Which logical package contents or physical archive are identified? | Package Content Root, Index Logical Hash, Archive Hash |
| Git identity | Which physical repository object/tree/commit is identified? | Git blob/tree/commit OID |

A hash is not automatically an identity for every dimension. In particular, a hash of an immutable state does not answer which later state continues it.

## 3. Candidate architectures

### A. Stable Entity ID + Content Hash (Study 05)

- Stable opaque ID identifies a logical entity across edits.
- Content Hash identifies one exact immutable state.
- Aliases and paths are mutable presentation/lookup bindings, not identity.
- Snapshot state selects the current immutable version for each logical entity.

**Strength:** continuity across ordinary edits, renames, and moves is explicit and straightforward to address.

**Cost/risk:** allocation, import, fork, copy, duplicate-ID reconciliation, and split/merge semantics need governance. Two entities with identical values must retain distinct logical IDs where independent lifecycle is intended.

### B. Content-addressed values + explicit lineage/selection (Studies 06–07)

- Immutable semantic values are addressed only by canonical content and hash-relevant dependencies.
- Equal canonical values can be deduplicated.
- Provenance and lineage are separate from semantic value identity.
- Current state is selected by a project snapshot, branch, or contextual slot mapping.
- Explicit many-to-many lineage records continuity decisions.

**Strength:** immutable values, deduplication, branching, and historical preservation have a simple model without a global permanent entity ID.

**Cost/risk:** the system must not infer a successor from content, names, paths, or source-specification references. Independent lifecycle requires a selector or explicit occurrence/slot context.

### C. Content-addressed values + optional occurrence state and scoped slot (Study 08)

- ValueHash identifies reusable immutable semantic content.
- OccurrenceStateHash identifies one immutable value-in-context state.
- Snapshot mapping selects current values/occurrences.
- Optional scoped SlotKey provides continuity only for independently managed slots.
- Lineage records moves, splits, merges, and accepted continuation.

**Strength:** distinguishes reusable values from independently governed uses, while avoiding a global ID by default.

**Cost/risk:** slot scope and lifecycle become explicit identity design. A slot key that survives arbitrary edits is a scoped stable identity in substance and must be named as such.

These alternatives are not entirely mutually exclusive. Architecture C is a more explicit content-only refinement; a Stable Entity ID could still be used for selected entity kinds or scopes if later requirements justify it.

## 4. Scenario comparison

| Scenario | Stable ID + Content Hash | Content-only + lineage/selection | Value + occurrence + snapshot slot |
|---|---|---|---|
| Rename of a display alias | Stable ID unchanged; alias changes | Value hash unchanged; selection unchanged unless name is semantic | Value and slot remain unchanged if alias-only |
| Rename of an externally observable API name | ID remains; interface state/hash changes | New value hash if external name is semantic | New value hash; slot continuity is an explicit decision |
| Two identical values, one shared lifecycle | Two IDs are possible but may be unnecessary | One deduplicated value | One value; one or multiple occurrences as policy requires |
| Two identical values, independent ownership/evolution | Distinct Stable IDs | Requires distinct selectors/lineage contexts | Distinct slots/occurrences referencing the same value |
| Edit one of two identical uses | Update selected state under one ID | New value plus explicit successor selection | New occurrence state in one slot; other slot unchanged |
| Move between modules/parents | ID naturally survives; scope/ownership rules still apply | New snapshot selection and explicit moved/continues lineage | New occurrence state/slot mapping; continuity explicitly accepted or rejected |
| Parent changes, child semantics unchanged | Child ID and value can remain | Reuse same value; snapshot mapping may remain same | Do not include parent hash merely for containment; keep same occurrence if context semantics unchanged |
| One requirement splits into two | Explicit lineage from old entity to zero/many successors | Many-to-many lineage; source spec is not a unique identity | Slot mapping and lineage decide whether one or two occurrences continue |
| Two requirements merge | Multiple IDs may map to one successor via explicit merge | Many-to-one lineage | One or more slots may be replaced by a merged occurrence |
| Same requirement produces multiple artifacts of same kind | Distinct IDs distinguish artifacts | Requires explicit role plus selector/occurrence; spec hash alone is insufficient | Distinct semantic slot declarations or explicit local discriminators |
| Two branches edit the same starting state | Same ID, divergent immutable versions; merge by ID and state | Exact value hashes and snapshot roots; merge needs selection/lineage context | Same snapshot slot maps to competing occurrence states; conflict or explicit merge |
| Both branches produce identical canonical result | Same ID/state may converge | Same value hash deduplicates; proposal history remains separate | Same value/occurrence state may deduplicate if all occurrence inputs match |
| Delete then recreate similar content | New ID or explicit resurrection policy | New value may equal old value; lineage must not be inferred | New slot/occurrence or explicit restoration decision |
| Call-site reorder/extraction/inlining | ID continuity does not itself solve call-site matching | Needs scoped call-site selector/lineage | Needs explicit call-site slot or snapshot mapping; ordinal/path is unsafe |
| Recursive/mutually recursive declarations | Stable IDs can break reference cycles, but hash design remains necessary | Hash-relevant DAG or explicit SCC/group canonicalization | Same hash-cycle constraint; occurrence hashing must not introduce root self-reference |
| Change in type/effect/observable semantics | Content state changes if fields are represented correctly | Value hash changes if canonical semantic projection includes it | Value hash changes; occurrence selector may remain |
| Change in non-semantic provenance/evidence | Entity ID/state may remain; evidence version changes | Value hash remains; provenance/evidence changes separately | Value/occurrence hash remains unless context itself is semantically relevant |

## 5. Findings from the studies

The recursive identity fixture compares two group encodings. Both make recursive members and their exact callers depend on one group version. Keyed members retain distinct addresses under symmetry. Structural addressing can deduplicate symmetric members, so separately managed uses still need their own selectors. [RT-05 recursive identity](../../semantic-representation/RT-05/RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)

### 5.1 Rename and move are not the same operation

A presentation rename must not alter semantic value identity. An externally observable name (exported symbol, protocol field, CLI command, route, etc.) is part of the relevant interface semantics and may change the operation's semantic identity.

Movement changes context or ownership, but does not by itself decide whether lifecycle continuity is preserved. That decision must be represented explicitly.

### 5.2 Equal values do not imply equal managed occurrences

Deduplication is a storage/value property. Ownership, authorization, lifecycle, and independent evolution are contextual properties. The graph must allow two slots/occurrences to reference one value without pretending that the two occurrences are the same.

Conversely, do not create an occurrence object for every value unless the domain requires independent contextual lifecycle or governance.

### 5.3 Specification anchors are provenance, not universal identity

One requirement can produce many artifacts; one artifact can satisfy multiple requirements; requirements and artifacts can split or merge. A source-specification hash cannot be a universal one-to-one entity key.

### 5.4 OccurrenceStateHash is an address, not a continuity selector

The Study 08 formula `H(ValueHash, ContextStateHash, Role, SlotDescriptor)` identifies one immutable contextual state. If an input changes, the hash changes. To follow a managed occurrence across states, the model still needs a scoped slot, snapshot mapping, or explicit lineage decision.

### 5.5 Call-site identity is a separate unresolved problem

A caller migration decision is per call site (RT-20). A call-site ID cannot be assumed stable merely because it is present in a declaration. Reordering, extraction, inlining, duplication, and generated code require a defined matching/selector policy. Names, source offsets, list ordinals, and structural similarity must not silently establish continuity.

### 5.6 Semantic profile constrains hash contents

RT-03 has not selected a language semantic profile or complete observable-behavior model. Therefore, current structural equality and prototype hashes cannot be described as full behavioral equivalence. Before freezing canonical semantic fields, RT-03 and the relevant RT-04 type/effect/ownership model must establish which distinctions are observable and identity-bearing.

## 6. Typed hash vocabulary from the Draft Glossary

The [Draft Glossary](../../../draft/GLOSSARY.md) proposes distinct typed identities:

- `OpHash`: exact operation semantics and contract-visible call target.
- `ImplHash`: exact concrete implementation and its hash-relevant dependencies.
- `CCHash`: conformance-class definition (operation plus constraints/criteria), not a discovered implementation list.
- `CandidateSetHash`: optional identity of a finite search result, not of the conformance class.
- Conformance evidence identity: evidence bound to exact implementation, class, assumptions, and tool context.

These must not be collapsed into a generic ValueHash or confused with package roots, Git OIDs, action/verification keys, or evidence digests. The glossary is still a terminology proposal; canonical preimages, domain separation, and normative substitution rules remain open.

The exact role of a generic ValueHash relative to `OpHash` and `ImplHash` must be made explicit in the eventual typed schema. A plausible direction is that the glossary's typed hashes are domain-separated identities for specific semantic object kinds, but this record does not yet assert that as the final encoding contract.

## 7. Current prototype implications

The current semantic graph prototype is a narrow experiment, not a decision:

- It hashes object kind, normalized payload, and sorted explicitly hash-relevant dependencies.
- `declaration_id` currently participates in normalized payload and therefore affects the value hash. This is not reconciled with either architecture.
- `call_site_id` and `target_id` also contribute to the current payload/edge identity, but their stability across edits and source transformations is not established.
- Snapshot selection keys are explicit in the prototype; this is compatible with the content-only prototype boundary, but does not prove they are stable cross-snapshot identity.
- The current merge routine merges selection mappings, not complete SPG objects or call-site graphs.

Do not remove identity-bearing fields from the prototype merely to make it match one candidate architecture. First add tests that expose their current effects, then change the schema only with an explicit decision and migration plan.

## 8. Provisional recommendation for the next prototype

Use a deliberately bounded hybrid interface:

1. Immutable semantic values addressed by exact, domain-separated content hashes.
2. Snapshot-scoped explicit selection keys mapping to exact value hashes.
3. Separate typed lineage/provenance records, supporting many-to-many split, merge, move, and supersession.
4. Optional occurrence-state records only where independent lifecycle, ownership, or governance is needed.
5. Optional scoped slot keys only where snapshot-local selection is insufficient; document them as scoped identity.
6. Exact call-site references and target hashes, with no inferred continuity when the selector is ambiguous.
7. Typed operation, implementation, conformance-class, candidate-set, and evidence identities kept distinct per the Draft Glossary.
8. No global Stable Entity ID requirement in the prototype interface, but no prohibition on adopting one later for a proven use case.

This recommendation is an experimental boundary, not a final choice between Study 05 and content-only identity. It keeps the prototype testable while avoiding heuristics that would conceal the unresolved identity decision.

## 9. Decision gates before a normative choice

The RT-05 fixture comparison covers alias and exported-name edits, independently selected equal values, cross-scope moves, context changes, split/merge, slot reuse, and call-site reorder. The follow-on experiment checks exact binding transfer during extraction, finite unary inlining, and stale evidence across changed Snapshot parents. Selection merge coverage remains limited to explicit keys. Authentic endpoint evidence, source correspondence, and import/merge round trips remain open. [Identity lifecycle experiment](../../semantic-representation/RT-05/RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) · [Call site refactoring experiment](../../semantic-representation/RT-05/RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md)

The identity architecture must remain open until the following are completed:

1. **Scenario coverage:** executable tests for alias rename, external-name change, identical values with shared and independent lifecycle, move, parent edit, split, merge, branch conflict, deletion/recreation, call-site transformations, and duplicate slot descriptors.
2. **RT-03/RT-04 reconciliation:** define the initial observable semantic fragment and determine which type, effect, ownership, and environment fields belong in operation and implementation identity.
3. **Call-site selector contract:** specify identity scope and continuity under reorder, extraction, inlining, duplication, and generated code.
4. **Lineage contract:** define allowed relation kinds, cardinality, provenance, branch scope, and ambiguity behavior.
5. **Snapshot-root contract:** decide whether parent roots are semantic state, separate history metadata, or separate digests; define mapping revision participation.
6. **Hash-envelope contract:** canonical typed encoding, algorithm tags, domain separation, schema versioning, hash agility, and adversarial vectors.
7. **Glossary reconciliation:** define the exact relationship between generic ValueHash and typed `OpHash`, `ImplHash`, `CCHash`, `CandidateSetHash`, and evidence identity.
8. **Trust/completeness gate:** integrate scoped reverse-reference evidence with RT-20 CIP and RT-24 merge, including trusted producer and observation coverage.
9. **Import/merge round trip:** prove that canonical repository representation reconstructs the same selected semantic state and mapping revision.

If any scenario requires a selector that survives arbitrary edits, the decision record must acknowledge that it has introduced a stable identity at the relevant scope, regardless of the chosen name.

## 10. References

- [Draft Glossary](../../../draft/GLOSSARY.md)
- [Study 05 — Name-Free Semantic Entities](../../semantic-representation/RT-05/RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md)
- [Study 06 — Content-Addressed Entity Identity](../../semantic-representation/RT-05/RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md)
- [Study 07 — Content-Only Identity Stress Tests](../../semantic-representation/RT-05/RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md)
- [Study 08 — Context-Derived Occurrence Addressing](../../semantic-representation/RT-05/RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md)
- [RT-03 — Core Language Semantics](../../language-design/RT-03/CORE-LANGUAGE-SEMANTICS.md)
- [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md)
- [Semantic Dependency Index](../../semantic-representation/RT-06/SEMANTIC-DEPENDENCY-INDEX.md)
- [RT-20 — Patch Planning and Hash Propagation](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)
- [Package Manifest and Content Identity](../../packages-and-ecosystem/RT-12/PACKAGE-MANIFEST-AND-IDENTITY.md)


## RT-04 dependency — identity decision remains gated

The comparative [RT-04 type/effect/ownership/capability report](../../language-design/RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) identifies additional semantic distinctions that may affect operation-contract, implementation, conformance-class, and evidence identities: public type/refinement contracts, effect declarations and handlers, error/cancellation outcomes, resource protocols, capability requirements, and concurrency guarantees. These are candidate hash inputs or typed dependencies, not selected fields.

Do not finalize the identity model or hash-bearing payloads until RT-04 scenarios validate which distinctions are externally observable, which are contract-level versus implementation-level, and how transitive effects/ownership/protocol dependencies are discovered. RT-04 does not resolve Stable Entity ID versus content-addressed values with explicit lineage/selection.

## Public-interface integration (2026-11-24; proposed)

Add public-interface discriminator cases: public rename versus private presentation rename, rename retaining an explicit alias, name reuse with different lineage, same public name with changed contract, same OpHash with different compatible provider, group split/merge with preserved member operations, and two branches publishing conflicting names or providers. Test alternatives A/B/C without presuming that stable ID and name are the same, or that a new independent interface hash is necessary. A behaviorally breaking new revision cannot silently replace an old pin.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
