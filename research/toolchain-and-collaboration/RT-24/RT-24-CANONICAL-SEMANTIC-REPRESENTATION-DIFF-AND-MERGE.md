# RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge

**Status:** Research proposal; candidate technical contract, not an accepted language or serialization decision  
**Date:** 2026-11-18  
**Priority:** P0  
**Depends on:** RT-03 (language semantics), Research Studies 05–08 (identity and occurrence alternatives), Semantic Dependency Index research, RT-19 (semantic API and snapshots), RT-20 (caller impact/hash propagation), RT-22 (repository/worktree contract), RT-23 (shared semantic state and synchronized commit). No standalone RT-05 specification currently exists in the repository.  
**Related:** [Git Representation and Semantic Merge](../RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md), [ADR-014](../../docs/adr/014-git-semantic-merge.md)

> This document narrows the next research and implementation boundary. It defines a candidate contract and deterministic algorithm shape, while leaving the final SPG schema, canonical byte encoding, hash envelope, and complete language semantics to their owning research and decisions. It does not accept ADR-014.

## 1. Purpose

Define a coherent contract for:

1. reconstructing the same semantic state from a Git repository representation;
2. comparing immutable semantic snapshots without confusing physical file changes with semantic changes;
3. merging three snapshots (base, ours, theirs) deterministically;
4. reporting ambiguity and invariant violations rather than silently choosing a side;
5. preserving RT-20 caller-migration and hash-propagation obligations;
6. producing a merge result that can be reconciled and committed under RT-22/RT-23.

The unit of correctness is the complete repository semantic state, not an individual file. File-level Git merge drivers may assist integration but cannot certify a repository-wide merge.

## 2. Scope and non-goals

**In scope:** repository representation properties; identity boundaries; typed semantic diff; three-way merge; conflict results and provenance; deterministic replay; separate mapping-revision merge; integration with RT-20 and RT-23.

**Out of scope:** final syntax/SPG schema/canonical bytes/hash algorithm (identity Studies 05–08 and SPG research own these); full language equivalence proofs; automatic LLM conflict resolution; production MCP schemas; Git object IDs as semantic identities; external databases as the only durable source of program meaning.

## 3. Terminology and state model

| Term | Meaning |
|---|---|
| Repository state | Git tree plus declared LLMLang source inventory and pinned inputs needed to interpret it |
| Semantic Snapshot | Immutable, validated SPG state with explicit roots and references |
| Semantic value | Immutable typed SPG value with canonical content and exact hash-relevant outgoing references |
| Value/Content Hash | Address of one exact immutable semantic value; exact hash envelope remains unresolved |
| Logical entity identity | Optional identity of a continuing conceptual entity; Stable Entity ID vs content-only model remains unresolved |
| Occurrence/selection key | Snapshot- or scope-relative selector identifying which value occupies a semantic slot; lifecycle rules remain unresolved |
| Lineage operation | Explicit relation between immutable values or occurrences (rename, move, split, merge, replacement, supersedes, etc.); never inferred from names or hashes alone |
| Mapping Revision | Immutable revision of external-interface mappings with its own identity and merge rules |
| Semantic diff | Typed, provenance-bearing description of changes between two snapshots |
| Merge candidate | Proposed result of merging base, ours, and theirs; not yet accepted or committed |
| Merge evidence | Inputs, policy/tool versions, decisions, validation, and provenance needed to audit/replay |

**Terminology dependency:** Before changing hash-bearing fields, identity boundaries, or merge matching rules, read the [Draft Glossary](../../draft/GLOSSARY.md). In particular, preserve the distinctions among `OpHash`, `ImplHash`, `CCHash`, optional `CandidateSetHash`, and conformance-evidence identity. These are typed identities for different objects, not interchangeable aliases for the generic Value/Content Hash. The glossary is a terminology proposal, not an accepted normative schema; unresolved canonical encodings and identity decisions remain open here.

A repository tree is not itself a Semantic Snapshot. Import must resolve the declared source inventory and dependencies, parse and normalize the representation, resolve references, and validate the complete graph. A tree that cannot be imported unambiguously is not a valid LLMLang merge input.

## 4. Repository representation contract

### 4.1 Authoritative and derived data

Git must contain enough canonical LLMLang source representation, manifests, and pinned dependency references to reconstruct committed semantic state, subject to availability of declared immutable external dependencies.

