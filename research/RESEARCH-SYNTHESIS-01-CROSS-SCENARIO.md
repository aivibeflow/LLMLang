# Research Synthesis 01: Cross-Scenario Architectural Findings

**Date:** 2026-11-16  
**Status:** Research synthesis / proposed design direction; not an accepted LLMLang decision  
**Based on:** Scenario Studies 01–04

## 1. Purpose

The four scenario studies examined identity-preserving rename, concurrent Change Sets, requirement impact analysis, and verification-result reuse. This document consolidates their common architectural implications and identifies the next design gaps.

It does not amend the normative concept or accept any proposal automatically.

## 2. Four scenarios, one shared foundation

| Scenario | Core problem | Required foundation |
|---|---|---|
| Rename | Preserve logical identity while semantic name/state changes | Stable identity, immutable state, typed name bindings |
| Concurrent changes | Prevent stale writes and incompatible merges | Immutable snapshots, expected-state preconditions, atomic acceptance |
| Requirement impact | Determine what must change or be revalidated | Typed cross-layer traceability and dependency closure |
| Verification reuse | Reuse only evidence that still applies | Verification-specific input identity and sound invalidation |

These are not four independent subsystems. They depend on one common model of semantic identity, immutable state, dependency relations, and provenance.

## 3. Proposed common object model

The architecture appears to need at least these distinct concepts:

### 3.1 Entity identity

A logical entity has a Stable ID that survives rename and movement. It must not be derived solely from mutable names or source locations.

### 3.2 Immutable semantic state

An entity state is canonical semantic content plus its hash-relevant relations. A modification creates a new state and Content Hash. Stable ID and Content Hash answer different questions.

### 3.3 Snapshot

A snapshot identifies a consistent graph state, normally by layer-root hashes and a project/policy root where needed. A Change Set is based on a specific snapshot, not a floating "latest" reference.

### 3.4 Typed relation

Graph edges must identify their semantics: ownership, reference, dependency, refinement, implementation, satisfaction, verification, derivation, supersession, and so on. A generic relation cannot support sound impact or invalidation.

### 3.5 Change operation

A Change is a typed operation over identities and expected prior states. It carries read/write dependencies, intent, provenance, and policy obligations.

### 3.6 Verification record

A verification record is an immutable result for a precise proposition and input manifest. It is not a property that can be copied onto an entity because its Stable ID is unchanged.

## 4. A unified lifecycle

A candidate workflow that composes the four scenarios:

1. **Request and clarification:** preserve original human intent and decisions.
2. **Baseline pinning:** bind the work to an accepted snapshot and relevant policy roots.
3. **Semantic proposal:** produce typed Change operations with Stable IDs and expected hashes.
4. **Impact computation:** calculate read/write sets, dependency closure, traceability gaps, and affected obligations.
5. **Conflict detection/rebase:** compare against current head; generate a new proposal revision if the baseline advanced.
6. **Candidate construction:** build a new immutable graph candidate without mutating accepted state.
7. **Validation:** run structural, name-resolution, type/effect, policy, and semantic checks.
8. **Verification:** reuse exact-key evidence where safe; otherwise run affected checks.
9. **Review/approval:** bind approval to the exact candidate, baseline, policy, and validation/evidence summary.
10. **Atomic acceptance:** compare-and-swap the accepted head and append immutable history.
11. **Evidence publication:** attach new verification records to the exact accepted snapshot and preserve stale records as history.

This lifecycle should support small implementation-only changes without forcing a full requirements ceremony, provided policy permits and the engine can demonstrate that no normative requirement is changed.

## 5. Cross-cutting invariants

The following are candidate invariants for future RFC work:

1. Stable identity is independent of mutable naming and source location.
2. Semantic states are immutable and content-addressed.
3. All Change operations identify their targets and expected prior states.
4. Accepted snapshots are immutable; acceptance advances a root pointer atomically.
5. Every Change Set has an immutable baseline.
6. Every semantic dependency relevant to validation is typed and discoverable or explicitly marked incomplete.
7. Traceability claims carry provenance and assurance state.
8. Impact analysis reports its scope and completeness boundary.
9. A merge candidate is not accepted merely because its component proposals were individually valid.
10. Approval applies only to the exact candidate/baseline/policy tuple reviewed.
11. Verification results bind to exact propositions, inputs, tools, configurations, assumptions, and environments.
12. Cache reuse never upgrades UNKNOWN, NOT_CHECKED, skipped, or unsupported work into success.
13. LLM output is a proposal or explanation, never an independent authority for identity, approval, or proof.
14. Incomplete graph knowledge causes conservative invalidation or an explicit UNKNOWN/INCOMPLETE result, not a false unaffected claim.

