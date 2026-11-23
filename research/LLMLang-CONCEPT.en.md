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

## 11. Декларативные ограничения и автоматическая реализация

Одна из исследовательских возможностей — описывать ограничения и гарантии, позволяя LLM предлагать реализацию.

Пример:

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

Предполагаемый процесс:
1. Формализовать гарантии и ограничения.
2. Проверить их непротиворечивость и достаточность.
3. Предложить архитектуру и алгоритм.
4. Сформировать реализацию.
5. Выполнить статические и формальные проверки.
6. Запустить тесты и измерения.
7. Отклонить реализацию, не удовлетворяющую установленным критериям.

`implementation: automatic` означает генерацию кандидата реализации, а не магическое решение произвольной задачи компилятором. Кандидат остаётся недоверенным до проверки.

---

## 12. Компилятор и общая архитектура

Предлагается не традиционный монолитный компилятор, а многоступенчатая система трансляции и верификации.

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

LLM формирует и изменяет предложения программы. Проверяющие подсистемы должны быть детерминированными и независимыми от LLM.

### 12.1. Structural Validator

Проверяет:
- существование всех ссылок;
- корректность типов объектов;
- уникальность ID;
- обязательные поля;
- допустимость циклов;
- соответствие графа схеме языка.

### 12.2. Type Checker

Проверяет статическую корректность типов, включая алгебраические, refinement- и типы состояний.

### 12.3. Effect Checker

Проверяет, что реализация использует только объявленные эффекты и capabilities. Анализ должен учитывать транзитивные вызовы.

### 12.4. Contract Verifier

Проверяет выполнение контрактов. Для подходящих задач может строить условия верификации и передавать их SMT-решателю.

Пример:

```text
requires:
    balance >= amount
    amount >= 0

ensures:
    balance - amount >= 0
```

Упрощённое математическое обязательство:

\[
balance \ge amount \land amount \ge 0
\Rightarrow balance - amount \ge 0
\]

Результаты должны иметь как минимум следующие статусы:
- `PROVEN` — свойство доказано;
- `DISPROVEN` — найден контрпример;
- `UNKNOWN` — доказать или опровергнуть не удалось;
- `NOT_CHECKED` — проверка не выполнялась.

`UNKNOWN` и `NOT_CHECKED` не должны считаться успешной проверкой.

### 12.5. Dependency Analyzer

Отслеживает зависимости между:
- требованиями;
- контрактами;
- типами;
- архитектурными объектами;
- алгоритмами;
- реализациями;
- тестами;
- доказательствами.

Изменение объекта должно инвалидировать зависимые результаты проверки, если они больше не гарантированно актуальны. Это основа инкрементальной компиляции.

---

## 13. Взаимодействие LLM и компилятора

Традиционная модель:

```text
LLM -> source code -> compiler -> errors
```

Предлагаемая модель:

```text
LLM -> structured proposal -> compiler -> verification feedback
```

LLM создаёт типизированные объекты или предложения об изменении графа. Компилятор проверяет их и возвращает структурированные диагностики.

Пример:

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

Диагностика должна быть:
- привязана к объектам SPG;
- машиночитаемой;
- детерминированной;
- максимально локальной;
- снабжённой контрпримером, если он доступен.

LLM может исправлять отклонённые объекты, но компилятор не должен считать собственное AI-исправление доказательством корректности.

---

## 14. Интерпретатор, VM и нативная компиляция

Предлагается поддерживать несколько способов исполнения с общей семантикой.

### 14.1. Graph Interpreter

Интерпретирует модель или отдельные узлы графа. Основное назначение:
- разработка;
- отладка;
- интерактивное исследование;
- выполнение отдельных операций;
- просмотр состояния и зависимостей.

### 14.2. Bytecode VM

Основной первоначальный целевой backend:
- контролируемое исполнение;
- изоляция;
- переносимость;
- контроль ресурсов;
- удобная отладка;
- runtime-проверки.

VM исполняет проверенный байткод, а не весь исходный SPG.

### 14.3. Native Backend

Генерирует машинный код для целевых архитектур, например x86-64 и ARM64.

Основное назначение:
- производительность;
- системное программирование;
- приложения с высокими требованиями к ресурсам.

### 14.4. Единая семантика

Интерпретатор, VM и native backend должны реализовывать одну семантику языка. Необходимо исключить расхождение поведения между режимами разработки и production.

---

## 15. Доверенная база и проверка преобразований

### 15.1. Trusted Computing Base

