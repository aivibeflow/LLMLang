# Research Scenario 18: Requirement Evolution and Semantic Impact

**Status:** Research / design proposal  
**Date:** 2026-11-16  
**Scope:** Immutable Requirement IR revisions, typed semantic dependencies, impact closure, provenance-only changes, split/merge, concurrent edits, and verification invalidation.

## 1. Executive summary

Scenario 17 introduced a typed Requirement IR. Scenario 18 tests whether it can evolve inside LLMLang's content-addressed graph without reintroducing a global mutable requirement identity or invalidating unrelated parts of a project.

### Main recommendation

Represent requirement evolution using four distinct structures:

1. **Semantic value** — immutable typed requirement content, addressed by its content hash.
2. **Snapshot selection** — a snapshot-local key selecting one semantic value for one role or slot.
3. **Semantic dependency edges** — exact hash-relevant inputs used to derive clauses, contracts, tests, and verification records.
4. **Lineage/provenance relations** — separate contextual links such as supersedes, split_into, merged_from, clarifies, and rephrases.

A requirement edit creates a new semantic value. It does not mutate the old one. The candidate snapshot selects the new value. Only artifacts reachable through hash-relevant dependency edges are in the semantic impact closure. Provenance-only changes do not invalidate semantic values or verification records.

This is consistent with the earlier research on content-addressed values, snapshots, and separation of semantic state from provenance.

## 2. Research background

### 2.1 Requirements traceability and change impact

The SWEBOK guide describes requirements tracing as both backward recovery of sources and forward prediction of effects. It notes that traceability supports impact analysis and typically forms a directed graph connecting requirements, design, implementation, and tests. It also warns that trace information must be maintained as requirements evolve; stale traceability undermines impact analysis.

Research on formalizing trace relations argues that treating every trace as an undifferentiated link can produce an explosion of false-positive impacts. The semantics of the relation matters: a dependency, refinement, rationale, and verification link do not necessarily mean the same thing.

**Implication for LLMLang:** impact analysis must traverse typed relations with explicit semantics, not all graph edges indiscriminately.

### 2.2 Provenance is not semantic dependency

W3C PROV-O distinguishes entities, activities, and agents, and provides relations such as `wasDerivedFrom`, `wasGeneratedBy`, and `wasAttributedTo`. It describes provenance chains without requiring every provenance fact to become part of the content of the derived entity.

**Implication for LLMLang:** a source citation, author attribution, clarification history, or wording note should not automatically alter the semantic hash of a requirement. If a clarification changes the actual interpretation, that is a semantic change and must create a new semantic value.

### 2.3 Immutable revisions and derivation

PROV-O's derivation vocabulary treats revision as the creation of a distinct derived entity. This fits the LLMLang rule that old semantic values remain immutable and new revisions receive new hashes. The provenance graph can say how the new value relates to the old one without making the old value mutable.

### 2.4 Incremental verification

The existing LLMLang verification-key experiment binds evidence to exact artifact identity, dependency closure, verifier, configuration, and assumptions. A requirement change that affects a contract or implementation must therefore change the corresponding verification identity. A provenance-only edit that does not change semantic inputs should not force re-verification.

## 3. Four kinds of evolution

These kinds must not be conflated.

### 3.1 Semantic change

Example: preferred-order tax rate changes from 1500 to 1200 basis points.

- New Requirement IR semantic value.
- New content hash.
- New snapshot selection for the preferred-tax slot.
- Dependent formal clause and caller contract must be re-derived.
- Tests and verification records that depend on the changed contract must be regenerated/recomputed.
- Standard-order requirement and generic `calculate_tax` contract remain unchanged if they do not depend on the changed policy.

### 3.2 Provenance-only change

Example: source citation is corrected, an author attribution is added, or a non-semantic explanation is rephrased while the confirmed rule remains exactly the same.

