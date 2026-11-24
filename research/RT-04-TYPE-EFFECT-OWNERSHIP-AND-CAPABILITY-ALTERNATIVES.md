# RT-04 — Type, Effect, Ownership, and Capability-System Alternatives

**Research area:** RT-04 — Type system, effects, ownership, and capabilities  
**Status:** comparative alternatives report; no architecture selected  
**Updated:** 2026-11-18  
**Depends on:** [RT-03 Core Language Semantics](CORE-LANGUAGE-SEMANTICS.md)  
**Related:** [LLMLang Concept](LLMLang-CONCEPT.md), [POSIX Runtime Architecture](POSIX-RUNTIME-ARCHITECTURE.md), [RT-24 identity work](RT-24-IDENTITY-DECISION-MATRIX.md), [Research Dependency Map](RESEARCH-DEPENDENCY-MAP.md), [RT-09 structural type identity and C ABI proposal](RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md)

## 1. Purpose and boundaries

RT-04 investigates type, effect, resource-ownership, capability, and concurrency/memory-model alternatives that can be combined with RT-03's candidate execution profiles. This is a comparative design study, not a language specification, implementation plan, or decision record.

Keep separate the following dimensions:
- value/type structure and type compatibility;
- refinement and state-dependent validity;
- effect description and effect handling;
- aliasing, ownership, borrowing, and lifetime;
- authority/capability checks;
- task, message, synchronization, and memory semantics;
- error and resource-failure representation.

A language can combine nominal algebraic data types, structural interfaces, effect rows, affine resource ownership, and object capabilities. These are composable design dimensions, not mutually exclusive language families.

### 1.1 Existing assumptions

The current concept proposes strict static typing, algebraic data types, refinement types, typed states, explicit resource ownership, effect checking, and explicit capabilities. It mentions Rust-inspired ownership/borrowing but leaves open a simpler model suitable for LLM authoring. Effect checking is expected to account for transitive calls. These are proposals, not accepted normative rules.

The POSIX runtime work expects public contracts to expose types and valid domains, pre/postconditions, state transitions, observable behavior, resource ownership/lifetimes, effects, required capabilities, success/failure outcomes, error behavior, blocking/interruption/partial completion, and concurrency/synchronization semantics. It leaves open whether LLMLang should expose POSIX directly or provide a safer typed façade.

RT-03 compares four semantic profiles:
- **A — Pure Functional Core:** immutable values, pure functions, strict evaluation, explicit results, deterministic sequential source semantics.
- **B — Imperative Linear Core:** explicit state transitions and mutation constrained by ownership/linearity.
- **C — Concurrent/Actor Core:** isolated agents, asynchronous execution, message passing, potentially nondeterministic traces.
- **D — Effectful Functional Core:** functional values/composition with explicitly declared and handled effects.

RT-04 must not silently select one. Static typing does not determine purity; ownership does not define concurrency; capability possession does not specify effects or observable behavior.

### 1.2 Non-goals

This report does not select syntax, inference algorithm, ABI, runtime, or standard library; prescribe Rust or another language wholesale; equate type safety with functional correctness or security; claim effect annotations prove implementation behavior; define final SPG schemas/hash envelopes; or choose a semantic profile or complete memory model.

## 2. Type-system alternatives

### 2.1 Type identity and compatibility

| Vector | Main idea | Benefits | Costs / questions |
|---|---|---|---|
| Nominal types | Declared identity independent of representation | Clear API/resource boundaries; prevents accidental interchange | Wrappers/conversions; identity and versioning rules |
| Structural types | Compatibility follows from required fields/operations | Flexible composition and generated interfaces | Accidental compatibility; public shape changes can widen impact |
| Algebraic data types | Sum/product types encode alternatives and composition | Exhaustive matching; explicit states/errors; proof-friendly | Closed variants require explicit extension/versioning policy |
| Traits/type classes/interfaces | Behavior implemented for types through instances | Generic abstractions and reuse | Coherence, overlap, orphan rules, implicit-resolution complexity |
| Generics / parametric polymorphism | Definitions abstract over types | Reuse and strong abstraction | Monomorphization/code size vs dictionaries; higher-kinded complexity |
| Dynamic boundary | Dynamically checked values at explicit boundaries | Interop and schema evolution | Runtime checks and weaker static guarantees |