Local semantic databases, indexes, caches, watcher journals, and acceleration structures are derived and rebuildable. They must not be required to recover the meaning of committed code. The primary semantic source representation is textual and reviewable. Binary formats may be used for optional derived indexes/caches, not as the only representation of semantic source state.

### 4.2 Canonical import/export laws

Let Import(T, D, V) import repository tree T using dependency set D and language/schema tool version V; let Export(S, V) export snapshot S canonically. For the supported profile, establish:

1. **Structural round trip:** Import(Export(S, V), D, V) yields the same canonical typed SPG structure, selected values, and hash identities for the supported schema/profile. This is not a claim of full behavioral equivalence; RT-03 has not selected complete language semantics.
2. **Canonical export:** exporting the same snapshot with the same canonicalization version produces byte-identical output, independent of process, traversal order, and cache state.
3. **Import determinism:** identical tree bytes, dependency pins, and tool/schema versions produce the same semantic result or the same structured failure.
4. **Physical independence:** formatting, declaration order, and file placement do not alter semantic identity unless explicitly defined as semantic.
5. **No silent omission:** unsupported syntax, missing dependencies, duplicate identities, unresolved references, and incomplete inventory produce explicit errors.
6. **Versioned canonicalization:** schema/canonicalization changes are versioned; upgrades must not silently reinterpret old repositories.

The equality relation and canonical byte format must be specified by the owning identity/schema work before conformance is claimed.

### 4.3 Source inventory

The manifest must identify LLMLang source roots, schema/language version, and dependency/lock inputs needed to reconstruct semantic state. The exact format remains open. Import must distinguish LLMLang source, ordinary files, generated/derived files, external immutable dependencies, and optional cache/index payloads. No file is included or excluded solely by filename heuristic. An ambiguous inventory boundary blocks strong validation.

## 5. Identity boundaries

Keep distinct:

1. **Git object identity:** blob/tree/commit IDs for physical content and history.
2. **Semantic value identity:** exact content-derived address of one immutable typed value; hash algorithm and canonical encoding are not selected.
3. **Optional logical identity:** continuity of a conceptual entity across value versions, if the Stable Entity ID model is selected.
4. **Occurrence/selection identity:** snapshot- or scope-relative selection of a value in a role/slot; not interchangeable with value or logical identity.
5. **Lineage identity:** explicit immutable relations between values/occurrences, including many-to-many split/merge history.
6. **Snapshot identity:** identity of selected roots/slots and explicit resolution inputs; treatment of causal parents remains open.
7. **Mapping Revision identity:** identity of one immutable interface-mapping revision.
8. **Action/evidence identity:** identity of a computation over exact inputs, implementation, configuration, and environment.

Consequences:
- A move or formatting-only change may alter Git objects without changing semantic value hashes.
- A semantic edit or changed hash-relevant exact reference creates a new immutable value hash.
- A changed reference creates a new caller value only when that reference is in the caller's hash-relevant payload.
- Equal value hashes permit value deduplication but do not prove equal logical entity, occurrence, ownership, or governance identity.
- A merge commit is not a semantic identity.
- Snapshot identity cannot be inferred from a Git tree hash alone.
- Provenance and lineage are separate from value identity unless a reviewed semantic rule makes a field behaviorally relevant.
- Only the hash-relevant dependency relation must be a DAG for recursive Merkle hashing; the full SPG relation graph is not thereby required to be acyclic.

Studies 05–08 leave Stable Entity ID + Content Hash versus content-addressed values with explicit lineage/selection unresolved. RT-24 must not silently choose either model. For the current prototype, exact value hashes address immutable values and explicit snapshot selection keys establish which value occupies a slot. This is a prototype boundary, not a normative identity decision. See [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md).

## 6. Semantic diff contract

### 6.1 Inputs and output

SemanticDiff(A, B, policy, versions) compares two immutable snapshots and returns a deterministic typed change set. It records both snapshot identities, policy/canonicalization versions, and required resolution context. A diff is not a textual patch and is not automatically applicable to an arbitrary third snapshot.

### 6.2 Required change classes

At minimum:
- entity_added, entity_removed, entity_updated;
- reference_added, reference_removed, reference_retargeted;
- lineage_declared (rename/move/split/merge/replacement, only when explicit);
- root_set_changed;
- dependency_pin_changed;
- mapping_revision_changed (reported in the separate mapping domain).