- Semantic value hash remains unchanged.
- Add or update contextual provenance relation.
- No semantic dependency closure changes.
- No verification invalidation is required solely due to this metadata change.

Important boundary: the system cannot infer that a wording change is semantically neutral merely because an LLM says so. The classification must be explicit and reviewable. If the clarification changes the meaning, create a new semantic value.

### 3.3 Structural change: split or merge

A requirement may be split into multiple smaller requirements, or multiple requirements may be merged.

- Each resulting semantic value has its own content hash.
- Snapshot selection keys are added/removed/changed.
- Lineage records express `split_into` or `merged_from`.
- Lineage is not itself a semantic dependency.
- Derived contracts and tests are recomputed according to their actual semantic inputs.

One source requirement can split into several new requirements; one new requirement can combine multiple sources. No one-to-one identity assumption is safe.

### 3.4 Concurrent change

Two branches may independently revise different requirement slots or the same slot.

- Disjoint slot edits can be merged structurally.
- Two different values proposed for the same slot are a conflict.
- A merge is a new immutable snapshot with both branch roots as parents.
- A clean structural merge is not proof of semantic consistency: cross-requirement constraints must be re-analyzed after merge.
- A rebase or conflict resolution creates a new proposal/snapshot; it must not rewrite the branch history.

## 4. Snapshot-local selection keys, not global requirement IDs

The selection key answers: "Which semantic value currently occupies this role in this snapshot?"

It is not the semantic value's identity and is not a globally stable identity. The same semantic value can be selected under multiple keys. Two independent occurrences can share a value hash while having different contextual selection keys.

The prototype therefore excludes the selection key from the semantic payload hash. It appears only in the snapshot mapping. This avoids reintroducing identity-by-name under another label.

A key may persist across ordinary revisions to express "the current preferred-tax requirement slot", but that continuity is a snapshot-level convention. Split/merge can replace keys. If a workflow later needs independently governed occurrences with durable ownership, that should be modeled as a separate optional contextual object, not smuggled into the semantic value.

## 5. Typed semantic dependency graph

A dependency edge is hash-relevant when the dependent artifact's meaning is defined in terms of that exact input.

Example chain:

`RequirementState → FormalClause → CallerContract → TestSuite → VerificationRecord`

Changing the RequirementState makes the old clause a stale derivation for the new requirement. The new clause receives a new hash and points to the new requirement state. The new contract depends on the new clause, and so on.

A generic callee contract such as `calculate_tax(taxable_basis_cents, rate_basis_points)` does not depend on the preferred caller's selected rate. Therefore, a preferred-order policy change does not invalidate the generic callee contract.

The direction is important: a caller contract may depend on the callee's interface contract; the callee's interface contract does not depend on the caller's particular business policy.

### Impact classes

- **Direct semantic dependents:** artifacts with a hash-relevant edge to the old requirement state.
- **Transitive semantic dependents:** artifacts reachable by reverse traversal of hash-relevant dependency edges.
- **Active baseline dependents:** members of that closure selected by the baseline snapshot.
- **Candidate replacements:** newly derived values selected under the changed snapshot keys.
- **Contextual/provenance relations:** visible for explanation and audit, but excluded from semantic impact traversal unless explicitly promoted into a semantic input.

Impact means "must be reconsidered/re-derived against the new input", not "must always change behavior". A deterministic re-derivation may produce an identical semantic result if the changed input is irrelevant to a particular output. That optimization requires a sound derivation rule; the prototype conservatively changes dependent hashes when the exact dependency hash changes.

## 6. Verification invalidation

Verification evidence is pinned to:
- exact artifact hash;
- exact hash-relevant dependency closure;
- verifier identity/version;
- configuration;
- assumptions.

A changed requirement should lead to a changed downstream artifact hash and verification key. Old evidence remains available for the old artifact but cannot certify the new artifact.

A provenance-only update does not change the semantic closure and therefore does not invalidate the semantic verification key. An audit/reporting layer may still need to refresh its provenance display; that is not a new proof obligation.

