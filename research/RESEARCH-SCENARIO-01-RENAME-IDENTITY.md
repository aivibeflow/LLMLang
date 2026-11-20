# Scenario Study 01: Rename Without Losing Entity Identity

**Date:** 2026-11-16  
**Status:** Research result / proposed design, not an accepted LLMLang decision  
**Scope:** Stable identity, names, graph references, content hashes, source bindings, and rename change sets

## 1. Question

How should LLMLang rename a semantic entity—such as a type, operation, module, field, or public API symbol—without treating it as a new entity, losing references, or incorrectly reusing stale verification results?

The key distinction is:

- **Identity:** which logical entity this is.
- **Name:** how the entity is referred to in a particular namespace or view.
- **State:** the exact semantic contents of the entity at a point in history.

A rename should normally preserve identity, while producing a new immutable semantic state.

## 2. Findings from related projects

### 2.1 DSP CodeGen: explicit UID independent of path

DSP CodeGen states that entity identity is a UID and that the path is an attribute, not identity; entities therefore survive path renames. It also binds code regions to graph entities using explicit `@dsp <uid>` markers. Its CLI exposes `move-entity`, `move-to-toc`, and `diff` operations.

This is the clearest directly documented precedent for separating graph identity from location/name. It also demonstrates a practical bridge between a persistent graph node and source code.

Important limitation: the documented UID rule does not, by itself, define how a language-level symbol rename updates every reference, namespace, import, generated artifact, or external API. The public graph primarily models modules and public/shared functions and types; private function bodies are not graph entities.

