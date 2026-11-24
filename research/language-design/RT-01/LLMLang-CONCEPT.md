# LLMLang — An AI-Native Programming Language Concept

The Russian-language companion is [LLMLang-CONCEPT.ru.md](LLMLang-CONCEPT.ru.md). This navigation link does not establish translation parity; the two texts remain separate documents.

**Status:** Concept document  
**Version:** 0.1  
**Working language name:** `LLMLang`  
**Working name of the internal representation:** Semantic Program Graph (SPG)

> LLMLang is an experimental concept for a programming language and development environment designed from the outset for programs to be created by large language models (LLMs), with independent, machine-based verification of the correctness of their results.

---

## 1. Vision and Goals

### 1.1. Core Idea

LLMLang is not a conventional programming language with an AI assistant. It is an AI-native language: its programming model, internal representation, development tools, and compilation architecture are designed from the outset for an LLM to often be the primary author of programs, while humans specify intent, requirements, constraints, and make architectural decisions.

The guiding principle:

**Do not make the LLM remember the rules. Make the language and tooling enforce them.**

The language should reduce the likelihood of errors arising when generating and modifying large amounts of code:
- omitted or incorrectly implemented preconditions;
- violated invariants;
- inconsistencies between interfaces and modules;
- unhandled error cases and states;
- implicit side effects;
- concurrency and memory-management errors;
- outdated tests and proofs following requirements changes;
- regressions introduced by refactoring.

### 1.2. Primary Goals

1. Make intent, requirements, contracts, constraints, and states first-class constructs.
2. Represent a program as a typed structure, not merely as text.
3. Provide deterministic verification independent of the LLM.
4. Keep changes local and analyze their impact through the dependency graph.
5. Support both formal verification and testing.
6. Avoid coupling the language to any single LLM or model.
7. Support conventional execution targets: VMs and native machine code.
8. Avoid requiring comprehensive formal design for every small utility.

### 1.3. Non-Goals

- Do not attempt to express every possible program declaratively.
- Do not use natural language as the sole formal syntax.
- Do not treat an LLM response as proof of correctness.
- Do not promise provable freedom from bugs in arbitrary programs.
- Do not make the LLM part of the trusted execution chain.
- Do not require formal proofs where they are practically unattainable or unjustifiably expensive.

---

## 2. Two Levels of Use

The concept combines two approaches:

- **LLM-friendly:** a strict, unambiguous language with a strong type system, contracts, and predictable semantics.
- **LLM-native:** programs are created and modified as structured models, with textual code serving as one representation of those models.

The preferred direction is LLM-native. However, the language should remain suitable for conventional development and human reading.

---

## 3. Program Model: Semantic Program Graph

### 3.1. Programs as Graphs of Objects

The primary program representation should not be a conventional AST but a typed graph — the **Semantic Program Graph (SPG)**.

An AST describes the syntactic structure of source text well, but is insufficient as the central model for:
- contracts;
- effects;
- invariants;
- dependencies;
- access permissions;
- tests;
- proofs;
- provenance and change history.

The SPG consists of typed objects with stable identifiers and explicit relationships.

Example operation:

```text
Operation#transfer
    ├── Input#source
    ├── Input#destination
    ├── Input#amount
    ├── Contract#preconditions
    ├── Effect#debit
    ├── Effect#credit
    ├── Contract#postconditions
    ├── Error#insufficient_funds
    ├── Test#transfer_success
    └── Proof#balance_conservation
```

Each object has:
- a unique ID;
- a kind and type;
- semantic content;
- references to related objects;
- a Stable ID and the Content Hash of its current immutable state;
- provenance information;
- dependencies and reverse dependencies.

### 3.2. Changes as Operations on Objects

The LLM should primarily modify specific objects rather than replace large sections of text.

Example:

```text
UPDATE Contract#transfer.preconditions:
    ADD source.status == Active
```

Such an operation must have unambiguous semantics, be checked for conflicts, and leave an auditable change history.

### 3.3. Representations and Serialization

Two primary representations are envisaged:

1. **Canonical machine representation** — a structured, unambiguous SPG format. Binary serialization is possible.
2. **Human-readable representation** — a DSL for viewing and editing objects.

JSON may serve as a convenient intermediate or debugging representation, but is not necessarily the most compact canonical format.

Text must not be the sole source of truth: after parsing, it becomes an SPG, from which textual representations can be generated.


### 3.4. Content-addressed identity and immutable states