Statuses remain separate: PROVEN, DISPROVEN, UNKNOWN, NOT_CHECKED, ERROR, and bounded outcomes. Missing new evidence is NOT_CHECKED/UNKNOWN, never inherited PROVEN.

## 7. Concurrent evolution and merge

The existing snapshot merge algorithm performs a three-way merge by snapshot selection key:

- If only one branch changes a key, take that change.
- If both branches make the same change, the value is compatible.
- If both branches change the same key to different values, report a conflict.
- If keys are disjoint, merge the selections and record both parent roots.

This is only a structural merge. After merge, Requirement IR consistency analysis must run over the merged snapshot. For example, separate edits to a rate requirement and an exemption requirement may be structurally disjoint but jointly contradictory.

No silent last-writer-wins behavior is allowed for same-slot conflicts.

## 8. Prototype 18

Files:
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/requirement_evolution.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_requirement_evolution.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-18-RESULTS.md`

The prototype reuses the existing ContentStore, RelationStore, Snapshot, merge, and verification-key primitives.

It demonstrates:
1. immutable semantic requirement revisions;
2. snapshot-local selection keys excluded from semantic hashes;
3. direct and transitive impact over hash-relevant dependencies;
4. active-baseline impact filtering;
5. no impact from provenance-only lineage additions;
6. verification identity changes after semantic evolution;
7. split and merge selection operations with separate lineage;
8. disjoint concurrent edits merge;
9. conflicting edits to the same slot are rejected.

The experiment is intentionally not a complete change-management engine. It does not infer semantic equivalence, authorize approvals, perform automatic rebase, or run formal proof engines.

## 9. Important limits and open questions

- A trace link is not automatically a semantic dependency. Each relation type needs a declared role in impact, hashing, audit, and navigation.
- The prototype's dependency closure is conservative: any hash-relevant dependency change invalidates downstream identities.
- It does not yet distinguish "must rederive" from "must rerun verifier" from "must request human review" as separate impact actions.
- It does not compute semantic diffs between arbitrary typed IR trees.
- It does not solve cross-snapshot aliasing or contextual ownership.
- It does not merge typed expression trees or resolve semantic conflicts automatically.
- It does not prove that all dependencies have been declared. Missing trace links remain a completeness problem.
- The snapshot merge primitive is in-memory and not a distributed atomic commit.
- Provenance-only classification needs explicit review evidence; it cannot be safely delegated to an unverified natural-language similarity judgment.

## 10. Recommendation

Adopt the following research-level rule for the next prototypes:

**Semantic values are immutable and content-addressed. Snapshot-local selection determines which value occupies a project role. Only explicitly typed, hash-relevant dependencies propagate semantic impact. Provenance and lineage remain separate unless a reviewed decision promotes a fact into semantic content.**

This provides a coherent bridge between Requirement IR and the existing content-addressed dependency model without making requirement names or source references universal stable identities.

## 11. References

- SWEBOK Guide V3.0, *Software Requirements — Requirements Tracing*. [Accessible copy](https://iso.ieclist.ink/iec/ISO%20IEC%20TR%2019759-2015%20PDF.pdf).
- Goknil, Kurtev, van den Berg, *Change Impact Analysis based on Formalization of Trace Relations for Requirements*. [University of Twente paper](https://research.utwente.nl/files/246928561/Goknil2008change.pdf).
- W3C, [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/).
- W3C, [PROV Model Primer](https://www.w3.org/TR/prov-primer/).
- *Change impact analysis for requirements: A metamodeling approach*, Information and Software Technology, 2014. [DOI](https://doi.org/10.1016/j.infsof.2014.03.002).
- *An Integrated Framework for Traceability and Impact Analysis in Requirements Verification of Cyber–Physical Systems*, Electronics, 2021. [Article](https://www.mdpi.com/2079-9292/10/8/983).