Each record identifies the exact immutable value and typed field/edge, before/after values or version references, the applicable occurrence/selection key or logical identity when defined, and source provenance. A reference retarget must not be collapsed into an undifferentiated value update: RT-20 requires call-site granularity. Matching changed values across snapshots requires the selected identity/lineage model; content-hash inequality alone does not establish that two values are versions of the same logical entity.

### 6.3 Diff invariants

- Deterministic ordering and stable machine-readable change IDs.
- Physical-only changes are distinguishable from semantic changes.
- Calls and other typed references retain per-call-site granularity.
- Deletion is distinct from replacement or lineage transfer.
- Root and dependency-pin changes are represented.
- Missing reverse-reference or source provenance information is an error, not an empty result.
- Equal semantic snapshots produce an empty semantic diff even if Git trees differ physically.
- A diff is bound to exact input snapshots; reuse elsewhere requires compatibility validation.

## 7. Three-way semantic merge contract

### 7.1 Inputs and result

SemanticMerge(Base, Ours, Theirs, Policy, Versions) consumes three immutable, fully imported snapshots with compatible schema and dependency context. It returns exactly one result class:

- **clean_candidate:** merge rules establish one result and validation evidence exists;
- **conflicted_candidate:** explicit decisions are required;
- **invalid_input:** an input cannot be trusted/imported/validated;
- **insufficient_context:** graph, dependency, reverse-reference, lineage, or mapping context is missing;
- **incompatible_versions:** schemas, canonicalization versions, or policies cannot be reconciled safely.

A candidate is not accepted state or a Git commit. RT-20 and RT-23 gates remain mandatory.

### 7.2 Deterministic procedure

1. **Pin inputs:** exact base/ours/theirs Snapshot IDs, Mapping Revision IDs, dependency pins, repository tree IDs, schema/canonicalization versions, merge policy, and engine build.
2. **Validate inputs:** import and validate all three complete states; reject duplicate identities, unresolved references, incomplete inventory, unsupported constructs, and invalid roots.
3. **Compute diffs:** D_ours = SemanticDiff(Base, Ours); D_theirs = SemanticDiff(Base, Theirs).
4. **Resolve identity/selection:** use the identity model explicitly selected by the schema. Until it is selected, the bounded prototype matches snapshot entries only by an explicit snapshot-scoped selection key and addresses values by exact content hash. Never infer continuity from path/name/content similarity alone.
5. **Combine independent changes:** compose disjoint semantic fields/edges only where typed constraints permit.
6. **Resolve same-subject changes:** apply the conflict matrix below; auto-merge only when one unique result follows.
7. **Validate whole graph:** rebuild and validate typed references, selected roots, contracts, dependency pins, and all applicable SPG invariants. Validate acyclicity of the hash-relevant relation separately; do not impose a DAG constraint on unrelated SPG relation families. A clean result also requires scoped dependency-completeness evidence for every safety-critical reverse-reference query.
8. **Run RT-20 impact analysis:** construct the complete Change Impact Plan (CIP) for call sites, caller versions, migrate/preserve/adapt/fork decisions, and hash propagation. Unresolved decisions block clean status.
9. **Merge mapping domain separately:** reconcile Interface Mapping Revisions under RT-23 revision/CAS rules. Mapping conflicts block acceptance.
10. **Canonicalize/export:** export deterministically, re-import the exact exported tree, and verify semantic round-trip equality.
11. **Emit evidence:** changes, conflicts, validation findings, CIP, mapping result, provenance, and all pinned input/tool identities.

No accepted immutable snapshot is mutated. The merge candidate is a new proposed state.

### 7.3 Initial conflict matrix

| Ours vs. theirs relative to base | Rule | Outcome |
|---|---|---|
| Disjoint entities, no cross-constraints | Combine | Auto-merge, then graph validation |
| Same entity, disjoint fields | Combine only if field merge laws and type constraints are defined | Otherwise conflict |
| Same field changed to same canonical value | Coalesce | Auto-merge |
| Same field changed to different values | No implicit winner | Conflict |
| One side unchanged, other updated | Take changed side, then validate graph | Usually clean |
| One side deletes, other unchanged | Delete, subject to root/reference checks | Usually clean |
| One side deletes, other updates | No implicit precedence | Conflict |
| Same identity added on both sides with identical content | Coalesce only if identity rules prove equivalence | Otherwise identity conflict |
| Same identity added with different content | No implicit winner | Conflict |
| Distinct additions | Combine, subject to graph checks | Usually clean |
| Same call-site selector is proven to identify the same scoped occurrence and is retargeted to the same callee version | Coalesce | Auto-merge |
| Same scoped call-site selector is retargeted to different callee versions | Per-call-site compatibility decision; no newest-wins rule | Conflict/CIP |
| Call-site continuity cannot be established across snapshots | Do not infer from source location, display name, or structural similarity | Identity/occurrence conflict |
| Rename/move with explicit shared lineage | Preserve identity if compatible | Conditional |
| Rename/move inferred only from path/name | Do not infer | Identity conflict |
| Split/merge/replacement without explicit lineage | Do not infer | Identity conflict |
| Dependency pin changed differently | No implicit version preference | Conflict |
| Incompatible root-set changes | Apply explicit root policy only | Otherwise conflict |