Each semantic SPG entity SHOULD have two distinct identifiers:

- **Stable ID** identifies the logical entity across its lifetime. Renaming or changing the entity does not change this ID.
- **Content Hash** identifies one exact immutable state of that entity. Any change to the entity's canonical semantic content or to a hash-relevant dependency produces a different Content Hash.

The Content Hash SHOULD be computed independently for fine-grained entities (for example, individual types, operations, expressions, contracts, effects, tests, and proofs), not only for modules or packages. Larger structures are represented by hashes that commit to their own canonical content and the hashes of their hash-relevant outgoing dependencies. This forms a Merkle DAG over the semantic dependency relation.

Conceptually:

```text
ContentHash(node) =
    Hash(
        domain_separator,
        node_kind,
        canonical_semantic_content,
        sorted_hash_relevant_edges_and_target_hashes
    )
```

The exact canonical encoding and hash algorithm are implementation decisions. The initial implementation SHOULD use a cryptographic hash such as SHA-256, include the algorithm identifier in the digest representation, and support algorithm agility. Hash inputs MUST use domain separation so that different entity kinds or hash purposes cannot be confused.

Canonicalization MUST ensure that semantically irrelevant presentation differences—such as whitespace, formatting, source locations, display names, timestamps, authorship, and provenance—do not change the Content Hash. These attributes remain separately addressable metadata. The hash represents canonical structured content and declared graph edges, not general semantic equivalence of arbitrary programs.

Hash-relevant edges MUST be typed. A Specification dependency should commit to the target Specification state; an Implementation dependency should commit to the target Implementation state. A consumer depending only on a public Specification should not be forced to change its own semantic hash merely because a provider changes an internal Implementation that still satisfies the same Specification.

Only the hash-relevant dependency relation must be acyclic. If ordinary SPG relations contain cycles, they MUST be excluded from recursive hash edges or represented through an explicitly defined canonical group/root object. A recursive hash definition over a cycle is not valid.

SPG entities and states addressed by Content Hash are immutable. An edit creates a new state with a new hash while preserving the Stable ID. Parent hashes change only when a hash-relevant child or local semantic content changes. Unaffected branches retain their hashes and can be reused or cached.

An accepted project snapshot SHOULD be identified by a root hash (or a small set of layer-root hashes) that commits to the exact reachable semantic graph. Provenance, approvals, signatures, and timestamps SHOULD be linked to that snapshot but excluded from its semantic root hash unless they themselves are intentionally part of program semantics.

This is content addressing, not a claim that equal hashes prove arbitrary behavioral equivalence. A hash proves identity of the canonical encoded graph under the selected cryptographic algorithm; correctness and compatibility still require independent verification.

---

## 4. Three Logical Program Layers

The SPG is proposed to be divided into three related but independently existing layers.

### 4.1. Specification Graph

Describes **what the program must do**:
- requirements;
- preconditions and postconditions;
- invariants;
- constraints;
- state models;
- permitted errors;
- safety properties.

### 4.2. Design Graph

Describes **how the program should be structured**:
- components;
- interfaces;
- dependencies;
- architectural boundaries;
- algorithms;
- data structures;
- allocation of responsibilities.

### 4.3. Implementation Graph

Describes **how the program is implemented**:
- expressions;
- instructions;
- control flow;
- memory operations;
- calls;
- runtime operations;
- concrete algorithm implementations.

### 4.4. Relationships Between Layers

Expected conformance relationships:

```text
Specification Graph
        ↑ satisfies
Design Graph
        ↑ implements
Implementation Graph
```

In practice, the implementation must conform to the design decisions, and those decisions must conform to the specification.

These relationships should be explicit and verifiable to the extent possible.

### 4.5. Whether Layers Are Mandatory

The preferred approach is for the layers to be independent and optional.

- A small program may be created directly in the Implementation Graph.
- A more complex program may add a Design Graph.
- A critical or large system may require a Specification Graph and conformance of all lower layers.

Project policy may establish a minimum required level of detail. This avoids overburdening simple tasks while retaining rigorous discipline for large systems.

---

## 5. Contract-Oriented Programming

Contracts are part of the language's semantics, not comments or external documentation.

Core elements:
- **Preconditions** — conditions that must hold before execution.
- **Postconditions** — guarantees that must hold after execution.
- **Invariants** — properties preserved throughout a defined lifecycle.
- **Effects** — permitted side effects.
- **Errors** — explicitly declared error outcomes.

Example:

