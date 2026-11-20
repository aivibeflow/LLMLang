# RT-03/04 Shared Semantics Corpus v1

**Status:** Scenario inventory and bounded comparison of typed calls, state, and actor schedules

**Updated:** 2026-11-20

**Scope:** Bounded expressions, effects, Result, cancellation, branches, resources, typed calls, private state, finite actor scripts, path-feasibility solver outcomes, and one analytical resource-return scenario in Prototype RT-04-01 and associated studies.

## 1. Purpose

RT-03 profiles and RT-04 checker vectors need shared inputs and an explicit observation boundary before their results can be compared. The repository already contains an executable A/D reference slice, a second small-step evaluator, a structural path model, resource outcome rules, and declaration-level RT-04 checkers. The current corpus is therefore a set of related finite experiment suites, not one end-to-end source-language conformance suite.

This inventory maps concrete scenario families to their evidence and records the next missing comparisons. A result from one family must not be generalized to constructs or profiles it does not exercise.

## 2. Observation record

For completed reference evaluations, compare:

- selected semantic profile and terminal outcome;
- ordered effect/resource events, including operation, payload, and outcome;
- returned value, including explicit `ok` or `error` data;
- final local state, file fixture, and resource map;
- whether an expression was skipped after Result propagation or cancellation.

RT-04 declaration checkers produce a different observation: accepted, rejected, or unknown status plus inferred effect/capability summaries and diagnostics. These are static checker outputs. They do not establish that a reference evaluation's events are authorized, implemented, or complete.

## 3. Existing executable scenario families

