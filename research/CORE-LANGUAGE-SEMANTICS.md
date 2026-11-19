# RT-03 — Core Language Semantics: Candidate Models and Trade-offs

**Research area:** RT-03 — Core language semantics  
**Status:** exploratory research; no semantic profile selected  
**Source:** deep-research report “Существующие материалы и ограничения” in the user's local ChatGPT Library, imported and translated into the repository on 2026-11-17  
**Scope:** candidate semantic models, evaluation, state, errors, effects, determinism, concurrency, termination, modules, and downstream architectural impact

## 1. Executive summary

RT-03 is foundational: it must establish what a LLMLang program means before types, canonical representation, proofs, compiler transformations, runtime behavior, incremental computation, or semantic merge can be finalized.

The existing QF_LIA/Lean/Logos work defines a narrow relational fragment and a proof-boundary experiment. It does **not** define the complete semantics of LLMLang. Likewise, earlier discussions of Semantic Program Graph (SPG), Specification/Design/Implementation Graphs, `OpHash`/`ImpHash`, Typed IR, and fail-closed behavior do not yet amount to a complete execution model.

The research compares four coherent candidate profiles:

- **A — Pure Functional Core:** immutable values, pure functions, strict evaluation, explicit result values, deterministic sequential execution.
- **B — Imperative Linear Core:** explicit state transitions and mutation, with ownership/linearity constraints and deterministic sequencing.
- **C — Concurrent/Actor Core:** isolated agents and message passing, with asynchronous scheduling and potentially nondeterministic traces.
- **D — Effectful Functional Core:** pure functional values and composition, with explicitly typed and handled effects such as state and I/O.

No profile is selected. Profile A is the simplest formal baseline; B offers direct imperative expression and potentially efficient mutation; C is a high-cost concurrency-oriented alternative; D is a compromise that keeps effects explicit while retaining a functional core. These are research profiles, not mutually exclusive final language editions: later synthesis may combine compatible vectors or define a small core with controlled extensions.

The key recommendation is procedural: preserve multiple viable vectors, test compatibility with RT-04 and downstream areas, and postpone normative selection until cross-aspect synthesis.

## 2. Existing evidence and scope boundaries

The project already contains a conceptual SPG direction, separate logical graph layers, semantic identity discussions, a formal-verification architecture, and a bounded relational verification prototype. Those materials provide constraints and questions, not a complete semantic definition.

The current QF_LIA work covers a restricted, deterministic relational subset. It is useful for determining what can be represented and checked in that fragment, but it cannot settle general recursion, mutable state, I/O, resource behavior, concurrency, or the complete observation model.

A formalization technique must also be distinguished from language semantics. Choosing operational rather than denotational semantics is a choice of formal presentation; it does not by itself decide whether the language is functional or imperative, pure or effectful, strict or lazy.

## 3. Semantic decision vectors

The following dimensions should be decided explicitly. They are related, but should not be collapsed into one early binary choice.

### 3.1 Value and computation model

1. **Pure functional:** expressions denote values; functions compose over immutable data. Effects are absent from the pure core or represented explicitly.
2. **Imperative state-transition:** commands transform a store or machine state. Assignment, sequencing, and mutable locations are first-class semantic operations.
3. **Functional/imperative hybrid:** pure expressions form the default, while mutation or effects are available through constrained constructs, references, or effect handlers.
4. **Actor/agent model:** computation consists of isolated processes with local state that coordinate through messages. Shared memory is absent or tightly restricted.
5. **Declarative/dataflow model:** computation is described by relations, rules, or data dependencies, potentially using fixed-point semantics. This is a useful comparison point, but is not currently a leading candidate for the LLMLang core.

### 3.2 Evaluation strategy