```text
operation transfer:
    input:
        source: Account
        destination: Account
        amount: PositiveMoney

    requires:
        source != destination
        source.status == Active
        destination.status == Active
        source.balance >= amount

    effects:
        source.balance -= amount
        destination.balance += amount

    ensures:
        total_balance == old(total_balance)
        source.balance >= 0
        destination.balance >= 0

    atomic:
        true

    failure:
        InsufficientFunds
```

The compiler and verification tools must check implementations against their contracts. If proof is impossible, the outcome must be explicitly marked as unknown or unverified rather than successful.

### 5.1. Public interfaces and implementation conformance (candidate)

A public interface is a stable, namespace-qualified named semantic entity with immutable revisions, a typed signature, and public contracts. It is separate from any concrete implementation. A consumer can depend on the exact public revision; an explicit versioned binding selects an exact implementation for a build or execution context.

An implementation has its own contract. Verification must establish both that the implementation body satisfies its own contract and that its contract refines the public contract, under aligned semantics and checked assumptions. A provider may accept a wider input domain and supply stronger guarantees, but must not impose stronger caller obligations or violate publicly promised effects, errors, ownership, progress or resource bounds. A declared binding or matching signature is not proof. Missing or unsupported evidence remains explicitly unverified.

A compatible provider replacement may preserve modular caller proofs while invalidating provider-dependent execution evidence. Changes to public semantics create immutable new revisions; compatibility and migration are explicit. This proposal extends the existing operation/implementation and contract refinement research; it does not replace exact hash-based invocation or settle the identity scheme.

See [Public interfaces and contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md) for the candidate architecture, diagrams, proof obligations, alternatives and planned benchmarks. No normative language decision is implied.

---

## 6. Type System

### 6.1. Strict Static Typing

A strict static type system with minimal implicit behavior is proposed.

Desirable properties:
- no implicit type conversions;
- no implicit conversion from nullable to non-null;
- exhaustive handling of algebraic types;
- explicit errors;
- typed states;
- support for refinement types;
- explicit resource ownership.

### 6.2. Algebraic Types

```text
type UserLookup =
    Found(User)
    NotFound
    Forbidden
```

A `match` must be exhaustive. Adding a new type variant must identify every location where handling becomes incomplete.

### 6.3. Refinement Types

A type may be refined by a predicate:

```text
PositiveMoney = Money where value > 0
```

This moves verifiable constraints into the type system and eliminates some invalid states before execution.

### 6.4. Typed States

An entity's state may be reflected in its type:

```text
Account<Active>
Account<Frozen>
Account<Closed>
```

A withdrawal operation accepts only `Account<Active>`.

A state transition changes the entity's typed representation. The specific ownership model and type changes during transitions require further investigation.

### 6.5. Structural Identity, Representation Requirements, and ABI

A separate architectural proposal treats a type as an extension of structural identity with representation requirements. Type and field names, as well as the semantic purpose of data, are not part of structural identity. Semantic expectations are specified by the consumer in its contract.

The proposed compilation pipeline distinguishes:
- **Identity** — the canonical data structure and its Identity Hash;
- **Type** — Identity plus canonical representation requirements and a Type Hash;
- **Layout** — the physical layout computed for a target ABI and its Layout Hash;
- **Function ABI** — the argument-passing and result-return contract computed for a particular function and ABI.

In source code, developers work with Types and function declarations. Layout and Function ABI are computed by the compiler for the selected target; the Layout Engine is the single source of truth for layout. Unsatisfiable requirements must produce diagnostics rather than being silently weakened.

The ABI of an external function is specified at the function declaration boundary (for example, the illustrative `extern "C"`), not globally on every type. A type may nevertheless carry C-compatible representation, alignment, and packing requirements. The concrete layout and aggregate-passing convention are resolved according to the target ABI profile.

The full model, hash boundaries, C interoperability, and open questions are documented in the [RT-09 proposal on structural type identity, layout, and C ABI](../../compiler-and-translation/RT-09/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md). This proposal is not approved normative semantics.

---

## 7. States and Finite-State Machines

Finite-state machines should be first-class language constructs.

Example:

```text
entity Job:
    states:
        draft
        ready
        running
        done
        failed

    transitions:
        draft -> ready
        ready -> running
        running -> done
        running -> failed

    immutable_when:
        state == done
```

The compiler must reject invalid transitions.

The state model may be linked to types, contracts, permissions, and resource lifecycles. It remains necessary to define which checks are performed statically and which require runtime checks.

---