“Usually clean” describes only the local rule; it never bypasses whole-graph validation, RT-20, or mapping reconciliation.

### 7.4 Repository-wide correctness

Entity-level merge may be an internal optimization, but the externally visible result is repository-wide. A locally compatible change can invalidate references, contracts, call graphs, roots, or dependencies elsewhere. The first prototype may support a small declared SPG subset and must fail closed outside it. It must not claim whole-language correctness from isolated-file tests.

The closed-inventory fixture tests this boundary with a real Git merge tree. A historical value can make the store-level graph audit pass even when the tree cannot reconstruct the callee. Comparing the tree's declared source to the indexed snapshot also detects a caller omitted before both graph readers run. [Merged-tree source completeness](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md)

The closed-inventory fixture tests this boundary with a real Git merge tree. A historical value can make the store-level graph audit pass even when the tree cannot reconstruct the callee. Comparing the tree's declared source to the indexed snapshot also detects a caller omitted before both graph readers run. [Merged-tree source completeness](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md)

## 8. RT-20 caller migration and hash propagation

Merge must not assume that every caller migrates to the newest callee. For every affected call site, RT-20 records an evidence-backed decision:
- preserve the old immutable callee version;
- migrate to the new version;
- adapt through an explicit adapter;
- fork a caller/callee version for distinct consumer behavior;
- unresolved.

The coordinator supplies RT-20 with exact input/candidate snapshots, changed callee versions, typed call-site identities, complete supported reverse-reference closure (direct/indirect/dynamic/external/generated), contract-impact findings, candidate reference changes, and provenance.

RT-20 returns a complete CIP. A merge is not clean while call-site decisions, caller splits, planned mutations, or hash propagation remain unresolved. If CIP execution changes the semantic graph, rebuild and revalidate the candidate. A caller may preserve an old callee while another migrates; a shared caller may require multiple immutable versions. Hash propagation follows only approved rewrites and semantic changes, never indiscriminate caller rewriting.

## 9. Interface Mapping Revision merge

Interface mappings are a separate versioned domain, not ordinary immutable SPG entities.

- Treat base/ours/theirs Mapping Revisions as immutable inputs.
- Apply RT-23 parent revision, scope, content digest, CAS baseline, and ownership model.
- Combine disjoint mapping-key changes only when invariants prove independence.
- Different values for the same key are conflicts.
- Delete/update, ownership/scope changes, and incompatible target-interface changes are explicit conflicts unless a unique rule is documented.
- Produce a new immutable Mapping Revision; never overwrite an input.
- Bind its ID into candidate, validation evidence, and commit preparation.
- If mappings are unchanged, retain an explicitly selected compatible revision; never choose a process-global latest revision implicitly.

## 10. Conflict and provenance model

Each conflict is machine-readable and reviewable, containing:
- stable conflict ID and type;
- semantic entity/edge/field or mapping key;
- base/ours/theirs values or references;
- source provenance and explicit lineage evidence;
- affected roots, callers, contracts, and dependency pins where known;
- why no unique automatic result exists;
- permitted resolution actions and preconditions;
- decision actor/policy, rationale, and resulting change.

Minimum classes: identity/lineage ambiguity; update/update; delete/update; reference retarget; duplicate identity; missing reference; contract/constraint incompatibility; dependency-pin conflict; root-set conflict; mapping conflict; unsupported schema/construct; incomplete graph/reverse-reference context; inconsistent canonicalization.

Resolution creates a new candidate and evidence. It does not rewrite input snapshots or erase the original conflict.

## 11. Determinism, replay, and failure behavior

