# RT-20 — Contract identity and compatibility boundary

**Status:** Research reconciliation; proposed terminology and compatibility obligations, not a normative LLMLang decision  
**Date:** 2026-11-18  
**Parent:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)  
**Terminology:** [Draft Glossary](../draft/GLOSSARY.md)  
**Related research:** [Scenario 10 — Contract Identity and Implementation Binding Snapshots](RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md), [Scenario 14 — Formal Behavioral Contracts and Refinement](RESEARCH-SCENARIO-14-FORMAL-BEHAVIORAL-CONTRACTS-AND-REFINEMENT.md), [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md)

## 1. Purpose

RT-20 currently stores a caller-required Contract hash at each call-site target alternative and resolves the callee-provided Contract through the exact callee declaration. This is the correct storage shape:

```text
Caller --required_contract--> Contract
   |
   +--callee--> Callee --provides_contract--> Contract
```

The remaining gap is semantic: the prototype has not defined whether the two Contract objects must be identical or may be distinct but behaviorally compatible. This document reconciles the identities used by RT-20 with the Draft Glossary and defines the obligations a future compatibility relation must satisfy. It does not introduce a new SPG schema or claim that the prototype proves compatibility.

## 2. Identity terms: separate questions, separate hashes

| Term | What it identifies | What it does not identify |
|---|---|---|
| Contract Content Hash (generic `ContractHash` in this document) | One exact immutable Contract semantic value | An operation, conformance class, implementation, or compatibility proof |
| `OpHash` | One exact semantic Operation version, including externally relevant interface, Contract, and semantic context | A concrete implementation or a conformance-class definition by itself |
| `CCHash` | One exact Conformance Class definition: an `OpHash`, constraints, and conformance criteria | A Contract object alone, a discovered candidate set, or proof that a particular implementation conforms |
| `ImplHash` | One exact immutable implementation artifact and its hash-relevant dependencies | Its conformance to any Contract or class |
| `CandidateSetHash` (optional) | One finite, scoped discovery result | The complete conformance class |
| Evidence identity | One immutable verification/evidence record for a specific claim and exact inputs | The truth of the claim unless a trusted verifier/policy validates it |

`ContractHash` is descriptive terminology for the exact Contract-object hashes already carried by the RT-20 prototype. It is not a newly selected acronym or a new normative hash type. In particular:

- `ContractHash != OpHash` as a type-level rule, even if a particular canonical Operation embeds or commits to a Contract value.
- `ContractHash != CCHash`. A conformance class includes an Operation identity plus constraints and conformance criteria; it is not the Contract object.
- `CCHash != CandidateSetHash`. Membership rules do not change merely because discovery finds another implementation.
- Equality of any two hashes is meaningful only within the same typed/domain-separated identity scheme. Cross-kind equality must not be used as a compatibility shortcut.

The glossary currently leaves canonical encodings and domain separation open. This document does not select an algorithm, envelope, or wire representation.

## 3. RT-20 call-site meaning

For each call-site target alternative:

- `required_contract_hash` identifies the exact immutable Contract value the caller requires at that site.
- The exact `callee_hash` identifies the selected immutable callee declaration.
- The callee declaration's single `provides_contract` reference identifies the exact Contract value it claims to provide.
- No second provided-Contract reference is stored in the caller, dependency edge, reverse index, decision, or CIP identity. The provided Contract is resolved through the callee hash.

This storage model is independent of the final identity architecture for logical entities, lineage, and SPG occurrences. It uses exact immutable value references without assuming that content hashes alone provide logical continuity.

A Contract reference is a declaration/semantic binding, not evidence that the callee actually satisfies the Contract. Likewise, an `implements` or `provides_contract` relation is a claim/binding, not a proof.

## 4. Identity equality versus behavioral compatibility

Two distinct questions must not be conflated:

1. **Identity:** are the required and provided Contract references the same exact immutable semantic value?
2. **Compatibility:** does the behavior permitted by the provided Contract satisfy every guarantee the caller is entitled to rely on under the required Contract?

If the hashes are equal and the typed objects validate, the prototype can establish exact Contract identity. This is a useful sufficient identity case, but the current RT-20 validator still does not establish behavioral refinement or authenticate evidence.

If the hashes differ, the result is not automatically incompatible. It is also not automatically compatible. A future verifier must evaluate an explicit, versioned relation over the two exact Contract objects and all relevant semantic assumptions.

For the behavioral model explored in Scenario 14, the intended direction is:

`ProvidedContract refines RequiredContract`

The callee must be at least as capable/guaranteed as the caller requires. In a trace-based model, for every input and initial state admitted by the required Contract, the callee's observable traces must be permitted by the required Contract. Informally:

`Traces(Provided, x, s) subseteq Traces(Required, x, s)`

This is only a starting point, not a complete LLMLang rule. A sound relation must also account for:

- **Input domain / preconditions:** the callee must accept every call the required Contract permits; it must not impose stronger preconditions.
- **Outcomes and postconditions:** every returned value and terminal outcome must satisfy the required guarantees.
- **Effects and frame conditions:** observable writes, events, I/O, and their ordering/multiplicity must remain within the required permissions.
- **Failures:** additional observable failure modes must not violate the caller's guarantees.
- **State abstraction:** concrete and abstract state transitions must be related by a justified, pinned abstraction relation.
- **Termination, liveness, and resources:** only properties explicitly promised by the required Contract are obligations; no unexpressed constant-time, constant-memory, or termination guarantee may be inferred.
- **Concurrency and environment:** histories, assumptions, target constraints, and external observations must be included when relevant.

A stronger provider guarantee may refine a weaker requirement. The reverse direction is not generally safe. Equality of types or signatures alone is insufficient.

## 5. Relation to the Glossary Conformance Class

The glossary's `CCHash` answers a different question from RT-20's per-call-site Contract pair.

- An `OpHash` names the semantic operation required by an abstract operation call.
- A `CCHash` identifies the complete admissibility predicate for implementations of that operation under constraints.
- An `ImplHash` names a concrete implementation.
- Conformance evidence establishes that an exact `ImplHash` belongs to an exact `CCHash`.

RT-20's current explicit callee model instead checks the relationship between a caller's required Contract and the Contract declared by the exact selected callee. This can be used as a local call-site compatibility obligation, but it must not silently be relabeled as implementation conformance to a `CCHash`. The two models may later be connected by an explicit mapping, but that mapping must define which Operation and conformance class govern the call.

Where the language uses abstract Operation dispatch and implementation selection, Scenario 10's binding-snapshot model remains relevant: callers depend on the Contract/Operation semantics, while the binding snapshot pins the selected implementation. A direct concrete callee reference in RT-20 must not be assumed to have those abstract-dispatch semantics.

## 6. Evidence requirements

A future compatibility result must be a claim-specific immutable evidence record, not a caller-supplied `PROVEN` string plus arbitrary ID. At minimum, its identity should commit to:

- exact required Contract hash;
- exact provided Contract hash;
- exact callee hash and, where relevant, `ImplHash`;
- compatibility relation and rule/version;
- proof obligations and their canonical digest;
- assumptions, environment, target constraints, and abstraction relation hashes;
- evidence artifact/certificate digest;
- verifier/checker identity and version;
- frontend/translation semantics and trusted computing base where applicable;
- result status and scope.

A verifier must resolve the exact referenced objects, validate their kinds and hashes, check that the evidence binds those same inputs, and apply an explicit trust policy to the verifier and evidence type. An opaque evidence ID is not authentication.

Statuses must preserve the difference between proof and bounded evidence. At minimum, distinguish `PROVEN`, `DISPROVEN`, `UNKNOWN`, `NOT_CHECKED`, and bounded-test outcomes. A finite-model checker may return `PROVEN` only for its explicitly complete finite model; it does not prove that source code was faithfully translated into that model. The existing `contract_model.py` prototype has exactly this limited scope.

## 7. Current prototype boundary

The current RT-20 implementation:

- stores the caller-required Contract hash per call-site target;
- stores the callee hash and resolves the callee-owned provided Contract through that exact callee;
- validates object kinds, hashes, and materialized references;
- includes the caller-required Contract hash in call-edge identity and semantic diff;
- records a compatibility status and evidence ID in decisions.

It does **not**:

- define a normative Contract compatibility relation;
- prove refinement between distinct Contract values;
- authenticate or independently validate compatibility evidence;
- prove that a callee implementation conforms to a `CCHash`;
- prove that an adapter/fork implements its rationale;
- establish source-to-model or compiler/runtime semantic correspondence.

Consequently, a decision's current `PROVEN` field is recorded input, not a verified conclusion. Candidate validation and semantic diff must continue to describe it as an untrusted assertion until the evidence gate is implemented. No migration, adaptation, or fork may be represented as behaviorally verified solely because these structural checks pass.

## 8. Proposed next work

1. Define a typed Contract semantic model and canonical identity projection without prematurely selecting the global hash envelope.
2. Specify the compatibility relation for preconditions, outcomes, effects, failures, state, termination, and concurrency, including explicit assumptions.
3. Extend the finite-model prototype with tests for domain variance, effect traces, failures, incomplete models, and distinct-but-compatible Contracts; keep its bounded scope explicit.
4. Design immutable evidence records and a trusted verification boundary. Reject missing, mismatched, stale, or unauthenticated evidence.
5. Integrate the verified relation into RT-20 planning and candidate validation; preserve the single callee-owned provided-Contract reference.
6. Revisit the mapping to `OpHash`/`CCHash` only after the operation-call and implementation-binding semantics are specified.

Until these steps are complete, RT-20 must fail closed for any action whose safety depends on unverified behavioral compatibility.