- **Strict / call-by-value:** evaluate arguments before the call, with a specified order (for example, left-to-right). This is familiar and comparatively predictable.
- **Lazy / non-strict:** evaluate an expression only when its value is needed. This enables deferred and potentially infinite structures, but introduces sharing, memoization, and evaluation-order questions.
- **Parallel/asynchronous evaluation:** independent computations may proceed concurrently. The language must define synchronization, failure propagation, and whether observable outcomes may vary.
- **Mixed strategy:** strict evaluation by default with explicitly lazy or asynchronous constructs. This can be practical, but each construct needs clear rules to avoid inconsistent expectations.

A strict strategy is a simpler starting point. Laziness should not be combined casually with shared mutable state: delayed evaluation can make the timing of mutations surprising. Any such combination needs explicit constraints and tests.

### 3.3 Purity and state

- **Pure core:** no implicit mutation. I/O, time, randomness, and other environmental interactions are explicit boundaries.
- **Local mutable state:** mutation is permitted within a bounded scope, such as a function or owned local resource.
- **Shared/global state:** modules or concurrent computations can observe and mutate shared locations. This substantially increases aliasing, dependency, race, and merge complexity.
- **Effect-mediated state:** state changes are expressed through declared effects and controlled handlers rather than unrestricted mutation.

The important distinction is not simply whether state exists, but whether it is local, shared, observable, and represented in the type/effect and dependency models.

### 3.4 Errors, exceptions, and cancellation

Candidate mechanisms include:

- **Explicit result values** such as `Result`/`Maybe`, making failure part of function results and type checking.
- **Exceptions** with specified propagation and handler selection. This is familiar but introduces non-local control flow and implicit failure paths.
- **Fail-closed termination** for unsupported or invalid cases, where no successful result is produced and execution stops. The exact boundary between compile-time rejection, runtime failure, and proof failure must be explicit.
- **Cancellation semantics** for concurrent work: failure may cancel sibling computations, remain local to one task, or follow a structured-concurrency policy.

These mechanisms need not be identical for every failure class. The language must distinguish ordinary domain errors, violated preconditions, resource exhaustion, unsupported constructs, and internal/runtime faults.

### 3.5 Determinism

- **Strict determinism:** fixed inputs and declared environment produce one observable result and one defined sequencing behavior.
- **Controlled nondeterminism:** multiple outcomes are permitted but are explicitly represented, bounded, or supplied by a declared source such as a seed or scheduler.
- **Uncontrolled nondeterminism:** scheduling, races, time, or randomness can change behavior without being captured in the program's semantic inputs.

For LLMLang, hidden nondeterminism is especially costly: it complicates reproducible builds, evidence reuse, semantic identity, debugging, and merge. Time and randomness can still be supported as explicit effects or environment inputs.

### 3.6 Effects and observable behavior

The semantics must define what an observer can distinguish. Candidate observations include:

- returned values and termination/divergence;
- explicit errors and failure classes;
- state changes visible outside a local scope;
- I/O and emitted events;
- resource acquisition, release, and exhaustion;
- message sends/receives and concurrency traces;
- declared environmental interactions.

A pure core may define observations narrowly and expose effects through explicit primitives. An effectful core can make the effect set part of function signatures and semantic identity. An imperative core must specify which state changes are observable and when.

The observation model is a prerequisite for semantic equivalence: two programs cannot be declared equivalent until the project says which differences count.

### 3.7 Concurrency and interaction

Options range from sequential execution, to explicit parallel combinators/futures, to isolated actors communicating by messages. Shared-memory concurrency is the most demanding option because it requires a memory model, synchronization semantics, and a strategy for data races.

A deterministic language may still execute independent pure computations in parallel if the observable result is unchanged. Therefore, parallel implementation is not necessarily the same thing as nondeterministic source semantics. The distinction between semantic concurrency and compiler/runtime parallelization must be preserved.

### 3.8 Termination and resource behavior

The language must decide how it treats general recursion, divergence, partial computations, stack/heap limits, timeouts, and resource exhaustion. A big-step semantics may simply fail to derive a result for a diverging computation; an operational semantics can represent its execution steps.

