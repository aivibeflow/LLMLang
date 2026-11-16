# Scenario Study 03: Impact Analysis for a Requirement Change

**Date:** 2026-11-16  
**Status:** Research result / proposed design, not an accepted LLMLang decision  
**Scope:** Requirement evolution, cross-layer traceability, impact closure, change planning, and evidence freshness

## 1. Question

A confirmed requirement changes. How does LLMLang determine which design decisions, implementation entities, contracts, tests, proofs, generated artifacts, and downstream requirements may be affected?

The desired result is not merely a list of files that mention a requirement. The engine must produce a defensible semantic impact set, explain why each item is included, expose gaps in traceability, and avoid claiming that the impact set is complete when dependency information is incomplete.

## 2. Findings from related projects

### 2.1 agent-spec: governed requirements and requirement-to-code linking

The inspected architecture separates a human-governed Requirement IR from a derived Code Graph IR. Requirements have explicit governance statuses such as proposed, accepted, superseded, deprecated, and rejected. A requirement graph validates dependency integrity and produces planning/traceability artifacts.

Its Intent-Code Linker grounds accepted work units in code symbols using a provider graph (Atlas in the current implementation). It records typed code-target facts with provider, node, kind, file, provenance, and graph fingerprint. A stale graph is a hard diagnostic; a missing symbol is separately reported. Derived code facts do not become normative requirement truth.

The architecture also describes an intent-aware affected stage that combines changed paths/symbols with provider impact data to produce requirement-to-code paths, selectors, worktree state, and typed gaps. Candidate tests are not promoted to evidence merely because they were generated.

This is a strong precedent for distinguishing:
- normative requirements from derived code facts;
- declared symbol references from verified bindings;
- fresh graph data from stale graph data;
- candidate tests from accepted evidence;
- a missing trace link from a passing trace link.

The README also explicitly warns that test selectors can break when tests are renamed and that passing a lifecycle does not prove the requirement corpus is comprehensive.