Доверенная база (TCB) должна быть небольшой и включать только необходимые механизмы:
- проверку типов;
- проверку доказательств;
- проверку байткода;
- минимальную критическую часть runtime.

LLM не должна входить в TCB.

### 15.2. Proof-Carrying Compilation

Преобразования между представлениями должны сопровождаться свидетельствами сохранения требуемой семантики там, где это возможно.

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

Не обязательно строить громоздкое формальное доказательство для каждого шага. Альтернативой может быть translation validation — независимая проверка конкретного результата преобразования.

Важно не утверждать, что доказана корректность исполнения, если доказана только корректность исходной реализации. Оптимизации, lowering и генерация кода также входят в цепочку доверия.

### 15.3. Граница гарантий

Формальная верификация доказывает соответствие программы формальной спецификации. Она не доказывает, что спецификация верно отражает реальные намерения пользователя. Для этого нужны анализ требований, ревью и приёмка человеком.

---

## 16. Предлагаемый цикл разработки

1. Человек формулирует задачу и ограничения.
2. LLM предлагает Specification Graph.
3. Проверяются структура, формализуемость и известные противоречия спецификации.
4. LLM формирует Design Graph.
5. Проверяются интерфейсы, зависимости и соответствие спецификации.
6. LLM создаёт Implementation Graph.
7. Выполняются проверки структуры, типов, эффектов и контрактов.
8. LLM исправляет отклонённые объекты.
9. Выполняются тесты, fuzzing и независимый аудит.
10. Создаётся проверенный байткод или нативный исполняемый файл.

Каждый результат должен быть привязан к точным Content Hash входных объектов и конфигурации инструментов. Изменение hash-relevant объекта должно менять хеши зависимых от него объектов и инвалидировать устаревшие проверки; неизменённые подграфы могут повторно использоваться.

---

## 17. Возможный технологический стек прототипа

Это предварительные гипотезы, а не окончательные решения.

| Компонент | Возможный выбор |
|---|---|
| Compiler Core | Rust |
| Program Graph | Собственная типизированная IR |
| Serialization | Канонический бинарный формат + JSON для обмена и отладки |
| Type System | Собственный type checker |
| Formal Verification | SMT solver |
| Optimization | Собственные преобразования IR |
| VM | Собственная виртуальная машина |
| Native Backend | LLVM как первоначальный backend |
| Testing | Property testing + fuzzing |

LLVM рассматривается как возможный backend, но не как центральная модель языка.

---

## 18. Принципы проектирования

1. **Проверяемость важнее доверия к генератору.** Любая программа от LLM считается кандидатом до прохождения проверок.
2. **Детерминированное ядро.** Компиляция и проверки не должны зависеть от вероятностного поведения LLM.
3. **Локальность изменений.** Изменение одного объекта должно затрагивать только известные зависимости, если это семантически безопасно.
4. **Явность эффектов.** Внешние действия не должны возникать неявно.
5. **Семантическая структура важнее текста.** Текст — представление, а не единственный источник истины.
6. **Никакого ложного успеха.** Непроверенное или недоказанное свойство не обозначается как доказанное.
7. **Опциональная строгость.** Простые программы не должны быть вынуждены проходить полный архитектурный процесс.
8. **Трассируемость.** Требования, архитектура, реализация, тесты и доказательства должны быть связаны.
9. **Независимая проверка.** Проверяющая сторона не должна полагаться на утверждения автора реализации.
10. **Несколько backend.** Семантика языка не должна зависеть от конкретной машины исполнения.
11. **Единый источник истины для исполнения и верификации.** Исполняемая программа и формальные модели должны автоматически выводиться из одной семантической модели LLMLang; независимое ручное дублирование алгоритма в модели не должно быть штатным процессом.
12. **Формальная семантика предшествует backend.** Каждая конструкция ядра языка должна иметь точную семантику, а каждый backend — определённое обязательство по её сохранению.
13. **Проверяемые трансляции.** Генерация модели и исполняемого кода должна сопровождаться доказательством сохранения семантики либо независимой translation validation. Верификационный статус нельзя выводить только из факта успешной генерации.
14. **Честная граница доказуемости.** Отсутствие подходящего backend, неудача автоматического поиска доказательства и опровержение свойства — разные результаты и должны различаться.
15. **Отсутствие скрытого обхода гарантий.** Неподдерживаемые или недоказанные конструкции должны явно маркировать затронутые свойства как непроверенные и распространять этот статус по зависимостям.

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