These can be combined. A candidate may use nominal ADTs for domain/resource identity, structural records for interchange, and traits for behavior. This combination is a test candidate, not a recommendation to freeze.

### 2.2 Refinement, dependent information, and state types

| Vector | What is expressed | Strength | Cost / risk |
|---|---|---|---|
| Simple static types | Broad value categories and signatures | Small checker; predictable inference | Many constraints remain runtime contracts |
| Refinement types | Base type plus predicate | Makes domain constraints statically visible where decidable | Solver integration, decidability boundary, proof obligations |
| Dependent types | Types may depend on values | Expressive invariants and indexed structures | Elaboration, equality, termination, and proof burden |
| Typestate / state-indexed types | Legal operations depend on resource/entity state | Prevents invalid lifecycle transitions where statically known | State explosion and externally changed state |
| Runtime-validated refinements | Boundary check plus validation evidence | Practical for external data | Evidence lifetime, trust, invalidation, serialization |

A refinement predicate may be decidable by a bounded checker, require SMT, require a proof term, or remain a runtime assertion. The type system must expose which case applies. Timeout, unsupported theory, missing assumptions, or UNKNOWN must not be treated as proof.

Typestate is not the same as a runtime state machine. A static state index describes what the checker can establish; runtime state may be changed by external actors. Stale-state detection must be specified.

### 2.3 Inference and explicitness

Candidate policies:
1. Local/Hindley–Milner-style inference: convenient for pure polymorphic expressions; harder with subtyping, effects, GADTs, and higher-rank features.
2. Bidirectional typing: infer in synthesis positions and check against expected types in annotated positions; potentially clearer diagnostics.
3. Mostly explicit types: public signatures and effect/resource boundaries declared, local inference allowed.
4. Global constraint inference: expressive, but diagnostics can become unstable and solving expensive as features grow.

LLM-authored code benefits from local, actionable diagnostics. Public operations, effect boundaries, resource transitions, and exported generic interfaces are candidates for explicit annotations even if local inference exists.

### 2.4 Subtyping, coercion, and contract compatibility

Keep three relations distinct:
- type subtyping: which values are accepted;
- coercion: an executable or representation-preserving conversion;
- behavioral substitutability: whether an implementation satisfies a consumer's contract under declared assumptions.

Type-compatible replacement is not automatically behaviorally compatible. Refinement, error sets, effects, resource obligations, and capability requirements can change the contract. Implicit coercions are semantic operations and should be visible to diagnostics, canonical IR, and evidence.

### 2.5 Structural identity and representation requirements

A separate cross-area proposal explores a name-independent Structural Identity Hash, a Type Hash that extends that identity with canonical representation requirements, and compiler-derived Layout and Function ABI descriptors. It also separates consumer-specific semantic contracts from the data shape and preserves foreign C declaration identity independently from LLMLang structural identity.

This is a candidate architecture, not a conclusion of the RT-04 comparison and not an accepted type-system or ABI policy. See [RT-09 structural type identity, representation requirements, layout, and C ABI proposal](RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md). The open questions include recursive canonicalization, type/nominal compatibility, requirement composition, target ABI profiles, and cross-target FFI validation.

## 3. Effect-system alternatives

### 3.1 Effect representation

| Vector | Main idea | Benefits | Costs / questions |
|---|---|---|---|
| No effect system | Effects by convention | Minimal syntax | Cannot reliably check transitive effects or least authority |
| Closed effect sets | Signature lists finite effect labels | Simple to explain/check | Extensibility and generic abstraction |
| Effect rows | Known effects plus open row | Composable higher-order functions and libraries | Row unification, constraints, polymorphic handlers |
| Algebraic effects/handlers | Computations request operations; handlers interpret them | Separates declaration from interpretation | Forwarding, ordering, finalization, handler semantics |
| Capability-indexed effects | Effect use requires explicit authority | Connects effects to least authority | Permission is not actual behavior; token scope/lifetime |
| Trace/event semantics | Effects represented as observable events/traces | Useful for concurrency, replay, refinement | Trace equivalence and state-space complexity |