## 8. Memory Ownership and Concurrency

The proposal is to use ownership and borrowing concepts, including lessons from Rust, while investigating a model that is easier for LLMs to analyze and generate.

Required guarantees:
- no use-after-free;
- no double-free;
- no data races;
- no unauthorized shared mutation;
- explicit management of resource lifetimes;
- explicit handling of cancellation and errors in concurrent tasks.

Illustrative syntax:

```text
resource Account:
    ownership: exclusive

operation update:
    borrow_mut account
    ...
```

Concurrency should be expressed explicitly:

```text
parallel:
    task calculate_a
    task calculate_b

join:
    calculate_a
    calculate_b
```

The order of dependent operations must be defined. Deterministic execution should be provided wherever it is possible without unacceptable performance loss.

---

## 9. Effect System and Capabilities

### 9.1. Explicit Effects

Functions should be pure by default. External interactions require effect declarations.

```text
operation load_user:
    effects:
        database.read
        network.request
```

Implicit:
- global state;
- network access;
- filesystem operations;
- database writes;
- process launches;
- modifications to external resources

are not permitted.

### 9.2. Transitive Effects

If operation A calls B, and B has the `network.write` effect, then A must explicitly authorize that effect or use a strictly defined delegation mechanism.

### 9.3. Capabilities

Permissions to perform dangerous actions may be represented as capabilities. Possession of a capability must be explicitly tied to the execution context and must never arise implicitly.

This model requires a separate security specification and threat model.

---

## 10. Built-in Tests and Verifiable Properties

Testing should be part of the program model and linked to requirements and contracts.

### 10.1. Property-Based Testing

```text
property balance_never_negative:
    for_all account:
        account.balance >= 0
```

### 10.2. Scenario Tests

```text
scenario transfer:
    given:
        source.balance = 100
        destination.balance = 50

    when:
        transfer(source, destination, 30)

    then:
        source.balance == 70
        destination.balance == 80
```

### 10.3. Requirements Traceability

```text
requirement R-001:
    account balance cannot be negative

    verified_by:
        property balance_never_negative
        scenario insufficient_funds
```

Tests, properties, and proofs should be standalone SPG objects.

Changing a requirement or contract should identify tests requiring review. One test may verify multiple requirements.

### 10.4. Separation of Verification Methods

The following must be distinguished:
- formal proofs;
- static checks;
- unit tests;
- integration tests;
- scenario tests;
- property-based testing;
- fuzzing;
- dynamic runtime checks.

The existence of a test is not, by itself, a formal proof that a property holds for all inputs.

---

## 11. Declarative Constraints and Automatic Implementation

One research direction is to describe constraints and guarantees while letting the LLM propose an implementation.

Example:

```text
component OrderProcessor:

    guarantees:
        order_is_processed_at_most_once
        payment_and_order_are_consistent
        failed_payment_does_not_create_order

    constraints:
        latency < 100ms
        memory < 64MB

    implementation:
        automatic
```

Proposed process:
1. Formalize the guarantees and constraints.
2. Check them for consistency and sufficiency.
3. Propose an architecture and algorithm.
4. Generate the implementation.
5. Run static and formal checks.
6. Run tests and measurements.
7. Reject any implementation that fails to meet the established criteria.

`implementation: automatic` means generating an implementation candidate, not magically having the compiler solve an arbitrary problem. The candidate remains untrusted until verified.

---

## 12. Compiler and Overall Architecture

Rather than a conventional monolithic compiler, a multi-stage translation and verification system is proposed.

```text
Intent / Specification
          |
          v
Semantic Program Graph
          |
          v
Structural Validation
          |
          v
Type Checking
          |
          v
Effect Checking
          |
          v
Contract Verification
          |
          v
Dependency Analysis
          |
          v
Lowering / Optimization
          |
       +--+--+
       |     |
       v     v
    Native   Bytecode
       |     |
       +--+--+
          |
          v
        Runtime
```

The LLM creates and modifies program proposals. The checking subsystems must be deterministic and independent of the LLM.

### 12.1. Structural Validator

Checks:
- that all references exist;
- object type correctness;
- ID uniqueness;
- required fields;
- whether cycles are permitted;
- conformance of the graph to the language schema.

### 12.2. Type Checker

Checks static type correctness, including algebraic, refinement, and state types.

### 12.3. Effect Checker

Checks that an implementation uses only declared effects and capabilities. Analysis must account for transitive calls.

### 12.4. Contract Verifier

