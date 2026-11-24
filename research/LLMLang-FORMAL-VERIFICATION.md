# LLMLang — Unified Semantics and Formal Verification

**Status:** Architectural requirement  
**Scope:** Language semantics, compilation, formal models, and proofs

## 1. Goal

LLMLang MUST eliminate the need to maintain an executable algorithm and its formal model independently. The executable program, the model for TLA+/TLAPS, and artifacts for other proof systems must all be derived automatically from a single canonical semantic description of the program.

The goal is not merely to keep source code and the model synchronized, but to establish a verifiable connection among the source program, its formal semantics, the verification model, and the executable result.

## 2. Single Source of Truth

1. An algorithm is defined once in LLMLang's canonical semantic model — the SPG and/or a typed semantic IR.
2. Executable and verification representations are derived artifacts.
3. Manually duplicating executable logic in TLA+ or another specification language is not the standard way to create a model.
4. Additional invariants, lemmas, abstractions, and environment assumptions are permitted if they are explicitly linked to the original program objects and do not replace the program's algorithm.
5. A change to the source semantics must automatically trigger regeneration of dependent representations and invalidation of outdated proofs.

## 3. Formal Semantics of LLMLang

Every construct in the proof-friendly core MUST have precise formal semantics defining:
- permitted values and states;
- evaluation and transition rules;
- observable behavior;
- effects and interaction with the environment;
- exceptional and erroneous outcomes;
- numerical semantics, including overflow, rounding, and special values where applicable.

The semantics must not be defined by the behavior of a particular backend. The interpreter, VM, native backend, and formal verification backends implement the same semantics within the scope of their explicitly stated guarantees.

An extension without formal semantics is permitted only if it is explicitly marked as unsupported for formal verification. Such an extension must not silently appear within the proved portion of a program.

## 4. Generation of Formal Models

The compiler SHOULD automatically select and run an appropriate verification backend based on the program's semantics and the required properties.

### 4.1. TLA+ / TLAPS

TLA+ is the preferred backend for:
- state-transition systems;
- concurrent algorithms;
- distributed protocols;
- synchronization and mutual exclusion;
- transactions, replication, and consensus;
- algorithms whose properties are naturally expressed through safety, liveness, and temporal logic.

The generator MUST construct the model from LLMLang's canonical semantic model rather than from an independently written specification. TLAPS can check mathematical proofs of model properties; TLC can explore finite state spaces and find counterexamples. Bounded checking with TLC must not be labeled as a universal proof over an unbounded state space.

### 4.2. Other Backends

TLA+ must not be the only verification mechanism. SMT/Why3, Lean, Coq, and other systems may be used for suitable classes of problems.

Backend selection is the responsibility of the LLMLang toolchain. The absence of a suitable backend must not prevent the execution of a correctly typed program, but it must limit the guarantees that can be claimed.

## 5. Preventing Semantic Divergence

A shared AST is not sufficient in itself: identical syntax trees do not establish identical semantics.

Explicit semantic-preservation obligations must exist for every transformation.

Required pipeline:

```
LLMLang source / SPG
        |
        v
Canonical semantic IR
        |
        +---------------------+
        |                     |
        v                     v
Verification backend     Execution backend
(TLA+, Why3, ...)        (VM, Rust, Go, C++, ...)
        |                     |
        v                     v
Formal model             Executable artifact
        |                     |
        +----------+----------+
                   |
                   v
        Verified correspondence
```

Target relationships:

- the semantics of the source program correspond to the generated formal model;
- the semantics of the generated executable code correspond to the semantics of the source program;
- all abstractions and additional backend states are related through an explicitly defined correspondence relation, such as refinement.

The preferred long-term approach is verified translators and proof-carrying compilation. At early stages, independent translation validation of individual translation results is acceptable. An unverified generator cannot certify its own correctness.

## 6. Verification Statuses

A status is assigned to each property individually. The minimum set is:

| Status | Meaning |
|---|---|
| `PROVEN` | A trusted proof checker has verified the proof under the stated assumptions |
| `DISPROVEN` | A validated counterexample has been obtained, or the negation of the property has been proved |
| `UNKNOWN` | Verification was unable to prove or disprove the property |
| `NOT_SUPPORTED` | The backend does not support the required construct or property |
| `NOT_CHECKED` | Verification was not performed |

Results from testing, fuzzing, runtime monitoring, and exhaustive exploration of finite state spaces must be recorded separately. They are not equivalent to `PROVEN`.

The absence of a discovered counterexample must not be treated as proof.

## 7. Assumptions and Boundaries of Guarantees

Every proof must record:
- input constraints;
- the numerical computation model;
- assumptions about the external environment;
- fairness and scheduling assumptions;
- abstractions and hidden states;
- trusted components;
- the versions of the language semantics and tools.

A proof establishes a property only under these assumptions. A proof about a formal model does not, by itself, prove the correctness of the native compiler, runtime, operating system, hardware, or the specification's correspondence to the user's actual intent.

## 8. Compositional Verification and Proof Boundaries

### 8.1. Properties, Not a Single Status for a Function

Verification status MUST be assigned to an individual property, not to a function or module as a whole. Different properties of a single function may simultaneously be proved, disproved, unsupported, or unknown.

For a called operation, the following must be tracked separately:
- its contract: preconditions, postconditions, invariants, effects, permitted errors, and termination conditions;
- conformance of the specific implementation to that contract;
- additional properties of the internal algorithm and implementation.