Identical pinned inputs, policy, and tool versions must produce the same canonical candidate or same ordered conflict/error result.

Evidence pins:
- base/ours/theirs Snapshot IDs and repository tree IDs;
- dependency and language/schema/canonicalization versions;
- merge policy and engine build;
- Mapping Revision inputs/result;
- semantic diffs and conflict records;
- RT-20 CIP and validation/audit evidence;
- canonical exported tree identity and round-trip result.

Any changed pinned input makes the prior result stale. Fail closed on missing data, unsupported semantics, ambiguous identity, incomplete reverse references, stale baselines, or unknown schema versions. Unknown is not a clean merge.

## 12. Git and Toolchain integration

The semantic engine is VCS-independent. The Git adapter obtains explicit base/ours/theirs repository trees and invokes repository-level merge. A per-file custom driver may assist but cannot certify the whole SPG, rely on undocumented ambient worktree state, or perform irreversible semantic mutations during speculative Git callbacks.

For merge, rebase, and cherry-pick, the coordinator pins exact Git operation inputs and resulting tree. Git's textual result is an input to semantic import/reconciliation, not proof of semantic success.

RT-23 governs materialization and commit:
- materialize canonical representation for the exact candidate snapshot and mapping revision;
- preserve only explicitly selected regular-file changes;
- verify the resulting tree by re-import/round trip;
- run mandatory checks on that exact combined tree;
- create one commit with expected-old-HEAD/ref checks;
- record commit OID ↔ snapshot, mapping revision, CIP, and evidence;
- recover idempotently after timeout/crash without duplicate commits.

A Git merge commit is not a completed LLMLang semantic merge until these conditions hold.

## 13. Prototype and test programme

The first prototype uses a deliberately small declared schema: stable IDs, typed references, roots, and a minimal contract/call relation. It must state its supported subset and make no full-SPG claim.

**Representation/diff tests**
1. Import/export round trip preserves roots and version identities.
2. Repeated export is byte-identical.
3. Formatting, declaration order, and file moves do not alter semantic identity.
4. Semantic edits alter the appropriate version identity under the selected hash envelope.
5. Reference retarget is represented at call-site granularity.
6. Add/remove/update/root/dependency-pin changes are distinct.
7. Unsupported syntax, duplicate IDs, missing references, and incomplete inventory fail closed.
8. Diff is deterministic and bound to exact snapshots.

**Merge tests**
1. Independent additions; disjoint entity updates.
2. Same field changed to same value and to different values.
3. Disjoint field updates within one entity.
4. Delete/unchanged and delete/update.
5. Same-identity add/add with equal and unequal content.
6. Cross-file reference changes and dangling-reference detection.
7. Root-set and dependency-pin conflicts.
8. Explicit rename/move lineage and ambiguous rename.
9. Explicit split/merge lineage and absent lineage.
10. Two call sites in one caller requiring different callee versions.
11. Different callers preserving/migrating independently.
12. Shared caller requiring a fork.
13. Incomplete reverse-reference index blocks clean status.
14. Mapping disjoint-key merge, same-key conflict, stale CAS.
15. Deterministic replay and tool/policy version mismatch.
16. Rebase/cherry-pick produce correctly pinned evidence.

**Git/commit/recovery tests**
1. Real temporary repository with LLMLang and ordinary files.
2. Clean textual merge but invalid SPG is rejected.
3. File-level driver success followed by repository validation failure.
4. Candidate export/import round trip.
5. CIP mutation invalidates and rebuilds candidate.
6. Successful merge materializes exact semantic state and selected ordinary files in one commit.
7. Unselected user changes are not staged.
8. Pre-commit failure creates no commit and retains resumable candidate.
9. Crash after Git commit but before Toolchain finalization is recovered idempotently.
10. Timeout/lost response is inspected by durable operation identity before retry.
11. Clone reconstructs committed semantic roots and mapping revision without the original local database.

Passing these tests validates only the tested subset and invariants, not all LLMLang merge semantics.

## 14. Implementation sequence and gates