These need not be exclusive: a row-polymorphic signature may be interpreted through handlers, while capabilities gate selected operations.

### 3.2 Effect granularity

Labels range from coarse (IO, State, Network) to operation-level (filesystem.read with a path scope, process.spawn with a profile, monotonic clock). Coarse labels are simpler but may overstate authority and weaken dependency precision. Fine labels improve policy and impact analysis but risk unmanageable signatures and unstable contracts.

Experiments should compare a small closed core vocabulary, parameterized effect labels, effect rows, and handler boundaries. Effects describe semantic interaction, not implementation accidents. An unobservable temporary file fully encapsulated inside a library need not necessarily become a public effect; a hidden network request cannot be omitted merely because it is inside a library.

### 3.3 Checking and handling

The checker needs rules for direct effects, transitive calls and dynamic dispatch, effect polymorphism, handler introduction/elimination/forwarding/masking, exceptions, cancellation, resource finalization, effectful initialization, and unsupported/dynamic handlers.

The concept explicitly requires transitive call analysis. A declared effect bound is an upper-bound contract, not a summary of direct effects alone: the checker must compare it with inferred effects over the complete reachable call closure. RT-06 dependency completeness and RT-07 proof boundaries must distinguish a declared effect from a verified fact. A declaration is an obligation, not proof that undeclared effects are absent. If call-graph completeness is missing or unresolved, the result must be UNKNOWN rather than acceptance.

### 3.4 Effect order and observations

An unordered set is insufficient if order changes observable behavior. Candidate semantics include:
- a set/row of possible effects with order specified operationally;
- ordered event traces;
- partial order / happens-before for concurrent effects;
- effect-specific laws permitting reordering only when proven safe.

The reference semantics must say which event orders are observable. Two writes to the same external resource are not interchangeable merely because their labels match.

[Scenario 37 — effect rows, handlers, and observable traces](RESEARCH-SCENARIO-37-EFFECT-ROWS-HANDLERS-AND-OBSERVATION.md) compares Koka's row-polymorphic handlers and duplicate labels with F*'s computation types and indexed-effect operation-set example. Both make clear that an effect bound, handler interpretation, and realized ordered trace are distinct evidence: an allowed-label set can deliberately forget order and multiplicity, while handlers can transform, forward, mask, or externally expose requests. COR-10/11 remain the executable LLMLang-side witnesses for observable handler outcomes and schedule order. No static row is treated as a substitute for those observations.

## 4. Ownership, borrowing, aliasing, and lifetime

### 4.1 Ownership alternatives

| Vector | Core discipline | Benefits | Costs / risks |
|---|---|---|---|
| Tracing GC | Runtime reclaims unreachable managed objects | Simple sharing and aliasing | Runtime costs; external resources still need lifecycle |
| Reference counting | Shared references maintain counts | Often deterministic reclamation | Cycles, atomic overhead, hidden costs, destructor reentrancy |
| Affine ownership | Value consumed at most once; dropping allowed | Strong resource transfer, less restrictive than linearity | Move/borrow rules and error-path diagnostics |
| Linear ownership | Value consumed exactly once | Strong resource/protocol accounting | Restrictive with branches and failures |
| Borrow checking | Temporary shared/exclusive borrows constrained by lifetimes | Prevents many use-after-free/data-race patterns | Lifetime diagnostics; async/self-reference complexity |
| Region/arena ownership | Values belong to a region with bulk lifetime | Predictable allocation and boundaries | Cross-region references and long-lived values |
| Runtime checks | Aliasing allowed; selected constraints checked dynamically | Flexible interoperability | Runtime failures; no automatic race freedom |

