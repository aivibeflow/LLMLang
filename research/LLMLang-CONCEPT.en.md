# LLMLang — An AI-Native Programming Language Concept

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

The full model, hash boundaries, C interoperability, and open questions are documented in the [RT-09 proposal on structural type identity, layout, and C ABI](RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md). This proposal is not approved normative semantics.

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

## 18A. Единая семантика и автоматическая формальная верификация

### 18A.1. Единственное описание алгоритма

Алгоритм должен задаваться один раз в канонической семантической модели LLMLang (SPG и/или её типизированном семантическом IR). Модель исполнения и модель верификации являются производными представлениями этой модели, а не независимо поддерживаемыми описаниями.

Разработчик не должен вручную переписывать алгоритм на TLA+ для того, чтобы получить проверяемую модель. Ручные дополнительные доказательные леммы, инварианты, абстракции и environmental assumptions допустимы, но они не должны становиться вторым независимым описанием исполняемой логики. Каждое такое дополнение должно быть явно связано с исходными объектами LLMLang и проверяемыми свойствами.

### 18A.2. Формальная семантика языка

Каждая конструкция, включённая в формально поддерживаемое ядро LLMLang, MUST иметь точную формальную семантику: значения, состояния, эффекты, правила вычисления и наблюдаемое поведение.

Семантика должна быть определена независимо от конкретного backend. Интерпретатор, VM, нативный backend и верификационные backend обязаны сохранять эту семантику в заявленных пределах.

Конструкция без формальной семантики может существовать только как явно обозначенное расширение с ограниченными гарантиями; её нельзя молча включать в доказанную часть программы.

### 18A.3. Генерация моделей верификации

Компилятор SHOULD автоматически строить формальные модели из канонической семантической модели LLMLang для алгоритмов и свойств, которые поддерживаются выбранной доказательной системой.

TLA+ является одним из backend, особенно подходящим для систем переходов состояний, протоколов, конкурентных и распределённых алгоритмов. TLAPS может использоваться для проверки математических доказательств свойств TLA+-модели; TLC и другие инструменты могут использоваться для проверки конечных моделей и поиска контрпримеров. Успешная проверка конечной модели не должна выдаваться за доказательство для неограниченного пространства состояний.

### 18A.4. Композиционная верификация и границы доказательств

Верификация должна быть композиционной: caller может использовать гарантии callee через его контракт, не анализируя каждый раз внутреннюю реализацию. Однако наличие контракта само по себе не доказывает, что реализация ему соответствует.

Для каждого вызываемого объекта необходимо различать:
- **контрактные гарантии** — предусловия, постусловия, инварианты, эффекты, гарантии завершения и допустимые исходы;
- **соответствие реализации контракту** — доказано ли, что конкретная реализация действительно обеспечивает эти гарантии;
- **доказательства свойств реализации** — какие свойства самой реализации установлены независимо от контракта.

Caller вправе опираться на контракт callee как на доказанную гарантию только тогда, когда соответствие реализации этому контракту доказано в текущем proof context либо обеспечено явно обозначенным доверенным предположением. Если соответствие лишь предполагается или не проверено, доказательство caller должно сохранять эту зависимость и не может считаться безусловным end-to-end доказательством.

Статусы назначаются отдельным свойствам, а не функции целиком. Недоказанность должна распространяться по графу фактических зависимостей конкретного свойства: вызовов, потоков данных, управления и эффектов. Она не должна автоматически делать неверифицируемыми все функции, которые прямо или транзитивно вызывают данную функцию. Если свойство caller не зависит от недоказанного поведения callee, это свойство может быть доказано независимо.

Система MUST различать:
- доказанные гарантии реализации;
- предположения о соблюдении контрактов;
- свойства, проверяемые только во время исполнения;
- свойства, для которых доказательство отсутствует или невозможно в текущем backend.

Runtime-проверка может обнаруживать нарушение в конкретном исполнении, но сама по себе не доказывает универсальное соблюдение свойства. Доверенное предположение может использоваться в композиции, но должно быть явно отражено в контексте доказательства и итоговых гарантиях.

Должна поддерживаться трассируемость цепочки:
`requirement → contract property → implementation evidence → call/dependency edges → caller property → system-level claim`.
При изменении контракта, реализации, предположения или hash-relevant зависимости система должна инвалидировать затронутые доказательства и пересчитывать только реально зависимые свойства.


