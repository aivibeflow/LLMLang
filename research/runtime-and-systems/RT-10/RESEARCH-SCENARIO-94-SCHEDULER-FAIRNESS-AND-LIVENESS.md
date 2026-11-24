# Scenario 94 — Scheduler Fairness and Liveness

**Status:** Prior-art comparison and experiment design; no LLMLang policy selected
**Updated:** 2026-11-19

**Executable follow-up:** [Scenario 112](RESEARCH-SCENARIO-112-WEAK-STRONG-AND-BOUNDED-FAIRNESS.md) checks continuous versus intermittent enablement with explicit starvation cycles and a fixed two-task round-robin bound. It does not validate a real runtime or prove general liveness.
**Scope:** Separate scheduler progress guarantees from structured task lifetime, actor protocol progress, resource fairness, and deterministic replay.

## 1. Research question

What, if anything, should LLMLang promise about a runnable task eventually receiving execution, and what assumptions make that promise true? A fairness statement is meaningful only after defining the scheduler's eligible entities, what counts as a scheduling step, and environmental assumptions. It must not silently imply that an awaited I/O operation completes, a lock becomes available, or a protocol reaches a terminal state.

This study is analytical. The references describe different layers: a language/runtime FAQ, runtime documentation, an async programming model, and structured task-group lifetime. They are not directly comparable as a single language-level guarantee. Versioned documents should be rechecked before a normative decision.

## 2. Distinctions and vocabulary

- **Runnable-task fairness:** among continuously runnable tasks, no eligible task is postponed forever. This is weaker than a numerical bound.
- **Bounded scheduling fairness:** under stated assumptions, a continuously runnable task is polled within a finite bound (often expressed as a maximum number of scheduling opportunities or polls).
- **Weak fairness:** a transition that remains continuously enabled eventually occurs.
- **Strong fairness:** a transition enabled infinitely often, but not continuously, eventually occurs. This is a stronger and more expensive model-checking assumption.
- **Protocol liveness:** an operation such as receive, send, or request eventually completes. It depends on peers and environment in addition to scheduling.
- **Resource fairness:** waiters for a lock, permit, channel slot, or I/O service eventually acquire/service it. Scheduler fairness alone does not imply this.
- **Termination:** a task reaches a terminal state. Neither fairness nor structured scope lifetime proves termination if the task can diverge or wait forever.

Every claim should state the quantification domain (tasks, actors, executors, workers), enabledness assumptions, task cooperation/preemption assumptions, and whether the bound is normative, implementation-specific, or merely observed.

## 3. Prior-art comparison