## 6. Architectural separation that should be preserved

The studies reinforce several distinctions that should not be collapsed:

| Do not conflate | Why |
|---|---|
| Stable ID and Content Hash | Identity survives changes; state hash does not |
| Name and identity | Names are mutable and namespace-scoped |
| Graph merge and semantic acceptance | Mechanically mergeable changes can violate invariants |
| Declared trace link and verified satisfaction | A relation is not proof |
| Requirement truth and code-derived facts | Implementation cannot silently redefine intent |
| Candidate test and executed evidence | Generated test source is not a test result |
| Verification key and entity hash | Tool/environment/proposition matter |
| Cache hit and correctness | Cache is safe only under a complete identity model |
| Approval and verification | Human authorization and machine evidence answer different questions |
| Unknown and success | Absence of a failure is not evidence of correctness |

## 7. Design questions that remain foundational

Before implementing these mechanisms, LLMLang should resolve:

1. **Identity scope:** Are Stable IDs project-global, layer-local, or namespace-scoped? How are IDs allocated for imported repositories and generated entities?
2. **Hash boundaries:** Which names, metadata, and typed relations enter entity hashes versus binding/index hashes?
3. **Snapshot model:** Is the accepted root a single project root or a tuple of independent layer roots plus policy/tooling roots?
4. **Dependency semantics:** Which edge kinds are hash-relevant, validation-relevant, impact-relevant, or merely navigational?
5. **Read-set completeness:** How does the engine represent dependencies discovered dynamically or only during verification?
6. **Approval authority:** Which component authenticates the human/role and attests the approval, and how is revocation handled?
7. **Evidence portability:** Which verification records can be shared across machines, and what attestation is required?
8. **Layer correspondence:** How strict must Specification→Design→Implementation traceability be for different project profiles?
9. **External boundary:** How are APIs, consumers, services, runtime configuration, and external dependencies represented?
10. **Partial progress:** Can specification acceptance precede implementation completion, and how is non-conformance represented without implying a complete accepted product?

## 8. Recommended next research steps

The next research should not add more feature names. It should turn the common foundation into precise data contracts and failure semantics.

Recommended order:

1. Define the minimal SPG entity, state, relation, and snapshot schema.
2. Define a canonical Change operation envelope with expected hashes, read/write sets, and intent.
3. Define the Change Set state machine and compare-and-swap acceptance protocol.
4. Define the typed traceability/impact result schema.
5. Define Verification Record and Verification Key schemas, including tool/environment manifests.
6. Build executable scenario fixtures for the four studies and test both success and failure paths.
7. Compare the resulting model against linkly, Edict, DSP CodeGen, agent-spec, and Atlas again to find contradictions or unnecessary complexity.

## 9. Preliminary synthesis

The strongest opportunity for LLMLang is not any single feature. It is a coherent chain:

**human intent → governed semantic requirements → immutable graph state → typed changes → impact/conflict analysis → independent verification → exact approval → atomic accepted snapshot.**

The Merkle DAG can make this chain efficient, but only if its hash boundaries and dependency semantics are defined rigorously. Otherwise, it risks becoming a fast cache over incomplete assumptions.

**Preliminary recommendation:** prioritize the shared identity/state/snapshot/relation model before designing more orchestration features. It is the foundation needed to make all four scenarios reliable.

This document is a research synthesis, not an accepted architectural decision.

## 10. Internal sources

- `RESEARCH-SCENARIO-01-RENAME-IDENTITY.md`
- `RESEARCH-SCENARIO-02-CONCURRENT-CHANGES.md`
- `RESEARCH-SCENARIO-03-REQUIREMENT-IMPACT.md`
- `RESEARCH-SCENARIO-04-VERIFICATION-REUSE.md`
- `LLMLang-CONCEPT.md`
- `RFC-REQUEST-CHANGE.md`
- `RFC-DEVELOPMENT-ENGINE.md`
- `RESEARCH-DEEP-COMPARISON.md`