Checks contract satisfaction. For suitable problems, it may construct verification conditions and pass them to an SMT solver.

Example:

```text
requires:
    balance >= amount
    amount >= 0

ensures:
    balance - amount >= 0
```

Simplified mathematical obligation:

\[
balance \ge amount \land amount \ge 0
\Rightarrow balance - amount \ge 0
\]

Results must have at least the following statuses:
- `PROVEN` — the property has been proved;
- `DISPROVEN` — a counterexample has been found;
- `UNKNOWN` — neither proof nor disproof was obtained;
- `NOT_CHECKED` — verification was not performed.

`UNKNOWN` and `NOT_CHECKED` must not count as successful verification.

### 12.5. Dependency Analyzer

Tracks dependencies between:
- requirements;
- contracts;
- types;
- architectural objects;
- algorithms;
- implementations;
- tests;
- proofs.

Changing an object must invalidate dependent verification results if they are no longer guaranteed to be current. This forms the basis for incremental compilation.

---

## 13. Interaction Between the LLM and the Compiler

Conventional model:

```text
LLM -> source code -> compiler -> errors
```

Proposed model:

```text
LLM -> structured proposal -> compiler -> verification feedback
```

The LLM creates typed objects or proposals for graph changes. The compiler checks them and returns structured diagnostics.

Example:

```text
RESULT: REJECTED

ERROR E-104:
    Postcondition not satisfied.

LOCATION:
    Operation#transfer / Effect#credit

COUNTEREXAMPLE:
    source.balance = 100
    destination.balance = 50
    amount = 30

EXPECTED:
    total_balance = 150

ACTUAL:
    total_balance = 120
```

Diagnostics should be:
- associated with SPG objects;
- machine-readable;
- deterministic;
- as localized as possible;
- accompanied by a counterexample when one is available.

The LLM may repair rejected objects, but the compiler must not treat its own AI-generated fix as proof of correctness.

---

## 14. Interpreter, VM, and Native Compilation

The proposal is to support multiple execution modes with shared semantics.

### 14.1. Graph Interpreter

Interprets the model or individual graph nodes. Primary uses:
- development;
- debugging;
- interactive exploration;
- execution of individual operations;
- inspection of state and dependencies.

### 14.2. Bytecode VM

The primary initial target backend:
- controlled execution;
- isolation;
- portability;
- resource control;
- convenient debugging;
- runtime checks.

The VM executes validated bytecode, not the entire original SPG.

### 14.3. Native Backend

Generates machine code for target architectures such as x86-64 and ARM64.

Primary uses:
- performance;
- systems programming;
- resource-intensive applications.

### 14.4. Unified Semantics

The interpreter, VM, and native backend must implement the same language semantics. Behavioral divergence between development and production modes must be prevented.

---

## 15. Trusted Computing Base and Transformation Verification

### 15.1. Trusted Computing Base

The Trusted Computing Base (TCB) should be small and include only necessary mechanisms:
- type checking;
- proof checking;
- bytecode verification;
- a minimal runtime-critical component.

The LLM must not be part of the TCB.

### 15.2. Proof-Carrying Compilation

Transformations between representations should be accompanied by evidence that the required semantics are preserved wherever possible.

```text
Program Graph
    |
    | Lowering + validation/proof
    v
Low-level IR
    |
    | Optimization + validation/proof
    v
Optimized IR
    |
    | Code generation
    v
Bytecode
    |
    | Bytecode validation
    v
Executable
```

A large formal proof is not necessarily required for every step. An alternative is translation validation — independently checking a particular transformation result.

It is important not to claim that execution correctness has been proved when only the correctness of the source-level implementation has been established. Optimizations, lowering, and code generation are also part of the trust chain.

### 15.3. Scope of Guarantees

Formal verification proves that a program conforms to a formal specification. It does not prove that the specification accurately captures the user's real intent. Requirements analysis, review, and human acceptance are needed for that.

---

## 16. Proposed Development Cycle

1. A human states the task and constraints.
2. The LLM proposes a Specification Graph.
3. The specification's structure, formalizability, and known contradictions are checked.
4. The LLM creates a Design Graph.
5. Interfaces, dependencies, and conformance to the specification are checked.
6. The LLM creates an Implementation Graph.
7. Structural, type, effect, and contract checks are performed.
8. The LLM fixes rejected objects.
9. Tests, fuzzing, and independent audits are performed.
10. Validated bytecode or a native executable is produced.