Sources:
- [agent-spec intent compiler architecture](https://github.com/ZhangHanDong/agent-spec/blob/main/docs/intent-compiler/architecture.md)
- [agent-spec README](https://github.com/ZhangHanDong/agent-spec)
- [agent-spec requirement graph](https://github.com/ZhangHanDong/agent-spec/blob/main/src/spec_knowledge/requirement_graph.rs)
- [agent-spec tool-first skill](https://github.com/ZhangHanDong/agent-spec/blob/main/skills/agent-spec-tool-first/SKILL.md)

### 2.2 Atlas: code-level dependency and impact substrate

Atlas provides a semantic code graph and impact queries over symbols, calls, references, and other extracted relationships. This can supply implementation-side evidence about what uses a changed symbol.

However, a code graph alone cannot establish which business requirement a symbol satisfies, whether a requirement remains correct, or which specification decisions are authoritative. That mapping must be explicit and governed by a higher-level model.

Source: [Atlas repository](https://github.com/LordCasser/atlas).

### 2.3 LLMLang's current baseline

The LLMLang concept already proposes three distinct layers—Specification, Design, Implementation—with explicit correspondence and verification relationships. The Development Engine RFC proposes semantic dependency analysis and incremental verification. The Request/Change RFC proposes requirements as authoritative structured objects, traceability, semantic diffs, and impact analysis.

The missing part is a precise propagation algorithm and a representation of incomplete or uncertain traceability.

## 3. Proposed traceability model

### 3.1 Use typed, directional relations

A generic `related_to` edge is insufficient. The graph should distinguish at least:

| Relation | Direction | Meaning |
|---|---|---|
| `refines` | Design → Specification | Design makes a requirement more concrete |
| `implements` | Implementation → Design | Implementation realizes a design element |
| `satisfies` | Design/Implementation → Requirement | Element contributes to satisfying a requirement |
| `verified_by` | Requirement/contract → Test or proof | Evidence checks a declared obligation |
| `depends_on` | Any semantic node → dependency | Node's validity depends on another node |
| `derived_from` | Derived artifact → source | Generated or inferred artifact provenance |
| `supersedes` | New requirement/decision → old | Explicit evolution of normative meaning |
| `constrains` | Constraint → target | A policy or invariant limits a target |

Relations must carry provenance and, where applicable, a confidence/verification status. A model-generated guess is not equivalent to a reviewed trace link.

### 3.2 Distinguish traceability states

A link should not be merely present/absent. Suggested states:

- **Declared:** an author asserts a relationship.
- **Validated:** deterministic checks confirm structural validity (e.g. target exists and has the expected kind).
- **Reviewed:** an authorized reviewer confirms the semantic relationship.
- **Verified:** relevant evidence demonstrates the claimed property.
- **Stale:** one or more pinned inputs changed.
- **Missing:** a required relation has not been supplied.
- **Unknown:** the engine cannot determine whether the relation exists or is complete.

These states must not be collapsed. In particular, a syntactically valid link is not proof that an implementation satisfies a requirement.

## 4. Impact analysis algorithm

### 4.1 Inputs

The impact operation receives:

- changed Requirement Stable IDs and before/after Content Hashes;
- the accepted baseline snapshot;
- typed traceability edges and their provenance;
- Design and Implementation dependency graphs;
- test, proof, contract, and build artifact input identities;
- project policy defining mandatory coverage and risk thresholds;
- current graph freshness information.

### 4.2 Compute a semantic impact closure

A conservative algorithm:

1. Identify directly changed requirement nodes.
2. Follow outgoing `refines` / `satisfies` correspondence edges to candidate Design and Implementation nodes.
3. Follow reverse dependency edges from affected design/implementation nodes to consumers.
4. Follow `verified_by` edges to tests, proofs, analyses, and verification obligations.
5. Follow dependencies of affected contracts and test fixtures to identify supporting semantic inputs.
6. Include generated artifacts and external interfaces whose declared inputs or exported semantics changed.
7. Re-evaluate cross-layer constraints and global invariants whose scope intersects the affected set.
8. Mark every traversed edge with the reason it was followed and its freshness/assurance status.
9. Detect required but missing trace links using project coverage policy.
10. Return the affected set, unresolved gaps, and a conservative completeness classification.

The traversal must be relation-aware. For example, a change to an internal Implementation detail should not automatically invalidate a Specification-level consumer if the consumer depends only on an unchanged public contract. Conversely, changing a requirement must not be hidden by an unchanged implementation hash: the requirement-to-implementation satisfaction claim itself needs re-evaluation.

### 4.3 Result is more than a node list

Each impact item should include:

- target Stable ID and current Content Hash;
- layer and node kind;
- impact reason and path from the changed requirement;
- direct vs transitive impact;
- relation types traversed;
- whether the target is required to change, required to revalidate, or merely worth reviewing;
- freshness of its source graph and trace links;
- relevant verification evidence and its status;
- confidence/completeness boundary.

The engine should group items into:
- **must update** — semantic mismatch or direct obligation change;
- **must revalidate** — content may remain valid, but proof/analysis inputs or assumptions changed;
- **review recommended** — possible impact without a deterministic obligation;
- **traceability gap** — required link or evidence is absent/stale;
- **unaffected with justification** — dependency boundary proves no relevant input changed.

## 5. Requirement change workflow

A requirement change should not directly mutate accepted Specification Graph state.

1. Create a Change against the exact requirement Stable ID and expected Content Hash.
2. Record the Request/Decision that authorizes or explains the change.
3. Produce a before/after semantic diff in business and formal views.
4. Compute the impact closure using the accepted baseline.
5. Identify affected Design/Implementation objects and verification obligations.
6. Generate a change plan with explicit dependencies and acceptance criteria.
7. Update or supersede related design and implementation objects in a Change Set or explicitly linked Change Sets.
8. Recompute affected hashes and trace links.
9. Run required verification and mark stale evidence as such.
10. Review the new requirement meaning and its downstream realization.
11. Accept atomically according to Change Set and approval policy.

A requirement change may be accepted before all implementation work is complete only if the project explicitly supports an intermediate accepted specification state and clearly marks downstream conformance as pending. It must not present the old implementation as verified against the new requirement.

## 6. Completeness and uncertainty

Impact analysis can only be as complete as the graph and its relations.

The engine must not claim "all affected code found" if:
- the code graph is stale;
- some language constructs were not extracted;
- a required requirement-to-code binding is missing;
- dependencies are unresolved or dynamic;
- a relation was inferred but not validated;
- external consumers are outside the indexed project boundary.

Suggested completeness outcomes:

| Outcome | Meaning |
|---|---|
| `COMPLETE_WITHIN_DECLARED_SCOPE` | All required graph inputs are fresh and all required relation classes are covered within the declared boundary |
| `INCOMPLETE` | Known missing/stale/unresolved relations prevent complete impact claims |
| `UNKNOWN` | The engine cannot determine completeness |
| `NOT_RUN` | Impact analysis was not performed |

Even `COMPLETE_WITHIN_DECLARED_SCOPE` does not mean the real world contains no unmodeled dependency. It means the declared project boundary and extraction capabilities were covered.

## 7. Verification invalidation

A changed requirement changes the proposition being verified. Evidence produced for the old requirement hash cannot automatically prove the new requirement.

Each verification result should commit to:
- requirement and contract hashes;
- design/implementation hashes in scope;
- test/proof specification hashes;
- tool/verifier version and configuration;
- assumptions and environment/toolchain identity;
- relevant external input versions.

On requirement change:
- direct proofs of the old requirement become stale for the new requirement;
- tests may remain executable but their coverage/meaning must be re-evaluated;
- tests generated from the new requirement are candidates until independently executed;
- unchanged implementation may still satisfy the new requirement, but must be checked against the new requirement hash;
- evidence may be reused only under an explicit sound reuse rule whose assumptions are machine-checkable.

## 8. Required invariants

Proposed invariants for a future RFC:

1. Confirmed requirements are normative; code-derived facts cannot silently rewrite them.
2. Every traceability edge has a typed relation and provenance.
3. Declared, validated, reviewed, verified, stale, missing, and unknown relations remain distinguishable.
4. Impact analysis uses a pinned baseline and fresh graph inputs or reports incompleteness.
5. Every affected item has an explainable path from the changed requirement.
6. A requirement change invalidates evidence whose declared proposition/input changed.
7. A generated test or inferred link is not accepted evidence until its required validation/review/execution occurs.
8. The system never reports complete impact outside the declared and validated analysis scope.
9. A passing implementation check does not establish that the requirement set is complete or correct.
10. Missing required traceability is a visible diagnostic, not an implicit unaffected result.

## 9. Open questions

1. Which relations are normative language-level SPG edges and which belong to the development/traceability layer?
2. Should every externally observable requirement require at least one Design or Implementation satisfaction path?
3. How should non-functional requirements map to multiple services, runtime measurements, deployment configuration, and operational evidence?
4. How should dynamic dispatch, reflection, plugins, generated code, and external systems affect impact completeness?
5. Should the engine distinguish semantic impact from delivery/work planning impact?
6. How should it represent a requirement that is intentionally not implemented yet but has been accepted?
7. Can a proof be transported across a requirement change by proving implication/equivalence, and what trusted checker establishes that relation?
8. What is the minimal set of traceability relations required for small projects without forcing full formal traceability?

## 10. Preliminary conclusion

agent-spec provides the strongest practical precedent for governed requirements, typed requirement-to-code bindings, graph freshness, traceability diagnostics, and explicit evidence boundaries. Atlas can supply code-level dependency and impact facts, but cannot replace normative requirements or semantic review.

LLMLang's three-layer graph offers a natural place to unify these facts, provided it does not collapse the distinction between normative specification and derived code intelligence.

**Preliminary recommendation:** model requirement impact as a provenance-carrying, typed graph traversal over a pinned snapshot. Return not only affected nodes but also impact paths, required actions, stale evidence, missing links, and a declared completeness boundary. Treat every changed requirement as a new verification proposition.

This is a research conclusion, not an accepted change to LLMLang's concept or RFCs.

## Sources

- [agent-spec intent compiler architecture](https://github.com/ZhangHanDong/agent-spec/blob/main/docs/intent-compiler/architecture.md)
- [agent-spec README](https://github.com/ZhangHanDong/agent-spec)
- [agent-spec requirement graph](https://github.com/ZhangHanDong/agent-spec/blob/main/src/spec_knowledge/requirement_graph.rs)
- [agent-spec tool-first skill](https://github.com/ZhangHanDong/agent-spec/blob/main/skills/agent-spec-tool-first/SKILL.md)
- [Atlas repository](https://github.com/LordCasser/atlas)
- LLMLang internal baseline: `LLMLang-CONCEPT.md`, `RFC-REQUEST-CHANGE.md`, `RFC-DEVELOPMENT-ENGINE.md`, `RESEARCH-DEEP-COMPARISON.md`
