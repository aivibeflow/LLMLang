# Research Scenario 14: Formal Behavioral Contracts and Implementation Refinement

**Status:** Research / exploratory; not normative.  
**Date:** 2026-11-16  
**Predecessors:** Scenarios 10, 12, 13; Dependency Graph Prototype 01.

## Executive conclusion

LLMLang should not define implementation substitutability as signature equality, type compatibility, matching examples, or a declared `implements` edge. The relevant question is behavioral:

> For every input and initial state admitted by the contract, can the implementation exhibit only behavior that the contract permits, at the contract's defined observation boundary?

A useful general model is **observable trace refinement**. Let `Traces(C, x, s)` be the set of observable traces permitted by contract `C` for input `x` and abstract initial state `s`; let `Traces(I, x, s)` be the traces implementation `I` can produce. A safety-oriented refinement condition is:

`Traces(I, x, s) ⊆ Traces(C, x, s)`

for every admissible `x` and `s), with a proved relation between concrete implementation state and abstract contract state.

This permits an implementation to be more deterministic than the contract, while forbidding behavior outside the contract. It does not mean that any weaker or underspecified contract is useful: an overly weak contract can admit implementations with materially different business behavior.

**Preliminary recommendation:** define contracts in terms of caller-observable outcomes, state transitions, effects, failures, and explicitly promised temporal properties; prove implementation refinement against exact immutable contract and implementation hashes; store proof evidence separately from semantic values; and require a small independent proof checker or trusted verifier boundary. Keep bounded testing and finite model checking distinct from unbounded proof.

## 1. Why type compatibility is insufficient

A function signature such as `Money -> Money` says little about business behavior. Two implementations may have identical types and differ in:
- tax rate, rounding, or currency conversion;
- state they modify;
- external events they emit;
- exceptions and failure conditions;
- ordering or concurrency behavior;
- termination, resource, or timing guarantees.

For example, two tax calculators can both return `Money`, but one applies a 15% rate and another applies 20%. They are not interchangeable merely because both satisfy the same type signature.

A behavioral contract must constrain all differences that a permitted caller can observe and that matter to the caller's requirements.

## 2. Behavioral substitutability and refinement

### 2.1 Observational boundary

A contract must define what counts as observable. Candidate observations include:
- returned values and their types;
- normal return versus typed failure/exception;
- externally visible state before and after a call;
- emitted events, messages, files, database writes, and network calls;
- ordering and multiplicity of externally visible effects;
- concurrency-visible histories and synchronization behavior;
- termination or permitted divergence;
- resource/timing bounds, but only when explicitly part of the contract.

Internal data structures, local variable choices, algorithms, and private helper calls are not observable unless they affect a declared observation.

The observation boundary is part of contract semantics. Two implementations cannot be declared equivalent until the boundary is fixed.

### 2.2 Trace refinement

A trace is an ordered sequence of observable events plus a terminal outcome (return, typed failure, or divergence). The contract denotes a set of allowed traces rather than one expected output.

For every contract-admissible input and initial abstract state:

`Traces(implementation) ⊆ Traces(contract)`

This is a refinement relation: the implementation may choose fewer behaviors than the contract allows, but may not introduce a forbidden behavior.

Examples:
- Contract permits either `return:approved` or `return:review`; implementation always returns `return:approved`. This may be a valid refinement.
- Contract permits only `write:invoice.total; return:ok`; implementation also emits `email.sent`. This is not a refinement unless the email effect is allowed.
- Contract requires termination; implementation diverges. This is not a refinement.
- Contract permits divergence and termination, but caller needs eventual completion. The contract is too weak for that caller's requirement; the caller must require the liveness property.

Trace inclusion is a useful unifying model, but infinite traces, fairness, liveness, and concurrent histories need a precise semantic treatment. A finite list of events is not by itself a complete model of a concurrent or reactive system.

### 2.3 State abstraction and simulation

The contract often describes abstract state while the implementation uses concrete state. The proof needs an abstraction relation `R(concrete_state, abstract_state)`.

At minimum, the verifier must establish:
1. initial concrete and abstract states correspond under `R`;
2. every concrete transition preserves the relation and corresponds to permitted abstract behavior;
3. observable labels/effects match the contract's allowed traces;
4. normal and exceptional terminal states satisfy the contract;
5. any promised termination or liveness property is established under stated assumptions.

The abstraction relation itself is part of the proof input and must be pinned by hash. It must not be accepted as an unchecked assertion supplied by the implementation author.

## 3. Contract clauses needed by LLMLang

A candidate contract IR should include the following independent dimensions.

### 3.1 Domain and preconditions

- input types and refinement constraints;
- admissible initial abstract states;
- explicit precondition;
- environmental assumptions;
- whether inputs are finite, unbounded, symbolic, or dependent on external state.

For safe substitutability, the implementation must accept at least the inputs the contract promises to callers. In Hoare-style terms, a candidate implementation must not strengthen the caller-facing precondition. If the contract permits a call under `P_C`, the implementation must be valid whenever `P_C` holds.

### 3.2 Outcomes and postconditions

- return-value constraints;
- abstract state postconditions;
- typed exceptional outcomes;
- outcome-specific postconditions;
- invariants that must hold on all exit paths.

The implementation's behavior must imply the contract's postconditions. A stronger postcondition is generally compatible with safety refinement; a weaker one is not.

### 3.3 Frame and effect conditions

- permitted state writes;
- permitted external effects;
- effect ordering and multiplicity constraints;
- permitted reads/dependencies where they affect concurrency or stability;
- ownership/aliasing restrictions;
- effect capabilities required to execute.

A frame condition is not a documentation hint. It constrains what an implementation may mutate. Dafny and JML both expose frame/read/write specifications as first-class verification concepts.

### 3.4 Failure semantics

- declared error variants;
- conditions under which each error may occur;
- whether errors are recoverable;
- state/effect guarantees on failure;
- forbidden failure modes.

An implementation must not add an observable failure mode that the contract excludes, nor silently convert a specified failure into success if callers rely on that failure.

### 3.5 Termination, liveness, and resource bounds

These should be explicit, not inferred:
- must terminate;
- may diverge;
- eventual progress under assumptions;
- upper bounds on steps, memory, or external operations;
- deadlines or latency guarantees where the runtime can enforce or verify them.

A total-function contract and a streaming-service contract have different termination semantics. Dafny's `decreases` mechanism is a concrete example of explicit termination obligations; it also distinguishes methods that are permitted to diverge.

### 3.6 Concurrency and histories

For concurrent operations, a simple sequential input/output contract is insufficient. Contracts may need to specify:
- allowed operation histories;
- linearizability or another consistency model;
- atomicity boundaries;
- ordering constraints;
- permitted interleavings;
- isolation and interference assumptions.

Do not claim substitutability across concurrent implementations based only on single-call postconditions.

## 4. Proof obligations for a candidate implementation

A verifier can decompose refinement into obligations. The exact proof rules depend on LLMLang's execution semantics, but a useful starting list is:

| Obligation | Required property |
|---|---|
| Type/domain compatibility | Implementation accepts every contract-admissible input |
| Precondition compatibility | Implementation does not require more than the contract promises |
| Postcondition refinement | Every implementation result satisfies the contract postcondition |
| State abstraction | Concrete state transitions preserve the abstraction relation |
| Frame/effect refinement | Writes and external effects stay within contract permissions |
| Failure refinement | Exceptions/errors are within the contract's declared outcomes |
| Termination/liveness | Any must-terminate or progress promise is proved |
| Concurrency refinement | Observable histories satisfy the specified consistency model |
| Assumption closure | Every environmental assumption is explicit, pinned, and justified |
| Translation/runtime soundness | The verified semantics corresponds to the code that is actually executed |

A proof of only the postcondition is not a proof of full substitutability if effects, errors, concurrency, or termination are observable.

## 5. Proof evidence and independent verification

A conformance record should bind the proof to exact inputs:

- contract Content Hash;
- implementation Content Hash;
- abstraction relation hash;
- proof-obligation set/hash;
- proof artifact/certificate hash;
- verifier kernel identity and version;
- frontend/compiler/IR translation identity;
- relevant dependency closure;
- assumptions and environment model hashes;
- policy/configuration hash;
- result status and scope.

The proof result must not be stored inside the immutable semantic value as mutable metadata. It is a separate immutable evidence record, keyed by exact proof inputs. This follows the prototype's existing separation between semantic values and context-scoped relations, but conformance evidence deserves its own typed record because it affects trust and reuse.

### 5.1 Small trusted checker

Preferred architecture:
1. A frontend translates source and contract into a defined verification IR.
2. A prover generates a proof certificate.
3. A small checker validates the certificate against exact IR and contract hashes.
4. The evidence record stores the checker identity, certificate hash, and assumptions.
5. Runtime/build selection accepts only evidence meeting the applicable policy.

The LLM may propose the contract, implementation, invariants, abstraction relation, or proof. It must not be trusted to certify its own work. The checker and any compiler/translation component in the trusted computing base must be identified explicitly.

A proof certificate is useful only if the checker validates it soundly. If the system trusts a large unverified compiler, solver, or runtime, that trust boundary must be disclosed rather than hidden behind a PROVEN label.

### 5.2 Status vocabulary

Keep statuses distinct:
- `PROVEN`: a sound verifier established the stated obligations for the exact inputs and assumptions;
- `DISPROVEN`: a valid counterexample or failed proof obligation demonstrates nonconformance;
- `UNKNOWN`: the verifier could not decide or the model/proof is incomplete;
- `NOT_CHECKED`: no verification was attempted;
- `BOUNDED_PASS`: all explored bounded cases passed, but this is not an unbounded proof;
- `ERROR`: the verification process failed operationally or produced invalid evidence.

Only `PROVEN` can satisfy a policy requiring formal conformance. `BOUNDED_PASS`, tests, simulations, and LLM review are useful evidence but cannot be silently promoted to proof.

## 6. Counterexample-driven diagnostics

When refinement fails, the verifier should return a compact witness:
- exact input and abstract initial state;
- event trace or state transition sequence;
- first divergence from the contract;
- violated obligation;
- relevant source/IR locations;
- assumptions and hashes used in the check.

This gives the LLM a narrow repair target without asking it to reread the whole project. A counterexample is also a regression-test candidate, but passing that test later does not by itself establish the full proof.

## 7. What existing tools contribute

### Liskov and Wing: behavioral subtyping

The foundational paper defines substitutability in terms of behavior visible to programs using the supertype abstraction, and discusses invariants and history properties. This supports a semantic rather than syntactic notion of implementation compatibility.

Source: https://www.cs.tufts.edu/~nr/cs257/archive/barbara-liskov/behavioral-subtyping.pdf

### Dafny: preconditions, postconditions, frames, termination

Dafny specifications include preconditions, postconditions, read/write frames, and termination metrics. Its reference explains that these clauses are verification inputs, not comments. This is a useful source of contract dimensions for LLMLang.

Sources:
- https://dafny.org/dafny/DafnyRef/DafnyRef
- https://dafny.org/dafny/OnlineTutorial/Termination
- https://dafny.org/dafny/OnlineTutorial/guide

### JML / OpenJML: exceptional behavior and frame conditions

JML describes normal and exceptional postconditions and explicit assignable/frame clauses. Its documentation emphasizes that frame conditions constrain memory locations a method may write. This is particularly relevant because return-value equality alone misses state mutation and external effects.

Sources:
- https://www.openjml.org/tutorial/FrameConditions
- https://www.openjml.org/tutorial/Postconditions
- https://www.openjml.org/documentation/features.shtml

These tools are evidence for established specification techniques, not a ready-made LLMLang semantic model. LLMLang still needs a unified contract IR, exact hash binding, evidence lifecycle, and multi-backend trust model.

## 8. Finite trace prototype

Added an experimental `src/contract_model.py` and tests.

The prototype:
- represents a finite input domain;
- represents allowed contract traces and modeled implementation traces;
- treats return values, failures, effects, and divergence as observable event labels;
- checks whether every implementation trace is contract-allowed;
- allows deterministic implementations to refine nondeterministic contracts;
- distinguishes `PROVEN`, `DISPROVEN`, and `UNKNOWN`.

Crucial limitation: `PROVEN` means exhaustive refinement of two explicitly complete finite models only. It does **not** prove that arbitrary source code faithfully corresponds to the implementation model, nor that the model captures the human's intended business rule. An incomplete model yields `UNKNOWN`, not success.

This is a deliberately small experiment to validate the relation and status handling, not the final verifier or contract language.

## 9. Implications for bindings and caller-driven evolution

Combining this result with Scenario 13:

1. A caller depends on a behavioral contract, not a concrete implementation hash.
2. A binding may select only an implementation with acceptable conformance evidence for that exact contract hash.
3. Replacing an implementation with a proven refiner need not change the caller's semantic hash.
4. The binding/build/deployment/execution identities still change where the implementation choice is consumed.
5. If the business rule changes (tax rate, eligibility rule, fee policy), that change belongs in the caller's required semantics or an explicit policy input, not in a purported implementation swap.
6. If the contract changes, old proof evidence does not automatically transfer. New contract hash means new conformance obligations.
7. If the implementation changes, evidence tied to the old implementation hash is stale for the new value.
8. If a compiler/backend/runtime changes, proof reuse requires evidence that the new translation/execution path preserves the verified semantics.

This gives a precise version of the project principle: the call site determines the required business meaning; the implementation must prove that it refines that meaning.

## 10. Preliminary recommendations

Research direction, not normative:

1. Use behavioral refinement, not signature equality, as the criterion for implementation substitutability.
2. Define an explicit observation boundary for every contract.
3. Model return values, state changes, effects, failures, and promised temporal/concurrency behavior.
4. Express preconditions, postconditions, frame conditions, and termination/liveness obligations separately.
5. Use abstract-state relations when implementation representation differs from contract state.
6. Require a proof record pinned to exact contract, implementation, dependencies, assumptions, and verifier identity.
7. Prefer proof certificates checked by a small independent kernel; disclose the trusted computing base.
8. Never equate bounded testing, finite exploration of an incomplete model, or LLM review with unbounded proof.
9. Keep business-policy values explicit and caller-visible.
10. Preserve `UNKNOWN` and `NOT_CHECKED` as non-success states.
11. Treat contract changes and implementation changes as separate impact events.
12. Keep the prototype experimental until a formal IR and source-to-verification-IR soundness story exist.

## 11. Open questions

- What is LLMLang's canonical observable event algebra?
- Should effects be typed capabilities, trace events, state transitions, or a combination?
- Which formal semantics should define concurrency and asynchronous operations?
- How should probabilistic behavior be specified and refined?
- What proof-certificate format and small checker architecture are practical?
- How can source-to-IR and backend translation correctness be established across Rust, Go, C++, and other targets?
- How should contracts express resource and timing guarantees without making proofs intractable?
- Which obligations are mandatory for every function, and which are conditional on the function's declared effects and execution model?
- How can natural-language business requirements be linked to formal predicates without pretending that formal proof validates the truth of human intent?
