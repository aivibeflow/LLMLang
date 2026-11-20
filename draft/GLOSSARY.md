# LLMLang Draft Glossary

**Status:** Terminology proposal for the draft specification  
**Scope:** Semantic identity, operation calls, implementation identity, and contract-based implementation discovery.

This glossary establishes names for concepts that must remain distinct in the language model. Definitions are proposed terminology, not yet normative language semantics.

## Core terms

### Contract

An immutable semantic value that specifies caller-observable behavior promised at a boundary. Depending on the semantic profile, it may constrain admissible inputs and initial states, outcomes, state transitions, effects, failures, termination/liveness, resource bounds, and concurrency observations. A Contract is a semantic object; a declaration that an operation or callee provides it is a binding/claim, not proof of conformance.

### Contract Content Hash (generic `ContractHash`)

The content identity of one exact immutable Contract value. This generic descriptive term is used by the RT-20 prototype for caller-required and callee-provided Contract references. It is not an alias for `OpHash` or `CCHash`, and the canonical hash envelope and domain separation remain open.

### Operation

A semantically defined callable capability with an explicit interface and contract. An operation describes what a caller may rely on; it does not, by itself, identify the code that executes.

### Operation Hash (`OpHash`)

The content identity of one exact semantic version of an operation. It identifies the operation definition, including its externally relevant interface, contract, and any semantic context that changes the meaning of the call.

An `OpHash` is the semantic call target. It is not the identity of a particular implementation.

### Implementation

One concrete realization of an operation. An implementation has a specific immutable semantic body and explicit semantic dependencies. Different implementations may satisfy the same operation contract.

### Implementation Hash (`ImplHash`)

The content identity of one exact implementation artifact, including its canonical body and all hash-relevant semantic dependencies.

An `ImplHash` identifies one concrete implementation, not a family of interchangeable implementations. A change to the implementation or to a hash-relevant dependency produces a different `ImplHash`.

### Conformance Class

The semantic set of all implementations that satisfy a specified operation contract under specified compatibility constraints.

A conformance class is defined by:
- the exact `OpHash` whose contract must be satisfied;
- applicable target and environment constraints;
- any additional compatibility conditions that affect whether an implementation is admissible.

Conceptually:

`ConformanceClass(OpHash, Constraints) = { Impl | conforms(Impl, OpHash, Constraints) }`

A conformance class is not merely a list of implementations currently known to a registry. It denotes the complete set defined by its conformance predicate, including implementations that may be discovered or published later.

### Conformance Class Hash (`CCHash`)

The content identity of a conformance class definition. It is computed from the canonical, typed definition of the class: its `OpHash`, constraints, and conformance criteria.

A `CCHash` identifies the rule that determines membership in the class; it does not hash an enumeration of currently discovered implementations. It is not the hash of a Contract object alone: the class definition includes an exact `OpHash`, constraints, and conformance criteria. Therefore, discovering another conforming implementation does not change the `CCHash`.

Changing the required operation semantics, target constraints, or conformance criteria creates a different conformance class and therefore a different `CCHash`.

## Related terms

### Candidate Implementation

An implementation discovered as a possible member of a conformance class, but whose membership has not yet been established. Similar signatures, matching names, or partial contract overlap are sufficient only for candidate discovery, not for conformance.

### Conforming Implementation

An implementation whose membership in a particular conformance class has been established by the required evidence. Conformance is always relative to a specific `CCHash`; an implementation is not simply “conforming” in the abstract.

### Candidate Implementation Set

A finite result of a particular discovery operation: the implementations found by a search at a given time under a given search scope. It is an operational search result, not the conformance class itself.

If a reproducible identity for such a snapshot is needed, it may have a separate `CandidateSetHash` computed from the canonical sorted member `ImplHash` values and search-scope metadata. This hash must not be confused with `CCHash`: new discoveries can change a candidate-set snapshot without changing the conformance class.

### Conformance Evidence

Tests, proofs, refinement arguments, or other accepted evidence establishing that a particular `ImplHash` belongs to a particular `CCHash`. Evidence is bound to exact implementation, operation, constraints, assumptions, and relevant tool versions.

## Identity and substitution rules

1. `ContractHash`, `OpHash`, `ImplHash`, and `CCHash` identify different kinds of objects and must never be used interchangeably.
2. A direct implementation call or binding that pins a concrete implementation names its `ImplHash` explicitly.
3. A call that names an `OpHash` specifies the required operation semantics. An implementation may serve that call only if it is established as conforming to the corresponding conformance class and applicable constraints.
4. Contract-based search discovers candidates; it does not itself establish conformance and does not silently rewrite a pinned `ImplHash` or `OpHash`.
5. A runtime or optimizer may choose among conforming implementations only where the call/binding semantics permit such selection. The selection must preserve the exact operation semantics requested by the call.
6. A matching `ImplHash` proves content identity, not conformance. A matching `CCHash` proves identity of the membership definition, not that any particular implementation belongs to it.
7. Conformance evidence for one `CCHash` does not automatically apply to another class, even if their contracts appear similar.

## Naming summary

| Concept | Term | Hash / identity |
|---|---|---|
| One exact immutable Contract semantic value | Contract | Generic `ContractHash` |
| One exact semantic operation version | Operation | `OpHash` |
| One concrete implementation | Implementation | `ImplHash` |
| The complete set defined by conformance to an operation under constraints | Conformance Class | `CCHash` |
| A finite search result at a particular time | Candidate Implementation Set | Optional `CandidateSetHash` |
| Evidence that one implementation belongs to one class | Conformance Evidence | Evidence identity, bound to `ImplHash` and `CCHash` |

## RT-20 terminology boundary

RT-20 stores the caller-required Contract hash at each call site and resolves the callee-provided Contract through the exact callee declaration. Those are generic Contract-object identities, not `CCHash` values. Exact Contract identity does not establish behavioral compatibility between distinct Contract versions. The proposed compatibility direction and evidence requirements are documented in [RT-20 Contract Identity and Compatibility](../research/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md).

## Open points

The following details remain for the specification to define:
- canonical encoding and domain separation for `OpHash`, `ImplHash`, and `CCHash`;
- the exact conformance relation and supported evidence strengths;
- how target constraints and environmental assumptions are represented;
- whether class membership may be established by formal proof only, or also by explicitly scoped testing/refinement evidence;
- when dynamic implementation selection is permitted and how its result is recorded for reproducibility.