Memory ownership and external-resource ownership are different. A file descriptor, process, lock, transaction, socket, or capability may require a protocol even if its memory is garbage-collected.

### 4.2 Borrowing and aliasing alternatives

- Exclusive mutable borrow: one mutable access, excluding competing reads/writes during its lifetime.
- Shared immutable borrow: multiple readers, no mutation through those references.
- Interior mutability/synchronized cells: mutation behind runtime or synchronization-aware abstractions.
- Effect/permission-based access: operations require read/write permissions.
- Ownership transfer/message passing: mutable state transferred between tasks instead of shared concurrently.

These may coexist in layers, but interactions must be explicit. A static exclusive borrow does not define FFI or cross-process behavior. Unsafe/foreign code needs a trusted boundary and stated assumptions.

### 4.3 Lifetime alternatives

1. Inferred lexical lifetimes.
2. Explicit region parameters and constraints.
3. Reference-counted/dynamic lifetime management.
4. Ownership transfer with no borrowed references crossing task boundaries.
5. Hybrid: lexical local borrowing, owned messages across async boundaries, explicit OS-resource handles.

Questions include whether a borrow may cross await, whether a task may hold a lock while suspended, and what cancellation does to an in-flight resource protocol.

### 4.4 Resource protocols and failure paths

Resource types may encode Open, Closed, Committed, RolledBack, Joined, or Cancelled states. Define whether destruction is implicit/explicit, whether cleanup can fail, whether cancellation runs finalizers, whether resources can be duplicated/shared/transferred/borrowed, how external invalidation is represented, and how exhaustion/partial completion is observed.

POSIX read/write, interruption, EOF, partial completion, descriptor lifecycle, and process state are concrete conformance scenarios.

## 5. Capability and authority alternatives

### 5.1 Capability representation

| Vector | Authority model | Benefits | Risks / questions |
|---|---|---|---|
| Ambient authority | Runtime/process grants access implicitly | Conventional compatibility | Hidden dependencies; weak least-authority reasoning |
| Static capability types | Function/task context declares capability types | Visible authority in signatures/call graph | Declarations can be stale; dynamic delegation |
| Object capabilities | Possession of unforgeable object grants scoped access | Explicit delegation and least authority | Identity, serialization, revocation, lifetime |
| Dynamic tokens | Runtime-issued tokens checked at operation boundaries | Session/tenant-specific authority | Runtime enforcement and provenance |
| Static + dynamic hybrid | Static requirements plus runtime-scoped tokens | Early checking and actual authorization | Correspondence and bypass prevention |

A capability is authority to attempt an operation, not evidence the operation succeeds or behaves correctly. Authorization and effect semantics remain distinct.

### 5.2 Scope, delegation, revocation

Contracts must answer whether authority is scoped to resource/path/tenant/process/operation; can be attenuated; can be revoked and what happens to in-flight operations; can be duplicated or transferred; how it crosses async tasks, actor messages, packages, and FFI; and what happens when a token is missing, expired, stale, or unrecognized.

Static checking may establish possession of a capability-typed value. Only the runtime/security boundary can establish whether it is currently authorized.

[Scenario 38 — effects, capabilities, and authority](RESEARCH-SCENARIO-38-EFFECTS-CAPABILITIES-AND-AUTHORITY.md) compares Koka's “capability” terminology for a dynamically available effect handler with `cap-std` directory handles, F* cryptographic authorization tokens, and Wasmtime host imports. These examples make the distinction operational: effect bounds describe possible behavior, capabilities authorize scoped attempts, imports define runtime availability, and traces record realized actions. They are separate fields in the call and evidence contract; none is inferred from another without a stated checker/runtime guarantee.

## 6. Concurrency and memory-model alternatives