| ID | Scenario and distinguishing input | Current evidence | What it distinguishes | Boundary |
|---|---|---|---|---|
| COR-01 | Strict pure arithmetic, nested addition, malformed arity | `test_rt03_reference.py`, `test_rt03_differential.py` | Evaluation result and fail-closed malformed input under A/D evaluators | No variables, functions, recursion, or source parser |
| COR-02 | Explicit Result error followed by a later operation | `test_rt03_reference.py`, `test_rt03_differential.py` | Ordinary `sequence` treats Result as data; `result_sequence` propagates the first error and skips later work | Result is an explicit fixture constructor; no general exception model or implicit call propagation |
| COR-03 | Declared and undeclared effect requests; file/network handler outcomes | Reference and differential suites | Profile A rejects effects; D requires declaration; deterministic fixture handlers preserve request and outcome | In-memory handlers only; no real OS/network behavior or handler algebra |
| COR-04 | Reordered state writes/read operations | Reference, differential, and cross-profile suites | Event order and final state are observable; set-like RT-04 summaries lose order and payload | One isolated fixture store; no aliasing or concurrency |
| COR-05 | Cancellation before a later operation, including nested continuation positions | Reference and differential suites | Cancellation is distinct from Result error, stops pending work, and preserves prior completed effects | No asynchronous task tree, sibling cancellation policy, or scheduler nondeterminism |
| COR-06 | Literal conditional branch and unknown-condition path fork | Differential, path-model, resource-rule, and mutable-predicate suites, [Scenarios 98](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md)–[101](RESEARCH-SCENARIO-101-SOLVER-VS-TRUTH-TABLE-PATHS.md), and [Scenarios 102](RESEARCH-SCENARIO-102-SOLVER-UNKNOWN-AND-SOUND-PATH-PRUNING.md)–[107](RESEARCH-SCENARIO-107-SOURCE-DERIVED-CALL-ALIASES.md) | Concrete evaluators take one branch; a seven-marker fixture covers 128 assignments/eight paths; repeated marker identity removes inconsistent choices; finite truth-table and pinned SymPy DPLL2 models agree on the original route set; Scenario 102 adds 128 fixed-seed formulas and replayable witnesses. Scenarios 102–103 retain timeout/UNKNOWN/error and untrusted UNSAT routes; 103 kills and reaps a worker on a real query deadline. Scenario 104 exhausts a mutable Boolean local: conflating the source name loses reachable routes, while versioned values plus the toggle transition match the concrete route set. Scenario 105 checks pure/toggle/may-write call summaries; unknown call effects retain all state-pair routes. Scenario 106 exhausts exact, disjoint, may-alias, and unknown call-site field targets; incomplete sets retain every possible route. Scenario 107 derives call targets from a bounded AST: branch joins preserve routes but lose alias/value correlation and can add infeasible ones. | One immutable predicate corpus and one finite AST-derived alias/call adapter, but no LLMLang parser, source/CFG completeness proof, path-sensitive points-to analysis, loop analysis, or general call graph; only one easy and one pigeonhole family are timed locally; no repeated performance distribution, checked proof, worker memory/concurrency isolation, source parser/CFG extraction, effects, integer theories, or source-level path proof |
| COR-07 | Resource acquisition, use, release, nested LIFO cleanup, Result error, cancellation, acquisition/release failures | Differential, path-model, and resource-rule suites | Cleanup order, precedence, skipped bodies after acquisition failure, retained resources, and exact cleanup errors | Bounded scope protocol only; no borrow/alias, transfer/return, arbitrary destructor, async or concurrent cleanup |
| COR-08 | RT-04 effect bounds, open-row annotations, call sites, affine resource CFGs, and scoped capability grants | `test_rt04_model.py`, cross-profile suite | Static declaration checks can accept/reject/report unknown under supplied graph and grant assumptions | Supplied completeness and grants are trusted fixture inputs; no source extraction or runtime enforcement |
| COR-09 | Typed calls, immutable bindings versus private mutable locals, invalid calls in unselected branches | [Typed call fixtures](PROTOTYPES/RT-04-01/test_rt03_typed_calls.py) | The same workload can return the same scalar values under A and B. Changing write order in B can change the result without changing the RT-04 projection | First-order, acyclic calls with scalar values and fresh per-invocation locals |
| COR-10 | Private, observable, and fallible interpretations of explicit state operations in D | [Handled state fixtures](PROTOTYPES/RT-04-01/test_rt03_typed_calls.py) | A, B, and D agree on the private total-state workload. Logging distinguishes runs with the same returned value. Rejecting a write changes the terminal outcome for the same effectful body | One scoped Int state effect, with built-in handlers and a terminal write failure |
| COR-11 | Closed actor group under per-sender FIFO or sorted delivery, with isolated failure or group abort | [Actor fixtures](PROTOTYPES/RT-04-01/test_rt03_actor_model.py) | The final scalar can agree across profiles while exact traces differ. Noncommuting writes distinguish ordering policies. Failure policies determine which deliveries can still occur | Finite scripted producers, a single receiving actor, one atomic turn per delivered message |
| COR-12 | Two-actor finite send/receive protocols | [Blocking protocol fixtures](PROTOTYPES/RT-04-01/test_rt03_blocking_protocol.py) | Mutual send-first blocks under rendezvous but completes with buffering; crossed request/reply completes under rendezvous | Two actors and one send/receive per actor; no cancellation, failure, selective receive, or source/runtime correspondence |
| COR-13 | Owned resource returned across fallible local cleanup, with an error-return branch | [Research Scenario 35](RESEARCH-SCENARIO-35-RESOURCE-RETURN-AND-CLEANUP.md), [ownership projection](PROTOTYPES/RT-04-01/rt03_return_cleanup.py), [RT-04 type-envelope probes](PROTOTYPES/RT-04-01/test_rt04_owned_result_boundary.py) | On cleanup failure, current RT-03 returns CleanupFailed without the pending value while transfer-first retains it and requires an error-with-value outcome; caller must dispose of that value before propagating failure. RT-04 B accepts primitive Result but not Owned or ErrorWithValue constructors | Ten ownership-projection tests plus three passing checker probes; typed-call probe skipped on Python 3.9. Staged transfer, static borrow proof, source correspondence, and independent review remain open |

## 4. Candidate-profile coverage

| Candidate/profile | Executable coverage | Missing evidence before cross-profile score |
|---|---|---|
| RT-03 A — pure strict core | COR-01, explicit Result values/propagation, cancellation outcome, conditional selection, and strict scalar calls in COR-09 | Module semantics, recursive source semantics and divergence/effect inference; [Scenario 36](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) has only an abstract cost model, not a source evaluator; integration of call semantics with Result and cleanup, and source-level type rules |
| RT-03 D — effectful functional core | COR-01–COR-07 and scoped Int state handlers across typed calls in COR-10 | Handler-aware summaries, effect rows, general handler composition, failure recovery, environmental nondeterminism, and concurrency |
| RT-03 B — imperative linear core | COR-09 executes private scalar locals with lexical lifetimes and ordered assignment | Aliasing, borrowing, definite assignment beyond initialized lexical cells, transfer, and cleanup across calls |
| RT-03 C — isolated concurrent/actor core | COR-11 explores all enabled schedules of closed finite scripts, with trace replay and explicit failure policy | Typed protocols, selective receive, multiple receiver lifecycles, async cancellation and cleanup, fairness, liveness, and runtime correspondence; see [Scenario 94](RESEARCH-SCENARIO-94-SCHEDULER-FAIRNESS-AND-LIVENESS.md) for fairness assumptions and a bounded discriminator |
| RT-04 A/B | Declaration fixtures and a direct projection of typed calls from the trees in COR-09/10 | Completeness from surface source or SPG, handler-aware effect checking, runtime authority, and correspondence for resource operations |