Simply declaring a postcondition does not make it a guarantee. A contract becomes an admissible basis for proving a caller only if there is proof that the callee implementation satisfies that contract, or if this conformance is explicitly accepted as a trusted assumption.

### 8.2. Assume-Guarantee Composition

Proof composition must follow the assume-guarantee principle:

1. For the callee, record the preconditions under which it is called and the guarantees it is required to provide.
2. A separate proof establishes that the callee implementation satisfies these guarantees under the stated preconditions and assumptions.
3. The caller may use these guarantees as an abstract contract without exposing the callee's internal implementation.
4. The caller's proof records every contract guarantee on which it relies, along with the corresponding proofs or assumptions.
5. A system-level property is considered proved only when the entire required chain of guarantees and implementation conformance is closed, and all remaining assumptions are explicitly reflected in the result.

If the callee implementation's conformance to its contract has not been proved, the caller can be proved only conditionally — assuming that the callee satisfies its contract. Such a result must not be presented as an unconditional guarantee for the entire system. The `PROVEN` status means that a proof has been checked under an explicitly stated proof context; any assumptions must be visible to the consumer and must not be lost during composition.

### 8.3. Propagation of Unproved Properties

Lack of proof must not automatically propagate to every caller merely because the callee is reachable in the call graph.

The system MUST analyze dependencies of the specific property, including:
- passing and use of values (data dependencies);
- effects on branching and reachability (control dependencies);
- side effects and state changes (effect/state dependencies);
- calls and the contract guarantees being used;
- assumptions about termination, errors, and exceptional outcomes when relevant to the property.

If unproved callee behavior affects a caller property being proved, the caller's proof must either obtain the necessary guarantee through a proved contract, retain an explicit assumption, or receive a status that prevents the property from being considered unconditionally proved. If no dependency exists, the callee's lack of proof must not lower the status of an independent caller property.

### 8.4. Evidence Types and Trust Boundaries

For each property being used, at least the following must be distinguished:
- a proof of implementation conformance to the contract, checked by a trusted proof checker;
- a trusted assumption of conformance to the contract;
- a runtime assertion/monitor that checks the property only in a particular execution;
- test evidence covering a finite set of scenarios;
- absence of evidence or lack of support for the property in the selected backend.

Tests and runtime checks must not automatically be promoted to universal proofs. Assumptions must be named, versioned, and included in the proof context. Consumers of a result must be able to determine which system-level guarantees are proved without assumptions and which depend on them.

### 8.5. Traceability and Invalidation

The system MUST support traceability along the chain:
`requirement → contract property → implementation evidence → call/dependency edges → caller property → system-level claim`.

A change to a contract, implementation, conformance proof, assumption, or hash-relevant dependency MUST invalidate the affected proofs and resulting properties. Invalidation must be property-specific: properties whose proof dependencies have changed are recomputed, while independent proofs may be retained.

## 9. Provenance and Invalidation

Every generated artifact and verification result MUST be bound to:
- the Content Hash of the source semantic objects;
- the version of LLMLang's formal semantics;
- the generator's version and configuration;
- the versions of the backend and proof checker;
- explicit assumptions and model parameters.

A change to any hash-relevant element MUST invalidate potentially outdated dependent proofs and results. Independent, unchanged subgraphs may reuse cached results.

## 10. Incremental Implementation

1. Establish the mathematical semantics of a small proof-friendly core.
2. Define a canonical semantic IR from which both executable and formal representations are constructed.
3. Implement one vertical slice: a small algorithm, its execution, and an automatically generated model.
4. Choose a class of algorithms naturally expressible in TLA+ and implement a TLA+ backend.
5. Check finite models with TLC and proofs with TLAPS, without conflating these levels of guarantee.
6. Introduce independent translation validation for both generation paths.
7. Gradually formalize and verify the translators themselves, then expand the proof-friendly core and the set of backends.
8. Add incremental invalidation and proof reuse based on Content Hash.

## 11. Architecture Acceptance Criteria

The architecture meets this requirement when, for a supported subset of LLMLang:
- a developer describes an algorithm only once;
- changing the algorithm automatically updates the model and executable artifact;
- the model contains no independently rewritten executable logic;
- each artifact's correspondence to the source semantics is checked by proof or independent translation validation;
- unsupported constructs and unproved properties are explicitly reflected in verification statuses;
- proofs are tied to exact versions of the source objects, semantics, and tools.

## Public-interface integration (2026-11-24; proposed)

Addition to compositional verification (a candidate, not a newly approved rule): for a public interface, the proof that Body satisfies C_impl and the proof that C_impl refines C_pub are distinct. A proof of the calling code may use the exact revision of C_pub as an explicitly registered assumption; closing the program proof requires a valid binding and independent verification of both obligations under consistent semantics, observation models, and assumptions. UNKNOWN, absence of an implementation, or absence of evidence do not constitute proved conformance. When an implementation is replaced, only proofs whose exact dependencies remain unchanged are retained.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## Explicit Assumptions and Conditional Proofs (RT-36 Research Proposal)

[RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md): separate typed assumptions about external implementations' conformance to contracts, exact library and ABI identifiers, trust-policy permissions, transitive PDG closure, and discharge and revocation of assumptions. A checked proof under open assumptions does not establish that the assumptions themselves have been proved. The research explores separating the verification result, closure, evidence kind, freshness, and admissibility; existing statuses are not changed without an accepted decision.