| Vector | Model | Benefits | Costs / obligations |
|---|---|---|---|
| Sequential core; parallelize pure work | Sequential deterministic source semantics; compiler parallelizes independent pure computations | Small semantic core and predictable observations | Does not expose concurrent coordination |
| Structured tasks/futures | Explicit task tree, join/cancel scopes, result/error propagation | Bounded lifetime and clear cancellation ownership | Detached tasks and failure propagation |
| Actors/message passing | Isolated state and typed messages | Reduces shared-memory race hazards | Protocol compatibility, ordering, mailbox bounds, supervision |
| Shared memory with locks | Shared mutation guarded by synchronization | Familiar and efficient in some systems | Deadlocks, lock ordering, cancellation, poisoning |
| Atomics/memory ordering | Explicit atomic operations and ordering constraints | Low-level performance | Complex formal model and backend burden |
| Ownership-based transfer | Exclusive ownership moves between tasks | Avoids concurrent aliasing for transferred state | Sharing needs protocols, copying, or immutable data |

Distinguish source concurrency semantics, permitted observable traces, runtime scheduling, compiler parallelization, and target memory model/ABI. Deterministic source semantics can permit parallel execution of pure independent computations. Actor execution can still have nondeterministic message arrival/order. Any shared-memory feature needs data-race, synchronization, atomic-order, cancellation, and failure rules.

## 7. Errors, state, and effects as one contract

Candidate error representations include algebraic result types for expected domain failures, checked exception/effect operations, panic/abort for unrecoverable faults, cancellation as a distinct control outcome, and resource exhaustion as a declared/environmental/profile-specific failure.

Do not collapse domain error, precondition violation, cancellation, resource failure, unsupported operation, and internal fault into one generic exception. Define which outcomes are catchable, retryable, observable, or allowed across ABI boundaries.

[Scenario 41 — typed errors and API evolution](RESEARCH-SCENARIO-41-TYPED-ERRORS-AND-API-EVOLUTION.md) compares explicit `Result`/error-set types and Swift typed throws with Go's open, wrapped error values. It makes caller exhaustiveness, deliberate type erasure, stable classification, and introducing a new failure case distinct compatibility questions. [Scenario 39](RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md) separately covers outcomes that must carry both error and owned value.

Stateful operations describe pre-state assumptions, permitted transitions, post-state guarantees, and partial completion. Ownership and typestate constrain legal calls, but runtime contracts must cover state changed by external actors.

## 8. Cross-product with RT-03 profiles

This table records pressure points, not compatibility verdicts.

| RT-03 profile | Type-system pressure | Effect/capability pressure | Ownership/concurrency pressure | Main risk |
|---|---|---|---|---|
| A — Pure Functional | ADTs, polymorphism, refinements | Explicit boundary effects and handlers | GC/regions/ownership at resource boundaries | Effect boundary may be too ad hoc for systems work |
| B — Imperative Linear | Typestate, refinements, alias-aware typing | Read/write and transitive effects | Affine/linear ownership, borrowing, lifetimes | Checker/proof complexity; aliasing widens impact |
| C — Actor/Concurrent | Message/protocol and task/result types | Per-actor authority, message-mediated effects | Actor ownership, task/resource lifecycle | Protocol, scheduling, trace, failure complexity |
| D — Effectful Functional | ADTs, effect polymorphism/rows, refinements | Effect inference, handlers, capability-gated operations | Explicit resource effects and owned handles | Handler semantics and hidden effect leakage |

No single ownership/capability choice follows mechanically from a profile. Profile D could use GC for ordinary values and affine handles for external resources; Profile B could still use structured tasks or actors for selected concurrency.

## 9. SPG, dependencies, and identity implications

### 9.1 Semantic distinctions to represent

The canonical representation may need distinct typed objects/references for type declarations, type constructors, refinement predicates and validation evidence, effect signatures/operations/handlers, capability requirements/values/delegation, resource types/lifecycle/ownership/borrows/finalizers, task/message/channel protocols, synchronization, error variants, and cancellation outcomes.

This is an inventory, not a final SPG schema. Edges should distinguish semantic dependency, type constraint, effect requirement, ownership/borrowing, capability authority, protocol interaction, implementation detail, and provenance.

### 9.2 Candidate hash boundaries