Resource behavior is particularly important for effects and runtime services. The semantics should say which resource failures are observable, which are implementation-defined, and which must be rejected or bounded by a profile.

### 3.9 Modules and composition boundaries

Module semantics must clarify visibility, initialization, state ownership, imports, cycles, and the scope of effects. Pure modules are comparatively easy to compose. Shared mutable module state creates wider dependencies. Actor modules introduce protocol and message compatibility. Effectful modules require effect requirements and handlers to compose predictably.

## 4. Candidate semantic profiles

### 4.1 Profile A — Pure Functional Core

**Shape:** immutable values, pure functions, strict call-by-value evaluation, sequential source semantics, explicit result values, and no implicit mutable state.

**Formal model:** expressions can be described compositionally using a functional or denotational account; an operational account can still be used for execution details. Divergence is represented as absence of a terminating result (often written `⊥`).

**Strengths:** strongest initial compositionality; comparatively simple equivalence reasoning, canonicalization, proof decomposition, deterministic testing, and semantic hashing. Independent pure computations may be parallelized as an implementation optimization without changing source semantics.

**Costs and limitations:** I/O, resources, and state need explicit interfaces or effect constructs. Some conventional algorithms may be less direct. A strict pure core does not by itself solve resource management or external interaction.

**Cross-aspect impact:**
- RT-04 can begin with a relatively small type model, but explicit effects/capabilities are needed when external interaction is added.
- RT-05 can hash immutable semantic structure with relatively clear boundaries.
- RT-06 benefits from local, explicit dependencies.
- RT-07 has the most straightforward initial proof story among these profiles.
- RT-09/RT-10 can use a compact functional IR and a runtime boundary for external effects.
- RT-11 can reuse results when pure inputs are unchanged.
- RT-15 can often merge independent changes when their semantic dependencies do not overlap.

### 4.2 Profile B — Imperative Linear Core

**Shape:** explicit commands and state transitions, mutable locations, sequencing, and ownership/linearity rules to constrain aliasing and resource access.

**Formal model:** a small-step operational semantics over configurations such as program counter, environment, and store. The evaluation order and mutation visibility must be fixed.

**Strengths:** direct expression of algorithms, in-place updates, explicit control of memory/resource behavior, and a familiar programming model. It can map efficiently to conventional machine execution.

**Costs and limitations:** proofs must account for stores, aliasing, ownership, and state invariants. Shared state increases dependency closure and can make seemingly local changes globally observable. Semantic merge must distinguish independent writes from conflicting writes.

**Cross-aspect impact:**
- RT-04 likely needs ownership, borrowing/aliasing, lifetimes, and possibly linear capabilities.
- RT-05 must represent stateful operations and relevant memory/ownership distinctions.
- RT-06 must model read/write dependencies and conservative impact propagation.
- RT-07 requires state-transition and memory-safety reasoning.
- RT-09/RT-10 need explicit memory operations and runtime support.
- RT-11 may need broader invalidation where state or aliasing affects results.
- RT-15 must treat conflicting writes and reordered dependent commands as semantic conflicts.

### 4.3 Profile C — Concurrent/Actor Core

**Shape:** isolated agents with local state, asynchronous execution, and communication through messages rather than unrestricted shared memory.

**Formal model:** labelled transition systems or related process semantics, with transitions for local computation and message passing. A program may have multiple allowed execution traces.

**Strengths:** natural representation of distributed and highly concurrent systems; isolation reduces some shared-memory race hazards; independent agents can be reasoned about locally when protocols are explicit.

**Costs and limitations:** scheduling and message ordering can create nondeterministic traces. Deadlocks, message loss/failure, cancellation, supervision, and protocol evolution require precise treatment. General verification and semantic merge are significantly harder.