Для других классов задач могут применяться иные backend (например, SMT/Why3, Lean или Coq). Выбор backend должен зависеть от формализованной семантики и требуемых свойств, а не от желания любой ценой перевести программу в TLA+.

### 18A.5. Связь модели с исполняемым кодом

Генерация модели и исполняемого кода должна исходить из одной и той же семантики LLMLang. Недостаточно лишь генерировать оба артефакта из общего AST: необходимо обосновать сохранение семантики каждым преобразованием.

Целевое обязательство — доказать, что наблюдаемое поведение сгенерированной модели и исполняемого кода соответствует семантике исходной программы. Для backend с дополнительными внутренними состояниями допускается отношение refinement или иное явно определённое отношение соответствия вместо буквального равенства состояний.

Предпочтительный долгосрочный механизм — доказуемые трансляторы и proof-carrying compilation. Практический начальный механизм — независимая translation validation каждого результата трансляции. Проверяющий механизм не должен безусловно доверять тому же непроверенному генератору, корректность которого он проверяет.

### 18A.6. Границы применимости и статусы

Не каждый алгоритм или каждое свойство удобно либо возможно автоматически представить и доказать в TLA+/TLAPS. Это не должно ограничивать выразительность всего языка и не должно блокировать обычную компиляцию, если программа удовлетворяет требованиям исполнения.

Для каждого свойства и каждого артефакта верификации необходимо различать как минимум:
- `PROVEN` — доказательство проверено доверенным proof checker в заявленных предположениях;
- `DISPROVEN` — получен проверенный контрпример или доказано отрицание свойства;
- `UNKNOWN` — попытка проверки не дала ни доказательства, ни опровержения;
- `NOT_SUPPORTED` — выбранный backend не поддерживает нужную конструкцию или свойство;
- `NOT_CHECKED` — проверка не запускалась.

Конечная проверка модели, тестирование, fuzzing и runtime monitoring должны иметь собственные типы результатов и не подменять `PROVEN`.

Все предположения о среде, fairness, ограничениях входов, числовой модели, внешних компонентах и границах абстракции должны быть явными и входить в контекст доказательства. Статус доказательства относится только к свойству при этих предположениях.

### 18A.7. Инвалидация и происхождение доказательств

Каждая модель, proof obligation, доказательство и результат translation validation должны быть привязаны к Content Hash исходных семантических объектов, версии семантики LLMLang, версии backend, конфигурации и явным предположениям.

Изменение любого hash-relevant элемента должно инвалидировать все потенциально устаревшие зависимые доказательства и результаты верификации. Неизменённые независимые подграфы могут повторно использовать кэшированные результаты.

### 18A.8. Доверенная база

Граница доверия должна быть документирована. В неё входят как минимум proof checker, механизмы проверки translation validation или доказательств компилятора, а также те части компилятора и runtime, от которых зависит заявленная гарантия.

Доказательство модели само по себе не доказывает корректность нативного кода, компилятора, runtime, ОС или оборудования. Каждая гарантия должна указывать, какие звенья цепочки доказаны, проверены независимо или остаются доверенными.


## 19. Основные открытые вопросы

Следующие решения пока не приняты и требуют отдельного проектирования.

### 19.1. Модель SPG
- Какие типы узлов существуют?
- Какие типы связей допустимы?
- Как разделяются Stable ID и Content Hash, и как обеспечиваются канонизация и стабильность обоих?
- Как вычисляются и распространяются Content Hash объектов?
- Как разрешаются конфликтующие изменения?
- Как устроены транзакции изменений графа?

### 19.2. Семантика слоёв
- Как формально выразить отношение `satisfies` между Design и Specification?
- Как выразить отношение `implements` между Implementation и Design?
- Какие связи проверяемы автоматически?
- Как политика проекта устанавливает обязательные слои?

### 19.3. Типовая система
- Как устроены generic types, traits/type classes и inference?
- Как сочетаются refinement types и SMT?
- Как моделируются типы состояний при изменении сущностей?
- Какая модель ownership лучше всего подходит для LLM и runtime?

### 19.4. Эффекты и безопасность
- Как устроены capabilities?
- Как передаются и ограничиваются эффекты?
- Как моделируется взаимодействие с недоверенным кодом?
- Какова модель угроз runtime?