| System/source | What it supports | Explicit limits / relevance |
|---|---|---|
| Go runtime FAQ, [Goroutines](https://go.dev/doc/faq#goroutines) | Describes runtime management of goroutines and preemption as an implementation technique that helps a goroutine make progress when another runs for a long time. | FAQ/runtime behavior is not a portable source-level bound on when a goroutine runs. Go's specification does not define a general per-goroutine fairness bound. Do not promote practical scheduler behavior to language semantics. |
| Tokio runtime docs, [Runtime](https://docs.rs/tokio/latest/tokio/runtime/) | Documents a conditional fairness guarantee: if the number of tasks does not grow without bound and each task poll returns within a bounded time, Tokio promises a task will be scheduled within some bounded delay. The docs also state assumptions for I/O/timer wakeups. | Runtime-specific guarantee with premises; it does not force a poll to return, guarantee completion of an awaited external operation, or establish fairness for locks/channels. A bounded delay is not necessarily a stable fixed constant. |
| Erlang/OTP reference, [Processes](https://www.erlang.org/doc/system/ref_man_processes.html) | Scheduler reductions provide preemption opportunities. The reference documents priority classes and warns that continuously runnable higher-priority processes can starve lower-priority work; process scheduling policy may vary with releases. | This is a VM scheduling contract/description, not a universal FIFO guarantee. Preemption bounds uninterrupted execution but does not by itself ensure every process progresses when priority rules permit starvation. |
| Rust async book, [Concurrency with async](https://doc.rust-lang.org/book/ch17-02-concurrency-with-async.html) | Async functions produce futures; an executor decides when to poll them. Progress depends on polling and suspension/yield behavior. | Rust's async language/library model does not prescribe one executor or global fairness. A future that is never polled or a poll that does not return can prevent progress. Runtime choice is material. |
| Swift structured concurrency, [TaskGroup](https://docs.swift.org/latest/documentation/swift/taskgroup/) | A task-group scope waits for child tasks to finish; cancellation is cooperative. This gives a lifetime/join property for scope exit. | Scope joining does not promise a scheduler order, fairness bound, or child termination. A nonterminating child can keep the group scope from completing. |

These sources illustrate at least four axes that should not be collapsed: preemption, polling fairness, priority starvation, and structured joining. Exact APIs and guarantees are release-sensitive; pin source versions in any conformance document.

## 4. Candidate LLMLang contract profiles

These are research alternatives, not recommendations:

1. **L0 — No language-level scheduler fairness.** Specify only task state transitions and leave scheduling to runtime/executor. Runtime documentation may add stronger guarantees.
2. **L1 — Weak fairness for continuously runnable tasks.** Under a finite set of live tasks and a scheduler that continues making steps, each continuously enabled runnable task eventually runs. No numeric bound and no guarantee for intermittent enablement.
3. **L2 — Strong fairness.** Tasks enabled infinitely often eventually run. This can rule out starvation in alternating-enable models but imposes stronger scheduler/model-checking requirements.
4. **L3 — Bounded fairness under explicit premises.** A runnable task is scheduled within a bound when task count is bounded, each poll/step returns within a bound, and the runtime remains operational. State whether the bound is abstract/existential or an observable numeric limit.
5. **Layered contract.** Language defines task and cancellation semantics; a named executor profile may define fairness/preemption bounds; synchronization primitives independently define waiter guarantees.

Potential scope choices include cooperative tasks (only at suspension points), preemptive tasks, and actor receive loops. A guarantee for one scope must not be presented as a guarantee for all.

## 5. Discriminating bounded experiment

Construct a finite transition system with two tasks and one capacity-one resource:

- `A` is continuously runnable and repeatedly executes a bounded step.
- `B` alternates between runnable and waiting on a permit; a third modeled event releases the permit infinitely often.
- Add variants where `A` performs an unbounded poll, where task creation grows without bound, where `B` is continuously runnable, and where `B` has lower priority.
- Record task selection, poll entry/return, permit release/acquire, cancellation request/observation, and terminal states as separate events.

For each candidate profile, enumerate finite prefixes and search for a cycle that starves `B`. Under weak fairness, reject only cycles where `B` remains continuously enabled forever; under strong fairness, reject starvation when `B` is enabled infinitely often. Under bounded fairness, assert a bound only when all declared premises hold. A finite search can find counterexamples to a claimed bound but cannot prove unbounded liveness without an appropriate induction/model-checking argument.

Run a runtime harness separately from the abstract model: pin compiler/runtime/OS/CPU, use a fixed task set and bounded polls, collect latency distributions and worst observed delay, and repeat under CPU load and task churn. Measurement supports engineering characterization; it does not replace a normative guarantee or prove an upper bound.

## 6. Implications for LLMLang semantics and evidence

- Scenario 57 establishes task-tree lifetime/join questions; Scenario 58 covers async function creation, polling/start, and scheduling. Neither implies starvation freedom. Keep these concerns linked but separately specified.
- Extend COR-11/COR-12 with competing receivers, blocked send/receive, cancellation, and explicit fairness assumptions. State which schedules are admissible before enumerating traces.
- A trace witness proves one allowed execution, not eventual progress. For deterministic evidence, distinguish all-schedule safety, fairness-filtered liveness, and runtime measurements.
- Define progress assumptions for model checking, deadlock detection, and any claim that a protocol eventually completes. Do not infer I/O completion, lock acquisition, or task termination from scheduler fairness.
- If runtime or executor profile changes can alter allowed traces or liveness, include that profile/version and relevant scheduling parameters in semantic/evidence inputs. If fairness is deliberately unspecified, cache keys need not include an unobservable scheduler algorithm, but tests must avoid asserting an unsupported schedule.
- Cancellation remains a request unless the contract separately proves a task observes it, exits, and finishes cleanup; see Scenario 40.

## 7. Open questions and falsifiers

1. Is LLMLang intended to make portable liveness claims, or only provide a runtime-specific executor contract?
2. Are cooperative suspension points sufficient, or do CPU-bound tasks require preemption for the desired workload/security model?
3. Should the language guarantee only weak fairness, or is strong fairness needed for recurring readiness events?
4. Which synchronization primitives, if any, promise FIFO or starvation-free waiter service independently of the scheduler?
5. Can a useful finite scheduling bound be stated without making ordinary task-count growth or blocking polls invalidate it?
6. How should priorities interact with liveness claims?

Falsify any proposed fairness profile with (a) a starvation cycle satisfying its stated premises, (b) a counterexample caused by an omitted environment assumption, or (c) a conforming implementation that violates the claimed observation. No profile is selected here.

## 8. Sources

- Go FAQ, “What happens to goroutines that are blocked?” and scheduler description: https://go.dev/doc/faq#goroutines
- Tokio runtime documentation, fairness and scheduling: https://docs.rs/tokio/latest/tokio/runtime/
- Erlang/OTP Reference Manual, Processes and scheduling: https://www.erlang.org/doc/system/ref_man_processes.html
- The Rust Programming Language, “Concurrency with async”: https://doc.rust-lang.org/book/ch17-02-concurrency-with-async.html
- Swift documentation, TaskGroup: https://docs.swift.org/latest/documentation/swift/taskgroup/
- LLMLang [Scenario 57](RESEARCH-SCENARIO-57-STRUCTURED-CONCURRENCY-AND-TASK-LIFETIMES.md), [Scenario 58](RESEARCH-SCENARIO-58-ASYNC-FUNCTION-TYPES-AND-SCHEDULING.md), [Scenario 40](../../language-design/RT-04/RESEARCH-SCENARIO-40-ASYNC-CANCELLATION-AND-CLEANUP.md), and [shared semantics corpus](../../language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md).