**Cross-aspect impact:**
- RT-04 needs channel/message types, capabilities, task ownership, and protocol constraints.
- RT-05 needs agent boundaries and message/protocol representation.
- RT-06 must track inter-agent dependencies and message-mediated effects.
- RT-07 may require model checking and temporal reasoning in addition to ordinary functional proofs.
- RT-09/RT-10 need asynchronous IR and a scheduler/message runtime.
- RT-11 may isolate some rebuilds by agent, but cross-agent contracts can widen impact.
- RT-15 can merge independent agent changes more easily than protocol changes; shared-channel and ordering conflicts remain difficult.
- RT-16 gains isolation but must address message validation, denial of service, and capability boundaries.
- RT-17 faces harder debugging and replay unless deterministic tracing is provided.

This profile is a high-cost option for the initial core, but it may remain valuable as a later extension or execution model.

### 4.4 Profile D — Effectful Functional Core

**Shape:** immutable values and functional composition, with effects such as state, I/O, exceptions, resources, or asynchronous work explicitly declared and interpreted by handlers.

**Formal model:** computations can be modelled as values paired with effect requests or as transitions over an explicit effect context. A schematic stateful judgment is `⟨σ, e⟩ ⇓ ⟨σ', v⟩`, where `σ` represents the relevant effect context.

**Strengths:** preserves a pure subset while providing controlled interaction with the environment. Effects can be visible in signatures and checked by RT-04. Pure regions remain amenable to local reasoning, caching, and optimization.

**Costs and limitations:** effect composition and handler semantics add complexity. The project must define the core effect vocabulary, handler laws, effect ordering, resource finalization, and behavior for unsupported effects. An incomplete effect system can hide rather than eliminate side effects.

**Cross-aspect impact:**
- RT-04 needs effect annotations, effect constraints, and capability/handler rules.
- RT-05 must include semantics-relevant effect declarations in canonical identity.
- RT-06 should distinguish pure dependencies from effectful dependencies.
- RT-07 can prove pure regions compositionally and handle effect laws at explicit boundaries.
- RT-09 can lower to functional SSA plus effect operations.
- RT-10 implements effect handlers and platform services.
- RT-11 can cache pure computations while invalidating effect-dependent results according to their declared inputs.
- RT-15 can merge pure changes more freely; changes to effect declarations or handlers may conflict.
- RT-16 can use declared effects to enforce least authority, provided declarations are sound.

## 5. Compatibility, orthogonality, and tensions

Some choices are largely orthogonal; others require explicit restrictions.

### 5.1 Mostly orthogonal choices

- **Big-step vs small-step** is a formalization choice, not a complete semantic profile. Both can describe multiple value/state models.
- **Evaluation strategy and state** are not inherently identical decisions. Lazy evaluation can exist with effects, but its interaction with mutation requires careful rules.
- **Module boundaries** can be introduced in pure, imperative, or effectful models, although their semantics differ.
- **Implementation parallelism and source-level nondeterminism** are distinct. A compiler may parallelize pure computations while preserving deterministic observations.

### 5.2 Important tensions

- **Laziness with shared mutable state:** delayed evaluation can change when state is read or written. Avoid this combination in the initial design unless a precise discipline is provided.
- **Unrestricted shared state with nondeterministic concurrency:** creates races and unstable outcomes. Prefer isolation, ownership, or explicit synchronization.
- **Determinism with hidden time/randomness:** incompatible unless environmental inputs are explicit or controlled (for example, a declared seed).
- **Pure core with arbitrary implicit effects:** contradictory. Effects must be absent, explicit, or handled at a defined boundary.
- **Actor semantics without meaningful concurrency:** can add protocol and runtime complexity without delivering the main benefit.
- **Mixed evaluation strategies:** need construct-level rules and conformance tests to prevent surprising semantic drift.

These are conditional incompatibilities, not proof that every mixed design is impossible. The exact conditions belong in later compatibility analysis.

## 6. Comparative assessment