Each result must be bound to the exact Content Hashes of its input objects and to the tool configuration. Changing a hash-relevant object must change the hashes of dependent objects and invalidate stale checks; unchanged subgraphs may be reused.

---

## 17. Possible Prototype Technology Stack

These are preliminary hypotheses, not final decisions.

| Component | Possible Choice |
|---|---|
| Compiler Core | Rust |
| Program Graph | Custom typed IR |
| Serialization | Canonical binary format + JSON for interchange and debugging |
| Type System | Custom type checker |
| Formal Verification | SMT solver |
| Optimization | Custom IR transformations |
| VM | Custom virtual machine |
| Native Backend | LLVM as the initial backend |
| Testing | Property testing + fuzzing |

LLVM is considered a possible backend, not the central language model.

---

## 18. Design Principles

1. **Verifiability over trust in the generator.** Every LLM-generated program is considered a candidate until it passes checks.
2. **Deterministic core.** Compilation and verification must not depend on probabilistic LLM behavior.
3. **Locality of changes.** Changing one object should affect only known dependencies when doing so is semantically safe.
4. **Explicit effects.** External actions must not occur implicitly.
5. **Semantic structure over text.** Text is a representation, not the sole source of truth.
6. **No false success.** An unchecked or unproved property must not be labeled as proved.
7. **Optional rigor.** Simple programs should not be forced through the full architectural process.
8. **Traceability.** Requirements, architecture, implementation, tests, and proofs must be linked.
9. **Independent verification.** The checker must not rely on assertions made by the implementation's author.
10. **Multiple backends.** Language semantics must not depend on a particular execution engine.
11. **Single source of truth for execution and verification.** The executable program and formal models must be derived automatically from a single LLMLang semantic model; manually duplicating the algorithm independently in a model must not be the standard workflow.
12. **Formal semantics before backends.** Every core language construct must have precise semantics, and each backend must have a defined obligation to preserve them.
13. **Verifiable translations.** Model generation and executable code generation must be accompanied by a proof of semantic preservation or independent translation validation. Verification status cannot be inferred merely from successful generation.
14. **Honest boundaries of provability.** A missing suitable backend, failure of automatic proof search, and disproof of a property are distinct outcomes and must be distinguished.
15. **No hidden bypass of guarantees.** Unsupported or unproved constructs must explicitly mark affected properties as unchecked and propagate this status along dependencies.

---

## 18A. Unified Semantics and Automated Formal Verification

### 18A.1. A Single Description of the Algorithm

An algorithm must be specified once in LLMLang's canonical semantic model (the SPG and/or its typed semantic IR). The execution model and verification model are derived representations of that model, not independently maintained descriptions.

Developers should not have to manually rewrite an algorithm in TLA+ to obtain a verifiable model. Additional manually written proof lemmas, invariants, abstractions, and environmental assumptions are permissible, but they must not become a second, independent description of executable logic. Each such addition must be explicitly linked to the original LLMLang objects and the properties being verified.

### 18A.2. Formal Language Semantics

Every construct included in the formally supported LLMLang core MUST have precise formal semantics: values, states, effects, evaluation rules, and observable behavior.

The semantics must be defined independently of any particular backend. The interpreter, VM, native backend, and verification backends are required to preserve these semantics within their stated scope.

A construct without formal semantics may exist only as an explicitly designated extension with limited guarantees; it must not be silently included in the proved portion of a program.

### 18A.3. Generating Verification Models

The compiler SHOULD automatically generate formal models from LLMLang's canonical semantic model for algorithms and properties supported by the selected proof system.

TLA+ is one possible backend, particularly suitable for state-transition systems, protocols, and concurrent and distributed algorithms. TLAPS may be used to check mathematical proofs of TLA+ model properties; TLC and other tools may be used for finite-state model checking and counterexample discovery. Successful finite-state model checking must not be presented as a proof over an unbounded state space.

### 18A.4. Compositional Verification and Proof Boundaries

Verification should be compositional: a caller may use a callee's guarantees through its contract without reanalyzing the callee's internal implementation every time. However, the mere existence of a contract does not prove that the implementation satisfies it.

For each called object, it is necessary to distinguish:
- **contract guarantees** — preconditions, postconditions, invariants, effects, termination guarantees, and permitted outcomes;
- **implementation conformance to the contract** — whether a particular implementation has actually been proved to provide those guarantees;
- **proofs of implementation properties** — which properties of the implementation itself have been established independently of the contract.