The existing A/D differential implementation uses two evaluation algorithms over the same exploratory contract. It reduces implementation-specific error risk within the bounded fragment, but it is not an independently authored semantics and cannot establish the contract's completeness.

## 5. Gap-ordered extensions

The following work is ordered by dependency. An item should be added to executable models only when its semantics can be stated without relying on an unstated choice.

1. **Carry handler observations into dependency and type summaries.** Use COR-10 to separate a callee's state requirement, the handler that satisfies it, and the writes or failures an observer can still see. Check a shape-preserving handler edit against those summaries.
2. **Define exception and failure classes.** Distinguish domain Result, precondition failure, runtime fault, resource exhaustion, and unsupported construct; specify handlers and propagation through calls and cleanup.
3. **Specify state/ownership alternatives.** Add local mutable store, alias/borrow, move, transfer/return, and branch-join scenarios under separate candidate rules.
4. **Extend AST-path coverage toward source-level conditions.** Scenarios 98–107 check concrete assignments, repeated marker correlation, formula feasibility, generated adapter cross-checks, conservative result handling, one real worker timeout, one mutation-identity counterexample, call-summary transitions, field-sensitive alias sets, and a bounded AST-derived alias summary with join-correlation loss. Next compare additional hard formula families and timing distributions, exercise startup/crash/protocol/resource failures, model alias/call/loop writes, and build independent parser/IR extraction and path-sensitive alias tracking, then bind branch-node coverage before claiming source completeness.
5. **Extend the actor experiments beyond closed scripts.** Add competing receivers and a protocol that can block. Compare cancellation and cleanup across actors using explicit fairness and termination assumptions.
6. **Separate deterministic semantics from environment variation.** Include time, randomness, scheduler, and external response as explicit inputs or controlled nondeterministic observations, then test evidence/cache key implications.

## 6. Reproduction and evidence links