The following is a qualitative research heuristic, not a measured benchmark or accepted ranking.

| Criterion | A — Pure | B — Imperative/linear | C — Actor/concurrent | D — Effectful functional |
|---|---|---|---|---|
| Formalization effort | Low | High | Very high | Medium |
| Determinism by default | High | High if order is fixed | Lower; trace-based | High for sequential effects |
| Expressiveness for stateful algorithms | Lower without effects | High | High for distributed work | High with declared effects |
| Implementation complexity | Lower | High | Very high | Medium |
| Proof decomposition | Strong | Requires state/ownership reasoning | Requires concurrency reasoning | Strong for pure parts |
| Incremental analysis | Relatively local | Depends on state/aliasing | Depends on protocols | Local for pure parts; effect-sensitive |
| Semantic merge | Comparatively tractable | Write/state conflicts | Protocol/trace conflicts | Tractable for pure parts; effect conflicts |
| Potential low-level efficiency | Depends on optimization/allocation | Strong in-place potential | Runtime overhead; scalable concurrency | Depends on lowering and effect implementation |

No profile dominates all criteria. The ratings should be revisited with representative LLMLang programs and reproducible measurements.

## 7. Implications for LLMLang architecture

### 7.1 Semantic Program Graph and identity

SPG must represent every distinction that changes observable semantics. Depending on the selected profile, these may include evaluation order, state reads/writes, effect declarations, error paths, resource operations, message protocols, and environment inputs.

`OpHash` should commit to the immutable operation semantics and its declared contract-relevant behavior. `ImpHash` should commit to the concrete implementation and all semantics-relevant implementation inputs. The exact payloads and dependency closure remain RT-05 decisions; this research does not settle them.

### 7.2 Dependency analysis and incremental computation

Pure computations offer the clearest local dependency model. Mutation requires read/write and alias analysis. Effects require dependency tracking for effect handlers and environmental inputs. Actors require protocol and message-flow dependencies.

If dependency completeness is unknown, reuse must remain conservative. A semantic change that changes the relevant implementation identity should propagate through the existing identity/invalidation mechanism; no separate ad hoc invalidation rule should be needed for a correctly captured dependency.

### 7.3 Formal verification

A small deterministic fragment can be a useful proof target, but it must not be mistaken for the full language. Profile A offers the easiest first proof slice. B needs store and ownership invariants. C may need temporal logic/model checking. D needs effect semantics and handler laws.

Lean/Logos/QF_LIA are tools for selected proof obligations, not a reason to constrain the whole language to the current relational fragment.

### 7.4 Compiler and runtime

The compiler and runtime must implement source semantics rather than define them. IR design follows the chosen semantic distinctions: functional values, explicit stores, effect operations, or message-passing primitives. A target that cannot implement a construct must reject it or report a declared profile restriction; it must not silently weaken semantics.

### 7.5 Git and semantic merge

Semantic merge depends on the observation model and dependency boundaries. Pure independent changes are easier to merge. Stateful operations need read/write conflict analysis. Effectful changes need effect-set and handler awareness. Actor changes need protocol and message-order awareness. The current Git representation/merge research remains useful, but a merge policy cannot be finalized before RT-03 and RT-05 are sufficiently stable.

## 8. Downstream dependency updates

The research supports the following dependency hypotheses. These are not normative constraints and should be validated as the affected research areas progress.