| Identity layer | Candidate semantic inputs to investigate | Not implied |
|---|---|---|
| Operation contract (glossary proposal OpHash) | Public type signature, pre/postconditions, observable state transitions, declared error/cancellation outcomes, externally observable effects, capability contract, protocol obligations | Internal implementation, proof-tool version, formatting |
| Implementation (glossary proposal ImplHash) | Body/IR, semantic type/effect elaboration, called implementation/contract dependencies, resource/synchronization behavior, behavior-relevant target/ABI/runtime assumptions | Provenance-only metadata; unrelated implementation detail |
| Conformance class (glossary proposal CCHash) | Contract plus defined compatibility/refinement class and conformance conditions | One concrete implementation's incidental structure |
| Verification/action/evidence identity | Exact inputs, assumptions, checker/solver/runtime versions, target profile, test/proof configuration and evidence | Must not be confused with semantic value identity |

This is a question map, not a finalized payload contract. Determine whether type/effect/capability declarations are embedded in canonical content, referenced through hash-relevant typed edges, or split between public contract and implementation. Each encoding must preserve exact semantics and dependency propagation.

A descriptive rename or alias should not automatically change operation identity unless it changes an externally observable contract or a defined nominal identity. A public effect requirement, error outcome, resource protocol, or concurrency guarantee may change the operation contract even if the ordinary return type is unchanged.

The concept's Stable ID + Content Hash proposal is not final. RT-24 leaves open stable entity identity versus content-addressed values with explicit selection/lineage. RT-04 supplies semantic distinctions needed for that decision but does not choose the identity model.

### 9.3 Dependency completeness

Transitive effect checking, alias/read-write analysis, capability propagation, and protocol analysis depend on sound dependency discovery. If dynamic dispatch, FFI, reflection, generated code, or runtime-loaded handlers can hide references, analysis must return explicit unknown/gap states rather than treating missing edges as empty.

RT-04 connects to RT-06 and snapshot-scoped reverse-reference completeness. An index digest alone does not prove the producer observed every relevant operation. Effect and ownership checkers need explicit observation/coverage assumptions.

## 10. Conditional incompatibility hypotheses

| Combination | Hypothesized tension | Evidence needed |
|---|---|---|
| Lazy evaluation + shared mutable state | Evaluation timing changes observed state | Small-step semantics and counterexamples |
| Unrestricted aliasing + unsynchronized mutation | Races and non-local behavior undermine deterministic reasoning | Memory-model scenarios and race analysis |
| Affine resources + implicit unrestricted duplication | Resource protocol can be bypassed | Static counterexamples and runtime tests |
| Static capability types + ambient authority | Declared and actual authority diverge | Adversarial delegation/revocation tests |
| Effect rows + dynamic handlers | Static effect set may not identify runtime behavior | Handler-resolution and unknown-effect tests |
| Async tasks + lexical borrows across suspension | Borrow may outlive owner or cross cancellation boundary | Lifetime/typechecking experiments |
| Typestate + external resource mutation | Static state may become stale | External invalidation/stale-handle tests |
| Effects + incomplete call graph | Transitive effects may be understated | Dynamic dispatch/FFI/generated-call coverage |
| Fine capabilities + coarse effect labels | Authorization may exceed semantic declaration | Least-authority scenarios |
| Nondeterministic concurrency + exact trace hashing | Identity/evidence may overfit one schedule | Trace equivalence and scheduler exploration |

These are conditional hypotheses, not final prohibitions.

## 11. Executable scenario corpus

Before choosing a vector, build fixtures with source program, initial state/environment, permitted observations, expected acceptance/rejection, and evidence oracle.