A caller may rely on a callee's contract as a proved guarantee only when implementation conformance to that contract has been proved in the current proof context or is supported by an explicitly identified trusted assumption. If conformance is merely assumed or unchecked, the caller's proof must retain that dependency and cannot be treated as an unconditional end-to-end proof.

Statuses are assigned to individual properties, not to a function as a whole. Lack of proof must propagate along the actual dependency graph for the specific property: calls, data flow, control flow, and effects. It must not automatically make every function that directly or transitively calls that function unverifiable. If a caller property does not depend on the callee's unproved behavior, it may be proved independently.

The system MUST distinguish:
- proved implementation guarantees;
- assumptions that contracts are satisfied;
- properties checked only at runtime;
- properties for which proof is unavailable or impossible in the current backend.

A runtime check can detect a violation in a particular execution, but does not by itself prove that a property always holds. A trusted assumption may be used in composition, but must be explicitly recorded in the proof context and resulting guarantees.

Traceability must be supported along the chain:
`requirement → contract property → implementation evidence → call/dependency edges → caller property → system-level claim`.
When a contract, implementation, assumption, or hash-relevant dependency changes, the system must invalidate affected proofs and recompute only properties that actually depend on the change.

Other backends (such as SMT/Why3, Lean, or Coq) may be appropriate for other classes of problems. Backend selection should depend on the formalized semantics and required properties, rather than on an insistence on translating every program to TLA+.

### 18A.5. Connecting the Model to Executable Code

Model generation and executable code generation must originate from the same LLMLang semantics. Simply generating both artifacts from a shared AST is not enough: each transformation's preservation of semantics must be justified.

The target proof obligation is to establish that the observable behavior of the generated model and executable code conforms to the semantics of the source program. For backends with additional internal states, a refinement relation or another explicitly defined correspondence relation may be used instead of literal state equality.

The preferred long-term mechanism is provably correct translators and proof-carrying compilation. A practical initial mechanism is independent translation validation of each translation result. The checker must not unconditionally trust the same unverified generator whose correctness it is checking.

### 18A.6. Applicability Limits and Statuses

Not every algorithm or property can conveniently or automatically be represented and proved in TLA+/TLAPS. This must not restrict the expressiveness of the language as a whole or block ordinary compilation when the program satisfies execution requirements.

For each property and each verification artifact, at least the following statuses must be distinguished:
- `PROVEN` — a trusted proof checker has checked the proof under the stated assumptions;
- `DISPROVEN` — a validated counterexample has been obtained or the negation of the property has been proved;
- `UNKNOWN` — the verification attempt produced neither proof nor disproof;
- `NOT_SUPPORTED` — the selected backend does not support the required construct or property;
- `NOT_CHECKED` — verification was not run.

Finite-state model checking, testing, fuzzing, and runtime monitoring must have their own result types and must not be substituted for `PROVEN`.

All assumptions about the environment, fairness, input bounds, numerical model, external components, and abstraction boundaries must be explicit and included in the proof context. A proof status applies only to the property under those assumptions.

### 18A.7. Proof Invalidation and Provenance

Every model, proof obligation, proof, and translation-validation result must be tied to the Content Hashes of the source semantic objects, the LLMLang semantics version, the backend version, the configuration, and explicit assumptions.

Changing any hash-relevant element must invalidate all potentially stale dependent proofs and verification results. Unchanged independent subgraphs may reuse cached results.

### 18A.8. Trusted Computing Base

The trust boundary must be documented. At minimum, it includes the proof checker, the mechanisms for checking translation validation or compiler proofs, and the parts of the compiler and runtime on which the claimed guarantee depends.

A proof of a model does not in itself prove the correctness of native code, the compiler, the runtime, the operating system, or the hardware. Every guarantee must state which links in the chain are proved, independently checked, or still trusted.


### 18A.9. Explicit assumptions and conditional proof management (research proposal)

[RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md) investigates first-class typed assumptions and exact foreign-provider bindings, explicit trust authorization, property-specific dependency closure, discharge/revocation and separate proof outcome, closure, freshness and admission. A locally checked proof under a declared foreign contract does not prove that implementation; policy can allow conditional use without granting unconditional proof status. This candidate extension reconciles §18A.6 with RT-32/33 and does not redefine existing statuses before adoption.

## 19. Main Open Questions

The following decisions have not yet been made and require separate design work.

### 19.1. SPG Model
- Which node types exist?
- Which edge types are allowed?
- How are Stable ID and Content Hash separated, and how are their canonicalization and stability ensured?
- How are object Content Hashes computed and propagated?
- How are conflicting changes resolved?
- How do graph-change transactions work?