The existing repository command for the RT-04-01 suites is:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v
```

Relevant reports include [RT-03 core semantics](CORE-LANGUAGE-SEMANTICS.md), [RT-04 alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [A/D × A/B cross-profile traces](RT-04-RT-03-CROSS-PROFILE-TRACES.md), and [RT-04 Prototype 01 results](RT-04-PROTOTYPE-01-RESULTS.md).

Before a scenario family is treated as research evidence, the result should identify the exact source revision, command, fixture set, implementation versions, and output. A passing suite verifies only the assertions actually represented by its fixtures.

## 7. COR-09 — Typed calls and private local state

The experiment asks whether B's private scalar mutation changes the observations of a workload that A expresses by passing values forward. Both variants run [the same workload](PROTOTYPES/RT-04-01/test_rt03_typed_calls.py), which conditionally increments an input, increments it once more, calls that calculation twice, and sums the results. Each function receives a fresh lexical environment. Arguments are positional and evaluated left to right. In A, a `let` initializer is evaluated in the surrounding scope and the body uses a new immutable binding. In B, `local` introduces an initialized cell and `set` targets the nearest binding. That binding must be mutable and the assigned value must have its type. Assignment produces Unit. Cell addresses cannot be returned or passed. The scalar result is the external observation. The ordered list of function entries is additional diagnostic evidence about evaluation order.

The [prototype](PROTOTYPES/RT-04-01/rt03_typed_calls.py) uses the same syntax trees for execution and for deriving call sites and their argument types. It visits both conditional branches during static checking. It runs the existing RT-04 checker on the derived declarations before execution. RT-03's A/B distinguishes execution rules, while RT-04's A/B chooses the checker vector. Both RT-04 vectors can check the call declarations for the B workload.

| Comparison | Observed result |
|---|---|
| Immutable value threading vs private mutation over both branch inputs and start values −3 through 3 | All 14 inputs agree on the scalar result and the function entry order, including repeated calls with fresh locals |
| Same two writes in reverse order in B | The result changes from `2` to `1`. The complete RT-04 declaration projection and the invocation list are identical |
| Bool passed to an Int parameter in an unselected branch | Both RT-04 vectors reject the projected call before execution |
| Callee and inner lexical scope shadow a caller's local name | Assignments leave the caller's cell at its original value |

Local execution of the command above reported 126 passing tests with Python 3.12.14, including seven typed call tests, on repository base `72822973f7cc9fd33ede66aad05e844bf25d5bd3` with the COR-09 working tree changes. The experiment uses one implementation of the typed fragment and hand-built syntax trees. Completeness applies to direct syntactic calls in those trees. Recursive calls, shared or escaping references, external effects, and RT-03 D's handler semantics remain outside this comparison.

The observed agreement makes immutable value threading a viable alternative for this private state workload. The write-order counterexample also constrains DEP-004 and DEP-005. Any later SPG, cache key, or equivalence check that relies only on these call/effect summaries would miss a change in behavior. COR-10 extends this comparison to D and varies whether writes and write failures are observable.

Prior art for the experimental rules includes strict application and lexical binding in the [Racket reference](https://docs.racket-lang.org/reference/application.html), [Racket local binding and location rules](https://docs.racket-lang.org/reference/let.html), and the [Rust reference on assignment expressions](https://doc.rust-lang.org/reference/expressions/operator-expr.html#assignment-expressions). The prototype adopts its own scalar and observation boundary.

## 8. COR-10 — What a state handler exposes

The D variant of the COR-09 workload requests reads and writes from a handler. The handler initializes one fresh Int cell per invocation of the handling expression. An initializer runs in the enclosing context. Requests in the body reach the nearest handler, including requests made inside a direct call. For a nested handler, subsequent operations outside its body resume using the outer cell. Requests that need state must be inside a handler or in a function explicitly marked `requires_state`. A call to that function has the same requirement, including in a branch that execution skips.

A total handler can keep writes private or expose an ordered record of the old value, requested value, and acceptance flag. A guarded handler rejects a negative write, retains earlier visible records, and ends execution without evaluating the rest of the body. This choice lets the experiment vary the observation boundary separately from the write policy. Work on algebraic effects describes both state and failure as effects, and *Handlers in Action* gives a state interpretation that logs writes. COR-10 uses fixed built-in handlers that resume a successful request once. [Handling Algebraic Effects](https://lmcs.episciences.org/705) · [Handlers in Action](https://homepages.inf.ed.ac.uk/slindley/papers/handlers.pdf)

| Comparison | Observed result |
|---|---|
| A with immutable bindings, B with private cells, D with a private total handler | All 14 inputs agree on the returned scalar and the diagnostic function entry order |
| Same effectful callee called twice under a private or logging handler | Both return `7` and have identical RT-04 call projections. The logging handler exposes `2→3` and `3→4` |
| Nested handler initialized from the outer handler at state `2` | The inner scope changes its cell to `3`. A later outer read still yields `2`, and the combined result is `5` |
| Same body writes `3`, `-1`, and `9` under total or guarded handler | The total handler returns `9`. The guarded handler records acceptance of `3` and rejection of `-1` when logging is enabled. It reports a terminal failure and never invokes the third write |
| Unhandled state operation, unhandled call in an unselected branch, or an entry with an open state requirement | Each is rejected before execution |

The call projection sent to RT-04 contains the derived signatures, call sites, and graph. The experimental body pass checks the closed state requirement separately. Discharging a state requirement expresses that requests have an interpreter. Even with that requirement discharged, a caller can observe logging or failure. The two logging modes give a concrete case where substituting one handler for another would be unsound if an equivalence check, cache, or evidence key relied only on the unchanged call declarations and returned value. A later effect or dependency model needs to represent which outcomes its observer can distinguish.

The experiment covers direct acyclic calls and scoped integer state with one resumption per successful request. Recoverable exceptions, effect rows, escaping state, user-defined handlers, and concurrency remain open. The full RT-04-01 suite reported 131 passing tests with Python 3.12.14 on repository base `72822973f7cc9fd33ede66aad05e844bf25d5bd3` with the COR-09/10 working tree changes. The five dedicated COR-10 tests cover cross-call observation, nesting, unhandled requests, terminal rejection, and type boundaries. The shared workload comparison is in the COR-09 test. [Prototype](PROTOTYPES/RT-04-01/rt03_typed_calls.py) · [Fixtures](PROTOTYPES/RT-04-01/test_rt03_typed_calls.py)

## 9. COR-11 — Actor traces and failure policies

The Profile C comparison uses independent scripts that send scalar messages to one receiving actor. Only the receiver owns the accumulator. To represent the COR-09/10 workload, each of two senders contributes the starting value, one optional increment, and one unconditional increment as distinct messages. All four profiles are compared on the final scalar. The actor model also exposes deliveries and failures in order, including the receiver's value after each delivery. The function entry diagnostic from A/B/D has no actor equivalent in this experiment.

The model separates sending from delivery. In the **channel FIFO** variant, the next sent but unprocessed message on any channel can be delivered. Processing that message is an atomic receiver turn. Sends on the same channel remain ordered. When **sorted batch** is selected, the receiver waits for the closed group to finish its scripts or fail, then processes the pending channels in a fixed order and messages in sender order. This requires knowing when the group is closed and buffering its messages. The model compares ordering by sender spelling with an explicit protocol order.

A producer can fail after its last send. **Isolate** records the failure and leaves the already-sent work and other senders active. **Abort** makes group failure terminal immediately and leaves the prior delivery events visible. Under sorted batch, a failure under the abort policy therefore occurs before the first delivery. Erlang provides a prior example of per-sender signal ordering with unspecified inter-sender ordering and separate failure signals. The closed batch and abort rules here are specific to the research model. [Erlang process reference](https://www.erlang.org/doc/system/ref_man_processes.html) · [Erlang/OTP notes on message passing](https://www.erlang.org/blog/message-passing/)

| Comparison | Observed result |
|---|---|
| A/B/C/D on both branch inputs and starts from −3 through 3 | All 14 inputs agree on the final scalar for every enumerated C schedule |
| Two senders, each with two or three messages, with no failures | Channel FIFO gives 6 or 20 exact traces per input. The independent shuffle oracle confirms the entire sets. Sorted batch gives one trace per input |
| One sender sets `1` and adds `1`, while another sets `9` | Channel FIFO gives final values `2`, `9`, or `10`. Sorting by spelling gives `9` when the first sender sorts first and `2` when it sorts last. An explicit order keeps `9` when the sender and its reference in that order are renamed together |
| Two senders each send once, then one fails | With FIFO, isolation returns `3` with 6 possible traces. Group abort produces 5 distinct prefixes and no returned value. Sorted batch produces a single trace for each failure policy |

Commuting increments make the result independent of schedule even when the delivery log is visible and varies. For noncommuting messages, an explicit protocol order preserves the scalar through the tested rename. That equivalence treats sender labels consistently under renaming. The labels in the raw trace still change. If names are meant to support behavior-preserving rename, using their spellings as order keys would violate that guarantee even at the scalar boundary.

Each explored state advances on a send, delivery, or failure. For a script group with `m` messages and `f` failure steps, a schedule has at most `2m + f` steps. Histories may share a search state only when the sender and receiver positions, current value, terminal flag, and full visible prefix agree. Those fields determine the same enabled steps and future observations. The explorer emits one schedule per distinct terminal observation. An independent shuffle or prefix oracle checks the expected sets for the small cases, and replay checks the emitted witnesses. These bounds apply to closed reliable scripts with one receiver. They provide no fairness or liveness result for a system with blocking receives, selective matching, message loss, restart, or unbounded actors. The suite reported 136 passing tests with Python 3.12.14 on repository base `72822973f7cc9fd33ede66aad05e844bf25d5bd3` with the COR-09–11 working tree changes. [Actor model](PROTOTYPES/RT-04-01/rt03_actor_model.py) · [Actor cases](PROTOTYPES/RT-04-01/test_rt03_actor_model.py) · [Four-profile comparison](PROTOTYPES/RT-04-01/test_rt03_typed_calls.py)

### COR-12 — Blocking protocol progress

To isolate blocking from the existing buffered actor model, a second finite model gives each of two actors exactly one send and one receive, in a fixed order. Under **buffered** semantics, send enqueues and advances. Under **rendezvous** semantics, send advances both actors atomically only when the peer is already at receive. The model enumerates all enabled schedules and records each complete or blocked trace; every returned witness is replayable. The rendezvous rule is one candidate contract and should not be generalized to all actor systems.

| Protocol | Buffered | Rendezvous |
|---|---|---|
| Both actors send then receive | All four schedules complete | One terminal blocked state; neither send is enabled |
| A sends then receives; B receives then sends | All schedules complete | One two-step handshake completes |

The paired cases show a semantic interaction between message capacity and protocol order: buffering permits mutual sends to proceed, while rendezvous requires a receiving peer; a crossed request/reply protocol satisfies that requirement. The bounded model has no cancellation, failure, timeouts, message loss, selective receive, repeated operations, or fairness policy. It proves only that a finite protocol graph has these outcomes under the encoded rules; it does not show source-program correspondence or runtime scheduling behavior. The focused prototype and tests are in [blocking protocol model](PROTOTYPES/RT-04-01/rt03_blocking_protocol.py) and [cases](PROTOTYPES/RT-04-01/test_rt03_blocking_protocol.py). The focused test run passed 3 tests; the existing COR-11 actor-model tests passed 5.