| ID | Scenario | Required observation |
|---|---|---|
| TYP-01 | Nominal vs structural interchange of same-shaped domain records | Assignability/coercion and reason |
| TYP-02 | Exhaustive match after adding error/state variant | Compile-time failure or explicit unknown behavior |
| TYP-03 | Refinement is true, false, undecidable, or times out | Proven/rejected/unknown/runtime-checked distinction |
| TYP-04 | Typestate transition with failure branch | Valid observable resource state |
| EFF-01 | Direct and transitive filesystem/network effects | Inferred/checked effects and diagnostics |
| EFF-02 | Handler intercepts, forwards, masks, or duplicates an effect | Exact observable behavior |
| EFF-03 | Same effect labels in different orders | Whether order is observable |
| EFF-04 | Dynamic dispatch or FFI performs undeclared effect | Reject/unknown/explicit unsafe boundary |
| OWN-01 | Shared reads overlap exclusive mutable borrow | Acceptance and reason |
| OWN-02 | Resource moved, duplicated, dropped, or borrowed twice | Ownership/lifecycle result |
| OWN-03 | Async suspension while holding borrow/lock/resource | Lifetime, deadlock, cancellation behavior |
| OWN-04 | Cleanup fails while another error is active | Error composition and resource state |
| CAP-01 | Capability missing, expired, revoked, attenuated, or delegated | Authorization and in-flight semantics |
| CAP-02 | Static capability exists but runtime token lacks scope | Static/dynamic rejection boundary |
| CON-01 | Independent pure computations run in parallel | Same observations as sequential reference |
| CON-02 | Shared writes with/without synchronization | Defined race/memory-order behavior |
| CON-03 | Actor message reorder, duplicate, loss, or cancellation | Protocol and trace semantics |
| ERR-01 | Domain error, precondition failure, cancellation, exhaustion, runtime fault | Distinct outcomes and catchability |
| POSIX-01 | Partial read/write, EOF, EINTR, close, peer invalidation | POSIX contract and resource ownership |
| HASH-01 | Public effect/error/resource contract changes, body unchanged | Contract/implementation/evidence identities changed |
| HASH-02 | Internal implementation changes, public contract unchanged | Contract stable; implementation/evidence changes as defined |
| HASH-03 | Descriptive alias/metadata only changes | No unintended semantic identity change |
| HASH-04 | Transitive callee effect/capability changes | Complete caller impact and hash propagation |

Each result records semantic profile, checker/runtime version, assumptions, and whether it is static, dynamic, tested, or formally proved. Passing scenarios validate only their covered subset.

## 12. Candidate research vectors

| Vector | Candidate combination | Advantages | Main cost / unresolved risk | Status |
|---|---|---|---|---|
| RT4-A Minimal static core | ADTs, nominal public types, local inference, explicit effect boundary | Small checker and diagnostics target | Resource/OS interaction may force extensions early | Candidate |
| RT4-B Refinement/contract-oriented | Static types, refinements, SMT/proof evidence, typed states | Strong connection to requirements and contracts | Solver limits, proof burden, stale runtime state | Candidate |
| RT4-C Effect-polymorphic | Effect rows and explicit handlers | Composable effect abstraction and transitive checking | Row/handler semantics and identity complexity | Candidate |
| RT4-D Ownership-oriented systems core | Affine/linear handles, borrowing, explicit lifetimes, typed state | Resource safety and low-level control | Checker complexity and async/FFI edges | Candidate |
| RT4-E Capability-oriented secure core | Explicit capability values, scoped delegation, effect/capability checks | Least authority and auditable access | Runtime enforcement and authority provenance | Candidate |
| RT4-F Actor/task-oriented concurrency | Typed protocols, structured tasks, isolated ownership | Clear isolation and concurrency contracts | Trace, cancellation, protocol, scheduling complexity | Candidate |
| RT4-G Hybrid layered model | ADTs, refinements at boundaries, effects/handlers, affine resource handles, capabilities, structured tasks | Simple pure subset plus stronger systems boundary | Integration complexity; composition must be validated | Candidate, not selected |

No vector has sufficient executable evidence to be accepted. RT4-G is a synthesis hypothesis, not a default recommendation.

## 13. Falsification criteria and confidence