### 19.2. Layer Semantics
- How can the `satisfies` relationship between Design and Specification be expressed formally?
- How can the `implements` relationship between Implementation and Design be expressed?
- Which relationships can be checked automatically?
- How does project policy specify mandatory layers?

### 19.3. Type System
- How should generic types, traits/type classes, and inference work?
- How should refinement types and SMT interact?
- How should state types be modeled when entities change?
- Which ownership model best suits LLMs and the runtime?

### 19.4. Effects and Security
- How should capabilities work?
- How are effects transferred and constrained?
- How should interaction with untrusted code be modeled?
- What is the runtime threat model?

### 19.5. Verification
- Which contracts must be provable?
- How should SMT solver time and resources be managed?
- How should partial proofs be represented?
- How should the correctness of optimizations and backends be checked?

### 19.6. Runtime
- How should memory, exceptions, and cancellation work?
- What is the concurrency model?
- Which guarantees are provided by the VM and which by the compiler?
- How can safety and performance be reconciled?

### 19.7. LLM Interface
- Which protocol should be used for SPG proposals and changes?
- How should context size be limited?
- How should diagnostics and counterexamples be represented?
- How can changes be made reproducible?

---

## 20. Proposed Research Stages

### Stage 0. Conceptual Specification
Establish terminology, goals, non-goals, the graph model, layers, semantics, and the boundaries of guarantees.

### Stage 1. Minimal SPG Model
Define a small set of objects: module, type, function, parameter, expression, contract, effect, test, and dependency. Implement serialization and structural-integrity checks.

### Stage 2. Minimal Language
Define a small DSL and an unambiguous mapping between the DSL and SPG.

### Stage 3. Static Semantics
Implement type checking, algebraic types, exhaustive matching, and a basic effect model.

### Stage 4. Contracts and Verification
Add preconditions, postconditions, invariants, verification conditions, and SMT integration.

### Stage 4A. Formal Semantics and Verification Backends
Define the semantics of a proof-friendly core and a minimal common semantic IR. Implement an initial vertical slice that generates both a formal model and an executable representation from one source. For a selected class of algorithms, add a TLA+ backend and TLC/TLAPS model verification; define translation validation and bind results to Content Hashes. Expand the range of backends only together with formal semantic-preservation obligations.

### Stage 5. VM
Define bytecode, a runtime, and an interpreter. Check that execution semantics conform to the language model.

### Stage 6. LLM Tools
Add APIs for structured proposals, local edits, diagnostics, and incremental checks.

### Stage 7. Backends and Optimization
Add lowering, optimizations, and a native backend with independent verification of transformations.

### Stage 8. Practical Evaluation
Compare LLMLang with Rust, Go, and other languages on the same tasks:
- defect frequency;
- number of correction iterations;
- contract completeness;
- review complexity;
- performance;
- generation and verification costs;
- resilience to requirements changes.

---

## 21. Success Criteria

The project cannot be considered successful merely because an LLM generates fewer lines or writes syntactically correct code faster.

Key criteria:
- fewer defects across an equivalent set of tasks;
- a higher proportion of errors detected before execution;
- high diagnostic accuracy;
- no false `PROVEN` statuses;
- reproducible compilation and verification;
- understandable, localized graph changes;
- acceptable verification costs;
- no significant performance degradation where performance matters;
- effective collaboration between humans and LLMs.

---

## 22. Brief Summary

LLMLang is envisioned as a language in which:

- intent and specifications can be represented formally;
- architecture, implementation, and specification exist as connected layers;
- the program is stored as a typed Semantic Program Graph;
- the LLM proposes graph changes but is not a trusted verifier;
- the compiler independently checks structure, types, effects, and contracts;
- tests and proofs are linked to requirements;
- execution is possible through an interpreter, VM, or native backend;
- compiler transformations are part of the verification chain;
- simple programs can omit some of the design layers.

The project's central hypothesis:

**By making the semantic program model, contracts, dependencies, and verification first-class elements of the language, we can significantly reduce errors when developing programs with LLMs — without relying on the LLM itself to always remember and correctly apply every rule.**

**Research status note (2026-11-18):** The type, refinement, effect, ownership, and capability proposals in this concept remain exploratory. See [RT-04 alternatives research](../RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) for the comparative option space and unresolved compatibility questions. This report does not make the concept's proposals normative.