### 19.5. Верификация
- Какие контракты обязаны быть доказуемыми?
- Как управлять временем и ресурсами SMT-решателя?
- Как представлять частичные доказательства?
- Как проверять корректность оптимизаций и backend?

### 19.6. Runtime
- Как устроены память, исключения и отмена?
- Какова модель конкурентности?
- Какие гарантии обеспечиваются VM, а какие компилятором?
- Как совместить безопасность и производительность?

### 19.7. Интерфейс LLM
- Какой протокол предложений и изменений SPG использовать?
- Как ограничивать размер контекста?
- Как представлять диагностики и контрпримеры?
- Как обеспечивать воспроизводимость изменений?

---

## 20. Предлагаемые этапы исследования

### Этап 0. Концептуальная спецификация
Зафиксировать термины, цели, не-цели, модель графа, слои, семантику и границы гарантий.

### Этап 1. Минимальная модель SPG
Определить небольшой набор объектов: модуль, тип, функция, параметр, выражение, контракт, эффект, тест и зависимость. Реализовать сериализацию и проверку структурной целостности.

### Этап 2. Минимальный язык
Определить небольшой DSL и однозначное отображение между DSL и SPG.

### Этап 3. Статическая семантика
Реализовать типизацию, алгебраические типы, исчерпывающие match и базовую модель эффектов.

### Этап 4. Контракты и проверка
Добавить предусловия, постусловия, инварианты, условия верификации и SMT-интеграцию.

### Этап 4A. Формальная семантика и верификационные backend
Определить семантику proof-friendly core и минимальный общий семантический IR. Реализовать первый вертикальный срез генерации формальной модели и исполняемого представления из одного источника. Для выбранного класса алгоритмов добавить TLA+ backend и проверку модели TLC/TLAPS; определить translation validation и привязку результатов к Content Hash. Расширять набор backend только вместе с формальными обязательствами сохранения семантики.

### Этап 5. VM
Определить байткод, runtime и интерпретатор. Сверить семантику исполнения с моделью языка.

### Этап 6. Инструменты LLM
Добавить API структурированных предложений, локальных изменений, диагностики и инкрементальных проверок.

### Этап 7. Backend и оптимизация
Добавить lowering, оптимизации и нативный backend с независимой проверкой преобразований.

### Этап 8. Практическая оценка
Сравнить LLMLang с Rust, Go и другими языками на одинаковых задачах:
- частота ошибок;
- количество итераций исправления;
- полнота контрактов;
- сложность ревью;
- производительность;
- стоимость генерации и проверки;
- устойчивость к изменениям требований.

---

## 21. Критерии успеха

Нельзя считать проект успешным только потому, что LLM генерирует меньше строк или быстрее пишет синтаксически корректный код.

Основные критерии:
- меньше дефектов на одинаковом наборе задач;
- более высокая доля ошибок, обнаруживаемых до исполнения;
- высокая точность диагностики;
- отсутствие ложного статуса `PROVEN`;
- воспроизводимость компиляции и проверок;
- понятные и локальные изменения графа;
- приемлемая стоимость верификации;
- отсутствие существенного ухудшения производительности там, где она важна;
- удобство совместной работы человека и LLM.

---

## 22. Краткое резюме

LLMLang предполагается как язык, в котором:

- намерения и спецификации могут быть представлены формально;
- архитектура, реализация и спецификация существуют как связанные слои;
- программа хранится как типизированный Semantic Program Graph;
- LLM предлагает изменения графа, но не является доверенной проверяющей стороной;
- компилятор независимо проверяет структуру, типы, эффекты и контракты;
- тесты и доказательства связаны с требованиями;
- исполнение возможно через интерпретатор, VM или native backend;
- преобразования компилятора входят в цепочку проверки;
- простые программы могут обходиться без полного набора проектных слоёв.

Главная гипотеза проекта:

**Если сделать семантическую модель программы, контракты, зависимости и проверку первоклассными элементами языка, то можно существенно снизить вероятность ошибок при разработке программ с помощью LLM — не полагаясь на то, что сама LLM всегда помнит и правильно применяет все правила.**

**Research status note (2026-11-18):** The type, refinement, effect, ownership, and capability proposals in this concept remain exploratory. See [RT-04 alternatives research](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) for the comparative option space and unresolved compatibility questions. This report does not make the concept's proposals normative.