Source: [DSP CodeGen README](https://github.com/Loqira-Labs/dsp-codegen) (reviewed 2026-11-16).

### 2.2 Atlas: deterministic IDs derived from structural coordinates

Atlas documents identifiers such as:

```text
SymbolId = blake3(file_id + language + symbol_path + kind + stable discriminator)
```

It separately uses content-hash-based dirty-file detection and a persistent semantic index.

This gives deterministic IDs without asking an LLM to invent identity. However, because the documented SymbolId derivation includes file identity and symbol path, a rename or move can change the derivation inputs. The available documentation does not establish a universal identity-preserving rename protocol for all symbol kinds.

Lesson: deterministic derivation and identity persistence are different guarantees. A deterministic ID can still be location-sensitive.

Source: [Atlas architecture](https://github.com/LordCasser/atlas/blob/main/docs/architecture.md) and [Atlas repository](https://github.com/LordCasser/atlas) (reviewed 2026-11-16).

### 2.3 Edict: structural comparison can mistake a rename for delete + add

The source-level review recorded in `RESEARCH-DEEP-COMPARISON.md` found that Edict's structural diff compares definitions by name. A rename can therefore appear as one removed definition and one added definition unless a separate identity mapping is supplied.

This is a useful warning: structural hashing and diffing do not solve identity by themselves. If names are the matching key, rename detection becomes heuristic or requires an explicit mapping.

Source: [Edict repository](https://github.com/Sowiedu/Edict) and the source-level findings in this repository's `RESEARCH-DEEP-COMPARISON.md` (reviewed 2026-11-16).

### 2.4 linkly: node IDs and proposal semantics

linkly's Semantic IR uses node IDs and explicit references in a flat node table. Its agent protocol separates proposing a change from mutating the accepted IR; proposals are reviewed before merge. Its proposal-intent design is relevant to expressing graph operations rather than relying on textual replacement.

The inspected material does not establish that every node ID is guaranteed to survive every rename or move. That lifecycle rule must not be inferred from the existence of node IDs alone.

Sources: [linkly repository](https://github.com/choiyounggi/linkly), [RFC-0010 Proposal Intent](https://github.com/choiyounggi/linkly/blob/main/rfcs/0010-proposal-intent.md) (reviewed 2026-11-16).

## 3. LLMLang baseline

The current LLMLang concept already distinguishes:

- Stable ID — identifies the logical entity across its lifetime.
- Content Hash — identifies one exact immutable semantic state.
- canonical semantic content and hash-relevant dependencies — inputs to the content hash.
- typed graph edges — references between semantic entities.
- Specification, Design, and Implementation layers — independently existing semantic layers.

The concept also states that renaming or changing an entity does not change its Stable ID, while a change to canonical semantic content or hash-relevant dependencies creates a new Content Hash.

Therefore, the high-level answer is already implied by the current concept. What is missing is an operational rename protocol: how to express it, validate it, propagate it, handle ambiguity, and preserve compatibility.

## 4. Proposed semantic model

### 4.1 Separate four notions

A semantic entity should not have one overloaded `name` field. At minimum, distinguish:

| Concept | Meaning | Example |
|---|---|---|
| Stable ID | Persistent identity | `ent_01J...` |
| Declared name | Identifier in a language namespace | `CustomerAccount` |
| Qualified name | Namespace-qualified lookup path | `billing::CustomerAccount` |
| Source binding/location | Where a source representation currently binds the entity | `src/account.llm:12` |

A display label or documentation title may be a fifth, non-semantic property.

The Stable ID must not be derived solely from the current name, qualified name, file path, or source range. Otherwise, a rename or move can change identity.

### 4.2 Rename operation

A rename should be a first-class typed graph operation, not an LLM-generated text replacement.

Illustrative operation:

```text
RenameEntity {
    target: StableID("type_customer_account"),
    expected_content_hash: "sha256:old...",
    namespace: "billing",
    old_name: "CustomerAccount",
    new_name: "ClientAccount",
    reference_policy: UpdateResolvedReferences,
    compatibility: PreserveAliasUntil("release-3")
}
```

This is illustrative syntax, not a proposed final API.

The operation must fail if:
- the target Stable ID does not exist;
- the expected hash is stale;
- the old name no longer resolves to that entity in the specified namespace;
- the new name collides with another declaration;
- required reference updates cannot be resolved unambiguously;
- a policy forbids the requested compatibility behavior.

### 4.3 Identity and hash behavior

For a normal semantic rename:

- Stable ID remains unchanged.
- A new immutable entity state is created.
- Content Hash changes if the declared language-level name is part of canonical semantic content.
- References stored by Stable ID remain references to the same entity.
- Name-resolution indexes and generated source views are updated.
- Any hash-relevant parent/root whose committed content or dependency projection changed receives a new hash.
- Unaffected graph branches retain their hashes.

A display-only label change may be excluded from the semantic hash if it is explicitly classified as presentation metadata. A language-level identifier must not be excluded merely to avoid invalidation: names can affect lookup, overload resolution, reflection, serialization, ABI, and external callers.

### 4.4 References must be semantic, not textual

Internal graph references should target Stable IDs, not repeat names as their identity.

When rendering or compiling source, the implementation resolves the Stable ID to the current name in the relevant namespace. A rename then changes the rendered identifier without changing the logical edge.

Where source code is user-authored or externally maintained, the system needs an explicit binding record from source occurrence to Stable ID. A text match is not sufficient evidence that two occurrences refer to the same entity.

### 4.5 Rename is layer-aware

The same logical entity may have representations in more than one SPG layer:

- Specification: requirement terminology or a named domain concept.
- Design: component, interface, or architectural role.
- Implementation: type, function, field, module, or local symbol.

These are not automatically one entity merely because their names match. Each layer can have its own Stable ID and explicit correspondence edges.

A rename in one layer must not silently rename all similarly named entities in other layers. The Change Set must specify which entities are renamed and which links are merely updated or re-evaluated.

## 5. Rename transaction and Change Set

A safe rename should be proposed as one atomic Change Set with explicit effects:

1. Identify the target by Stable ID and expected Content Hash.
2. Validate namespace and collision constraints.
3. Change the declared name.
4. Update resolved internal references and import/export declarations.
5. Update source bindings or generate a source patch.
6. Recompute affected semantic hashes.
7. Run impact analysis over reverse dependencies.
8. Re-run name resolution, type checking, and other required checks.
9. Re-evaluate compatibility obligations for public interfaces.
10. Produce a reviewable diff and evidence report.
11. Require approval when project policy or the change's compatibility impact requires it.
12. Commit the accepted snapshot atomically.

A partial application must not leave a graph where some references point to the old name and others to the new name unless the language explicitly supports both names during a migration period.

## 6. Compatibility policy

A rename is not always behavior-preserving from the perspective of external consumers.

Three policies should be distinguishable:

| Policy | Meaning | Typical use |
|---|---|---|
| Internal rename | Update all project-controlled references; no old-name support | Private implementation symbol |
| Alias/deprecation | Keep old name as an alias for a declared period | Public API migration |
| Breaking rename | Remove old name and record compatibility break | Major interface change |

The compatibility policy must be explicit. The engine must not infer that a rename is safe merely because internal references compile.

An alias is a distinct semantic declaration or binding that resolves to the same target Stable ID; it should not create a second entity identity accidentally. Deprecation metadata and removal deadlines should be explicit.

## 7. Ambiguous identity and legacy import

When importing an existing codebase, LLMLang may not know whether a removed declaration and a newly added declaration are a rename or two unrelated entities.

The engine should distinguish:

- **Certain identity:** an existing Stable ID or explicit source binding proves continuity.
- **Strong candidate:** structural similarity suggests a rename, but does not prove it.
- **Ambiguous:** multiple possible matches or insufficient evidence.
- **New entity / deletion:** no continuity claim is made.

Only the first case should be automatically treated as a confirmed identity-preserving rename. A strong candidate can be presented as a proposal for human/agent review. Ambiguity must not be silently resolved by an LLM guess.

This avoids false continuity, which could incorrectly transfer approvals, proofs, ownership, or security policy to a different entity.

## 8. Verification and cache consequences

A rename may preserve runtime behavior but still invalidate some analyses.

Expected treatment:

- Syntax/name-resolution results: invalidate for affected namespaces and references.
- Type checking: re-run for affected declarations and dependents; reuse only where exact semantic inputs are unchanged.
- Contract proofs: reuse only if the proof's exact inputs are unchanged under the proof's declared equivalence model. A changed symbol name in a proof context may or may not be irrelevant; this must be explicit.
- Tests: test source may need rewriting; execution results can be reused only if the executable/test inputs and environment identity remain exact.
- API compatibility checks: re-run for exported names and aliases.
- Documentation indexes and search indexes: update affected entries.

A Stable ID is not a cache key. A Content Hash is not automatically a sufficient cache key either: a verification result must also commit to verifier version, options, assumptions, toolchain/environment identity, and every other declared input.

## 9. Required invariants

The following are proposed invariants for a future RFC:

1. A confirmed rename preserves the target Stable ID.
2. A semantic name change creates a new immutable state and a new Content Hash.
3. Stable IDs are not derived solely from mutable names or locations.
4. Internal semantic references resolve by identity, not by textual spelling.
5. Every source occurrence used as evidence has an explicit or reproducibly derived binding to a semantic entity.
6. A rename cannot silently bind to a different entity because a name was reused.
7. Name collisions and stale expected hashes reject the Change Set before mutation.
8. A Change Set either applies all required graph/source binding changes or applies none.
9. Public compatibility effects are explicit and independently checked.
10. Approval, verification, and provenance are not transferred to a different entity merely because it resembles the renamed entity.
11. Heuristic rename detection is advisory until confirmed.
12. Cache reuse is based on exact declared inputs, not Stable ID alone.

## 10. Open questions

1. Are Stable IDs globally unique within a project, within a layer, or within a repository namespace?
2. Should aliases be modeled as first-class entities, name bindings, or typed edges?
3. Does a language-level rename always change the entity's own Content Hash, or should names be separate hash-committed bindings? The choice affects hash granularity and cache invalidation.
4. Should the rename operation include all reference updates in one Change Set, or can some references remain unresolved with explicit migration diagnostics?
5. How should overload sets, shadowing, generic specialization, and macro-generated names be represented?
6. How are generated source bindings distinguished from manually maintained source bindings?
7. Which public API changes require explicit human approval, and which can pass under policy?
8. How should a rename across Specification/Design/Implementation correspondence links be reviewed when the names differ intentionally?

## 11. Preliminary conclusion

The current LLMLang Stable ID / Content Hash split is the right foundation, but it is not yet a complete rename design.

The most useful concrete precedent is DSP CodeGen's UID independent of path and explicit code marker. Atlas demonstrates the value of deterministic extraction and content-hash-based incremental indexing, while also illustrating why path-derived IDs need a separate identity-preservation mechanism. Edict is a warning that name-based structural diffing can reduce rename to delete-plus-add. linkly contributes a proposal/review boundary for graph mutations.

**Preliminary recommendation:** make rename a first-class, identity-targeted Change operation with an expected Content Hash, explicit namespace, collision checking, resolved-reference propagation, compatibility policy, and atomic Change Set semantics. Keep heuristic rename detection separate from confirmed identity continuity.

This recommendation is a research conclusion, not an accepted change to `LLMLang-CONCEPT.md`.

## Sources

- [DSP CodeGen README](https://github.com/Loqira-Labs/dsp-codegen)
- [Atlas architecture](https://github.com/LordCasser/atlas/blob/main/docs/architecture.md)
- [Atlas repository](https://github.com/LordCasser/atlas)
- [Edict repository](https://github.com/Sowiedu/Edict)
- [linkly repository](https://github.com/choiyounggi/linkly)
- [linkly RFC-0010: Proposal Intent](https://github.com/choiyounggi/linkly/blob/main/rfcs/0010-proposal-intent.md)
- LLMLang internal baseline: `LLMLang-CONCEPT.md`, `RFC-REQUEST-CHANGE.md`, `RFC-DEVELOPMENT-ENGINE.md`, `RESEARCH-DEEP-COMPARISON.md`