| Step | Deliverable | Gate |
|---|---|---|
| 0 | Reconcile identity Studies 05–08 with RT-03/SPG assumptions | Prototype fields and unresolved identity/schema assumptions are explicit; no unsupported identity choice is made |
| 1 | Minimal canonical text representation and importer/exporter | Round-trip, determinism, physical-independence, fail-closed tests pass |
| 2 | Semantic diff | Typed per-edge changes, exact input binding, deterministic results |
| 3 | Pure three-way merge core | Conflict matrix and graph validation pass on declared subset |
| 4 | RT-20 integration | Complete CIP and per-call-site decisions gate clean candidate |
| 5 | Mapping Revision merge | CAS and mapping conflicts independently tested |
| 6 | Git repository coordinator | Explicit base/ours/theirs trees; real repository tests |
| 7 | RT-23 commit/recovery integration | Exact-tree synchronized commit and crash/timeout tests pass |
| 8 | Benchmark and architecture review | Measure import, diff, merge, validation, and reconstruction separately |

Do not begin with a production Git merge driver. The pure representation/diff/merge core and test corpus are prerequisites. A narrow driver prototype may follow once repository-level input acquisition is explicit.

## 15. Open decisions

1. Stable Entity ID + Content Hash versus content-addressed values with explicit lineage/selection (Studies 05–08); no model is selected.
2. Exact SPG entity/edge schema, relation families, semantic/hash roles, and call-site identity lifecycle.
3. Occurrence/selection key scope and lifecycle; whether identical values may be shared across independent occurrences.
4. Canonical textual representation, manifest/lock division, canonical typed encoding, algorithm-tagged hash envelope, and canonicalization versioning.
5. Hash-relevant fields and whether recursive constructs need a representation compatible with an acyclic hash-relevant relation.
6. Structural SPG equality versus behavioral equivalence; RT-03 has not selected a complete semantic profile.
7. Snapshot-root construction and whether causal parent roots belong to semantic state or separate history/evidence.
8. Scoped dependency-completeness evidence for static, indirect, dynamic, generated, external, and unresolved references.
9. Merge policy for contracts, roots, dependency pins, and sparse/partial repository states.
10. External dependency retrieval and verification during clone/recovery.
11. Provenance serialized in source versus retained as commit/toolchain evidence.
12. Division between Git tree acquisition, repository coordinator, merge driver, and mergetool.
13. Mapping revision scope/ownership and detailed merge policy.

Resolve each through its owning research/ADR; this document records safe behavior while decisions remain open.

## 16. Exit criteria

This track may move from design to a scoped prototype only when:
- the supported SPG subset and identity assumptions are explicit;
- canonical import/export laws are executable tests;
- semantic diff has stable typed outputs and per-call-site provenance;
- three-way conflict rules are deterministic for the subset;
- whole-graph validation and fail-closed behavior are demonstrated;
- RT-20 CIP is a mandatory merge gate;
- mapping revisions are handled separately under RT-23;
- candidate export/import is verified;
- Git operation inputs and RT-23 commit/recovery boundaries are explicit.

Passing this gate permits a scoped prototype; it does not accept ADR-014 or prove production readiness.

## References

- [Git Representation and Semantic Merge](../RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md)
- [ADR-014 — Git repository representation and semantic merge](../../docs/adr/014-git-semantic-merge.md)
- [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md)
- [Study 05 — Name-Free Semantic Entities](../RT-05/RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md)
- [Study 06 — Content-Addressed Entity Identity](../RT-05/RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md)
- [Study 07 — Content-Only Identity Stress Tests](../RT-05/RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md)
- [Study 08 — Context-Derived Occurrence Addressing](../RT-05/RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md)
- [Semantic Dependency Index](../RT-06/SEMANTIC-DEPENDENCY-INDEX.md)
- [Core Language Semantics / RT-03](../RT-03/CORE-LANGUAGE-SEMANTICS.md)
- [RT-19 — Toolchain Server and Semantic Development API](../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md)
- [RT-20 — LLM Patch Planning and Hash Propagation](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)
- [RT-22 — Git Repository and Worktree MCP Surface](../RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md)
- [RT-23 — Single-Instance Toolchain and Multi-Worktree File Views](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md)

## Public-interface integration (2026-11-24; proposed)

Add distinct diff/conflict classes for public name/alias, operation revision and contract, provider binding, and external symbol mapping. Identical final signatures do not resolve concurrent incompatible contract edits. Disjoint edits may combine into a stale certificate, ambiguous selection or duplicate public export; validate whole merged catalog/binding consistency, exact endpoints, and required evidence before atomic publication. Preserve pinned old revisions and explicit migration decisions. The existing interface mapping experiment is a scoped symbol/signature model, not proof of this richer semantic admission.

Related: [Public interfaces and verified contract refinement](../RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