A vector is weakened if its checker cannot express required POSIX/resource contracts without pervasive escape hatches; effect inference misses reachable observable effects; ownership rejects representative systems programs without a sound boundary; capabilities do not map to enforceable runtime authority; cancellation leaks resources or violates lifecycle contracts; static proof/runtime validation/unknown cannot be distinguished; behaviorally equivalent implementations become spuriously incompatible due to internal details; hashes omit behaviorally relevant inputs or include irrelevant metadata; or reference semantics and independent tests disagree.

Confidence:
- **High:** RT-04 materially constrains RT-03, RT-05, RT-07, RT-09, RT-10, RT-16, and RT-18; existing dependency map and runtime contracts support this.
- **Medium:** effect rows/handlers, affine ownership, and explicit capabilities are worth prototyping; integration costs and fit remain unvalidated.
- **Low:** any final ranking of type/effect/ownership/capability/concurrency vectors; no comparative executable corpus has run.

## 14. First executable evidence and remaining exit criteria

[RT-04 Prototype 01](PROTOTYPES/RT-04-01/README.md) now compares two deliberately limited declaration-level checker vectors. Its [results](RT-04-PROTOTYPE-01-RESULTS.md) and [scenario matrix](RT-04-PROTOTYPE-01-SCENARIOS.md) record 27 focused unit tests: primitive/closed effects, open effect rows, positive/negative/unknown refinement, transitive effect summaries, direct and transitive effect-bound checks, incomplete call-graph UNKNOWN cases, definite violations despite incomplete graphs, ambient versus propagated capabilities, affine duplicate consumption, branch-consistent and inconsistent joins, loop re-consumption, malformed CFG references, unknown resources/callees/effects, and malformed input. The prototype is not a compiler, source semantics, complete dependency analysis, runtime authorization mechanism, or architecture decision. Its `call_graph_complete` fixture metadata is an explicit assertion, not authenticated evidence that a source extractor discovered all calls; dynamic dispatch, FFI, generated calls, handlers, and reflection remain outside the model.

Remaining exit criteria:

1. Extend the branch-sensitive resource-flow prototype with source-to-CFG completeness evidence, symbolic path conditions, and explicit terminal-path/cleanup obligations; the current finite CFG model covers only repeated consumption and join-state agreement.
2. Select at least two cross-aspect candidate combinations derived from RT-03 profiles, not merely variants with hidden shared assumptions.
3. Implement small checker/reference models for type/effect propagation and resource/capability transitions.
4. Replace fixture-level call-graph completeness assertions with source/snapshot-bound evidence; test ordinary/generic calls, dynamic dispatch, handlers, generated calls, reflection, and FFI.
5. Test ownership/borrow/lifetime across error, cancellation, and async suspension.
6. Reconcile the observation model with RT-03 and POSIX scenarios.
7. Update dependency edges with evidence-backed relationships and conditional incompatibilities.
8. Revisit RT-24 identity only after hash-bearing semantic distinctions and scenario outcomes are understood.

RT-04 is complete for comparative-survey scope only after alternatives/questions are independently reviewed. It is not a selected architecture until executable scenarios, RT-03 reconciliation, and downstream identity/proof/runtime checks support that decision.


## Cross-profile trace evidence

See [RT-03 A/D × RT-04 A/B shared observable-trace cross-check](RT-04-RT-03-CROSS-PROFILE-TRACES.md), [RT-03 core semantics](CORE-LANGUAGE-SEMANTICS.md), and [executable scenario matrix](RT-04-PROTOTYPE-01-SCENARIOS.md). These documents should be reviewed together; the trace oracle is exploratory and does not select an architecture.

## Public-interface integration (2026-11-24; proposed)

Separate callable shape, type variance, effects, caller authority, ownership transfer and behavioral refinement at public-interface admission. Contravariant input and covariant result reasoning is conditional on the type/aliasing model; mutable generic positions may be invariant. A provider must preserve required observable effects, error alternatives, cleanup/borrow obligations, and declared progress, not merely have a smaller effect set. Test generic and stateful interfaces, joint protocol invariants, adapters, capabilities on exceptional exits, and conflicting provider declarations. Public names do not enter structural type identity merely because they are exported.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