| Source → target | Relationship | Why it matters | Confidence |
|---|---|---|---|
| RT-03 → RT-04 | Constrains | Types, effects, ownership, capabilities, and memory rules must preserve the selected evaluation and observation semantics. | Strong hypothesis |
| RT-03 → RT-05 | Constrains | Canonical graph kinds and identity must capture distinctions that affect program meaning. | Strong hypothesis |
| RT-03 → RT-06 | Requires | Sound dependency/impact analysis needs defined state, effects, evaluation, and observable behavior. | Strong hypothesis |
| RT-03 → RT-07 | Requires | Proofs need a precise source fragment, execution model, and observation boundary. | Strong hypothesis |
| RT-03 → RT-09 | Constrains | IR lowering and optimization must preserve source semantics. | Strong hypothesis |
| RT-03 → RT-10 | Constrains | Runtime behavior must implement evaluation, effects, errors, concurrency, and resource semantics. | Strong hypothesis |
| RT-03 → RT-11 | Influences | Purity, state, and effects determine cache inputs and invalidation scope. | Strong hypothesis |
| RT-03 → RT-14 | Constrains | AI-proposed changes must be checked against explicit language semantics. | Strong hypothesis |
| RT-03 → RT-15 | Influences | Semantic equivalence and conflict detection depend on state, effects, ordering, and concurrency semantics. | Strong hypothesis |
| RT-03 → RT-16 | Influences | The semantic model defines the guarantees and threat boundaries available to security controls. | Open hypothesis |
| RT-03 → RT-18 | Influences | Semantic evolution affects conformance profiles and compatibility guarantees. | Strong hypothesis |

## 9. Open questions and falsification plan

The following questions remain unresolved:

1. Which effects belong in the core, and which belong in libraries or runtime interfaces?
2. Is state absent, local/owned, or generally mutable?
3. Which errors are values, exceptions, compile-time rejections, or fail-closed runtime failures?
4. What exactly is observable for equivalence: values only, or also state, I/O, resources, traces, and termination?
5. Is strict evaluation the default? Are lazy constructs required?
6. Is source-level concurrency in the core, an effect/library, or a later extension?
7. How are cancellation, resource exhaustion, and finalization specified?
8. What module initialization and state-sharing rules are required?
9. Which semantic subset can be independently formalized and executed first?

Recommended experiments:

- **Reference interpreters:** implement small, isolated interpreters for the viable profiles over the same representative program corpus.
- **Semantic equivalence and refactoring:** compare programs after reorderings, extraction, inlining, and other transformations; identify which transformations preserve observations.
- **State/effect tests:** exercise aliasing, mutation order, exception propagation, resource cleanup, and undeclared effects.
- **Concurrency scenarios:** test message ordering, cancellation, failure isolation, and reproducible replay.
- **Merge scenarios:** create independent and conflicting changes to pure functions, stateful operations, effect declarations, and actor protocols.
- **Proof experiments:** formalize a small property in Lean (and use model checking where appropriate) for each profile; compare proof complexity and trusted assumptions.
- **Performance and authoring evaluation:** benchmark representative workloads and assess whether LLM-generated changes remain understandable and reviewable.

Each experiment should state its hypothesis, assumptions, fixtures, reproducible commands, and failure criteria. A profile should be downgraded or rejected only when a concrete requirement or experiment demonstrates a material incompatibility.

## 10. Research conclusion and next steps

The most defensible current position is to retain A and D as strong candidates for a formal, compositional core; retain B as a viable option where direct state and low-level control prove necessary; and keep C as a higher-cost concurrency direction or extension. This is a prioritization for further investigation, **not** a selection of the language semantics.

Next steps:

1. Cross-check the candidate vectors against RT-04 type/effect/ownership/capability research.
2. Define a common observable-behavior vocabulary and a minimal semantic test corpus.
3. Specify one small reference fragment for at least two candidate profiles and compare formalization effort.
4. Validate the RT-03 dependency edges through concrete RT-05, RT-06, RT-07, RT-09, RT-10, RT-11, RT-15, RT-16, and RT-18 work.
5. Normalize the resulting vectors for whole-specification synthesis; do not transfer any profile into `draft/` until an explicit project decision is made.

## 11. Source provenance

This repository document is an English research synthesis of the deep-research report “Существующие материалы и ограничения” stored in the user's local ChatGPT Library (created 2026-11-17; 370 extracted text lines). The source report's final paragraph claimed that this document and related files had already been committed under abbreviated commit IDs. That historical claim was not independently verifiable and was contradicted by the repository state checked during this import: `research/CORE-LANGUAGE-SEMANTICS.md` did not exist on `main`. The current repository changes, rather than the source report's claimed commit IDs, are the authoritative record of this import.


**Cross-aspect research:** RT-04's [type/effect/ownership/capability alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) compares candidate mechanisms against profiles A–D. It does not select a profile; shared observations and executable cross-profile scenarios remain open.


**Executable cross-profile evidence:** [RT-03 A/D × RT-04 A/B shared observable-trace cross-check](RT-04-RT-03-CROSS-PROFILE-TRACES.md) and its [scenario fixtures](PROTOTYPES/RT-04-01/test_rt03_rt04_cross_profile.py). This is a finite compatibility oracle, not a selected semantic profile or complete reference interpreter.


## 12. Executable reference-semantics slice (2026-11-18)

A first bounded interpreter now exists for the two leading compositional candidates A and D:

- [Reference interpreter](PROTOTYPES/RT-04-01/rt03_reference.py)
- [Executable tests](PROTOTYPES/RT-04-01/test_rt03_reference.py)
- [Shared cross-profile trace report](RT-04-RT-03-CROSS-PROFILE-TRACES.md)
- [Scenario matrix](RT-04-PROTOTYPE-01-SCENARIOS.md)

The fragment evaluates literals, strict left-to-right integer addition, left-to-right sequencing, explicit result-shaped values, and effect requests. A rejects effect requests. D admits only declared effects and uses finite in-memory fixture handlers for file/state/network operations. Traces preserve event order, operation, payload, outcome, result, and final fixture state.

This is meaningful executable evidence beyond hand-authored trace fixtures, but it is not a complete reference semantics and does not select A or D. It omits parsing, binding, functions/recursion, general handlers and effect-row inference, Result propagation, exceptions/cancellation, resource lifecycle, concurrency, divergence, and source-to-model completeness. The handlers are deterministic in-memory fixtures, not platform runtime semantics. The RT-04 checker remains a separate declaration-level model.

The original proposed validation gate—explicit Result propagation, cancellation, and resource acquire/use/release—has since been implemented in the bounded A/D evaluators and independently structured resource/path models. See the current coverage inventory in [RT-03/04 Shared Semantics Corpus v1](RT-03-04-SHARED-SEMANTICS-CORPUS.md). Those models cover only their declared finite fixture protocol and do not establish source-level completeness or select an ownership model.

Path-feasibility evidence now includes exhaustive finite assignments, repeated-marker correlation, a bounded DPLL comparison, generated Boolean formula cross-checks, a conservative result contract, one real process-enforced solver deadline, and a finite mutation-identity counterexample in [Scenarios 98–104](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md). A replayable assignment can establish one possible path, but unresolved solver results and unverified negative claims cannot justify pruning a may-path. Broader timeout/failure distributions, hard formula families, alias-/call-aware mutation, and source parser/CFG correspondence remain open.


## 13. Differential evaluator cross-check

A second evaluator, [`rt03_smallstep.py`](PROTOTYPES/RT-04-01/rt03_smallstep.py), independently implements the same bounded fragment using explicit continuation/value stacks rather than recursive evaluation. [Differential tests](PROTOTYPES/RT-04-01/test_rt03_differential.py) compare ordered traces, results, and final state/file fixtures across pure, state, file, and network cases, including a generated corpus of short state-write sequences.

The recursive and small-step implementations agree on their tested finite corpus, including explicit Result propagation, synchronous cancellation, and bounded resource cleanup. This is implementation-level cross-checking, not an independently authored specification, proof, or external audit: both models were developed against the same exploratory contract. Independent review remains a separate gate. The broader observation model still omits exceptions, asynchronous/concurrent semantics, general ownership and borrowing, divergence, and source-to-model completeness.
