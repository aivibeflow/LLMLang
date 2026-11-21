# RT-26 — Hierarchical Resource Accounting, Limits, Throttlers, and Handlers

**Status:** Partially validated in two cooperative cumulative-budget models (reservation and cancellation settlement); mandatory resource dimensions and real-time enforcement remain open. See [cooperative reservation](RT-26-COOPERATIVE-BUDGET-RESERVATION.md) and [cancellation settlement](RT-26-CANCELLATION-ACCOUNTING.md).  
**Research area:** RT-26  
**Priority:** P1  
**Scope:** LLMLang language semantics, runtime, task/coroutine model, native targets, and Toolchain Server workloads  
**Decision boundary:** this research evaluates language-level abstractions and enforcement architecture. It does not preselect syntax, promise exact attribution for every metric, or assume that every target can enforce every limit.

## 1. Motivation and goal

Production systems often need to account for and constrain the resources consumed by an individual task or an entire hierarchy of tasks. When a limit is reached, the system needs a defined policy/handler that decides what happens next rather than relying on ad hoc process-wide monitoring.

Determine how LLMLang can make resource accounting, budgets, limits, throttling, and limit-exceeded handling first-class high-level language capabilities while retaining precise semantics, safe task isolation, measurable overhead, and explicit portability guarantees.

The research must cover both:
1. **Accounting/observation:** what resources a task and its descendants consume, how consumption is attributed, and how measurements are exposed.
2. **Enforcement/control:** how limits are declared, checked, enforced in real time, and handled when crossed.

## 2. Resource dimensions

At minimum investigate the following dimensions independently. Define units, measurement source, attribution model, resolution, accuracy, overhead, and platform availability for each.

- **Memory:** current/peak live or resident memory, allocated bytes, retained/committed memory, allocation volume, and optionally per-task allocation attribution. Distinguish logical live bytes from RSS and allocator-retained memory.
- **CPU:** CPU time consumed, execution time versus wall-clock time, per-core or aggregate use, and CPU-rate/concurrency controls.
- **Disk I/O:** bytes and operations read/written, throughput, IOPS, latency where available, and attribution to tasks and descendants.
- **Network I/O:** bytes/packets sent and received, operation counts, bandwidth/rate, and attribution across sockets, connections, and delegated tasks.
- **Coroutine/task switches:** task or coroutine creation, suspension, resumption, yield, scheduler handoff, and context-switch counts. Define exactly which events are counted and distinguish language-level coroutine switches from OS thread/context switches.
- **Performance counters:** hardware PMU and software performance events such as instructions, cycles, cache misses, branch misses, page faults, and context switches, subject to hardware, kernel, permissions, virtualization, and sampling constraints.

Also identify additional resource dimensions that materially matter to production LLMLang workloads, but do not expand the mandatory core without evidence.

## 3. Task hierarchy and accounting model

Research the task as the primary accounting scope and define how accounting composes across nested/delegated work:

- Task identity, lifetime, parent/child relationships, structured-concurrency scopes, detached work, and task migration between worker threads.
- Whether child consumption is charged to both child and ancestors, only to the nearest budget owner, or through a configurable aggregation model. Prevent accidental double counting in reported totals.
- Budget inheritance, explicit overrides, delegation, transfer, shared budgets, and multiple concurrent parents/owners.
- Attribution for work performed by runtime services, native libraries, blocking I/O, kernel workers, callbacks, and external processes on behalf of a task.
- Accounting of resources that outlive the initiating task, including background operations, retained memory, open files/sockets, and cleanup.
- Behavior when attribution is unknown or incomplete. The system must expose uncertainty rather than silently claim exact accounting.
- Interaction with cancellation, cleanup, retries, task supervision, and resource ownership.

Compare per-task, task-group, request/session, process, and container scopes. Determine which scopes are semantic language entities and which are runtime/deployment scopes.

## 4. Limits, budgets, quotas, and throttlers

Define and distinguish:

- **Budgets/quotas:** cumulative consumption over a task lifetime or a defined period/window.
- **Instantaneous limits:** maximum concurrent memory, open resources, or other live quantities.
- **Rate limits:** CPU, disk/network throughput, allocation rate, or event rate over a window.
- **Concurrency limits:** maximum active child tasks, operations, connections, or in-flight requests.
- **Deadlines/timeouts:** wall-clock bounds versus CPU-time budgets; clarify overlap with existing time/deadline semantics.
- **Soft and hard limits:** warning/early notification versus mandatory enforcement.
- **Hierarchical limits:** parent budgets shared by descendants, child sub-budgets, reservation/commit semantics, and sibling contention.
- **Throttlers:** cooperative yield/delay, token/leaky bucket, scheduler-level throttling, I/O shaping, admission control, and target-specific OS controls.

For every mechanism specify the unit, scope, window, reset/refill behavior, burst allowance, accounting precision, overshoot bound, and failure mode. Analyze races and concurrency: multiple children may cross a shared limit simultaneously, and checks performed only at safe points can overshoot.

## 5. Limit-exceeded handlers and policy decisions

Research a first-class handler/policy mechanism invoked when a budget or limit is approached or exceeded. Do not assume one universal default action. Compare actions including:

- Continue with an observable warning or explicit authorization.
- Throttle or delay the task/selected descendants.
- Pause/suspend work pending a policy decision.
- Cancel the task, a subtree, or the whole request.
- Retry with a smaller budget, different strategy, or later admission.
- Degrade quality or switch to a cheaper/less resource-intensive implementation.
- Shed optional work or reject new child tasks.
- Spill state to disk or release caches/resources.
- Escalate to a parent/supervisor or external policy service.
- Terminate an isolated process/container when cooperative enforcement cannot be trusted.

Define handler inputs as typed evidence: resource kind, configured limit, observed value, measurement source/precision, scope, task identity, ancestry, timestamp/deadline, and whether the limit is soft/hard. Define handler outcomes, authorization, reentrancy, idempotency, deadlines, handler resource budgets, and behavior if the handler itself fails, blocks, recursively exceeds a limit, or is unavailable.

A handler must not be able to bypass a hard isolation boundary merely by returning a permissive action. Identify which actions are policy decisions and which are non-overridable runtime/OS safety constraints.

## 6. High-level language integration

Evaluate how resource control should appear as a high-level language capability, rather than only as external process configuration or low-level system calls.

Investigate:

- Resource scopes/regions associated with task creation and structured concurrency.
- Typed resource kinds, units, budgets, limits, and observed usage values.
- Declarative task contracts/annotations versus explicit scoped APIs and effect/capability requirements.
- Parent-to-child budget inheritance and explicit budget delegation.
- Typed limit-exceeded events and handlers integrated with existing error/effect/handler semantics.
- Whether resource accounting is observable program state, an effect, a capability, or a combination; what is deterministic and what is environment-dependent.
- Static checking opportunities (e.g. required budget declarations, forbidden unbounded operations) versus inherently dynamic enforcement.
- How libraries declare resource behavior/requirements and how callers can supply or constrain budgets.
- Whether a program can request a budget, while a host/supervisor retains authority to grant a lower ceiling.
- Syntax/API ergonomics for nested task hierarchies, without committing to a concrete syntax before semantic alternatives are compared.

Provide end-to-end source examples for nested tasks, delegated budgets, soft/hard limits, throttling, and limit-exceeded handlers. Compare candidate designs with equivalent Rust, Go, Java, Swift, Erlang/BEAM, and relevant workflow/runtime systems.

## 7. Enforcement architecture and platform boundary

Compare enforcement layers and their guarantees:

- Language/runtime cooperative checks at allocation, scheduling, I/O, task switching, and other safe points.
- Runtime scheduler integration and per-task accounting.
- Allocator instrumentation and memory accounting, including interaction with RT-25.
- OS facilities such as cgroups, rlimits, process accounting, I/O controllers, and performance-event interfaces where applicable.
- Container/orchestrator controls and external supervisors.
- Sandboxing and process isolation for workloads that cannot be safely interrupted or attributed in-process.

For each resource, classify guarantees as exact, bounded-overshoot, sampled/approximate, best-effort, or unavailable. Define maximum detection/enforcement latency where measurable. Explain how enforcement behaves for blocking syscalls, uninterruptible kernel work, native/FFI code, shared resources, and work delegated outside the process.

Do not claim that a language-level per-coroutine limit can be enforced by an OS mechanism that only sees a process/container. If fine-grained attribution is unavailable, specify the fallback scope and disclose the loss of precision.

## 8. Required experiments and benchmarks

A bounded model compares split check-and-charge with serialized ancestor reservation, including duplicate attempts and cancellation after settlement. [Cooperative budget reservation](RT-26-COOPERATIVE-BUDGET-RESERVATION.md)

Build a reproducible comparison using representative LLMLang workloads and task trees. Include nested tasks, sibling contention, high fan-out, task migration, blocking I/O, native/FFI work, cancellation, cleanup, and detached/background operations.

Measure:

- Accounting accuracy against an independent ground truth or controlled workload.
- Attribution completeness and uncertainty for every metric.
- Enforcement detection latency and overshoot beyond limits.
- Throttling accuracy, fairness, starvation, and recovery after refill/release.
- Runtime overhead for accounting enabled/disabled and for different sampling/check frequencies.
- Memory/CPU overhead of the monitoring and handler mechanisms themselves.
- Scalability with task count, hierarchy depth, event rate, and number of active budgets.
- Portability and permission failures across supported targets and deployment environments.
- Handler latency, failure behavior, and effect on the resource budget it supervises.

Publish exact environment, kernel/runtime/toolchain versions, permissions, fixtures, commands, raw machine-readable results, and analysis scripts. Include adversarial tests that attempt to evade accounting through child tasks, native calls, shared handles, background work, and rapid concurrent limit crossings.

[The cancellation accounting fixture](RT-26-CANCELLATION-ACCOUNTING.md) compares task closure and refund rules across bounded event schedules. It shows overshoot if acknowledgment frees a live reservation.

## 9. Correctness, safety, and security gates

- No task may gain more authority or budget than its parent/supervisor explicitly delegates.
- Shared hierarchical budgets must remain correct under concurrent consumption and cancellation.
- Resource ownership and cleanup must remain correct when limits trigger cancellation or termination.
- Hard limits must have a documented enforcement boundary and bounded or explicitly unbounded overshoot.
- Unknown/inaccurate measurements must not be presented as exact.
- Handler execution must itself be bounded, authorized, observable, and protected from recursive failure.
- A task must not escape a hard process/container isolation limit by spawning or delegating work outside the accounted scope.
- Unsupported metrics/controls must fail explicitly or degrade to a documented weaker scope; no silent no-op for a requested hard limit.
- Resource policy must not alter unrelated language semantics except through documented effects, errors, and observations.

## 10. Required outputs

1. A resource-metric catalogue with units, sources, attribution, precision, overhead, and platform coverage.
2. A formal task-hierarchy and accounting model, including aggregation and budget delegation rules.
3. A taxonomy and semantics for budgets, quotas, instantaneous limits, rates, concurrency limits, deadlines, and throttlers.
4. A typed limit-exceeded event/handler model, including failure and authorization behavior.
5. A language-level design comparison with source examples; no syntax is selected without semantic analysis.
6. An enforcement matrix mapping each metric/limit to runtime and OS/container mechanisms and its guarantee class.
7. Reproducible experiments, benchmark harness, raw results, and correctness/security tests.
8. A recommendation separating portable language guarantees from target-specific capabilities and deployment policy.
9. A list of unsupported or approximate cases and a safe fallback/rollback strategy.

## 11. Exit criteria

RT-26 is complete only when:

- The accounting scope and hierarchy semantics are explicit and validated under concurrent nested/delegated tasks.
- Every mandatory resource metric has a documented source, unit, attribution model, precision, and platform limitation.
- Limits and throttlers have defined windows, enforcement points, overshoot bounds, and failure behavior.
- Limit-exceeded handlers have typed inputs/outcomes, bounded execution, authorization rules, and failure semantics.
- At least one end-to-end language-level prototype demonstrates nested task budgets and a handler-driven response to a limit.
- Representative experiments quantify accuracy, enforcement latency, overhead, fairness, and portability.
- The final recommendation distinguishes guaranteed language semantics from best-effort runtime and OS facilities.

Until these criteria are met, resource accounting and enforcement remain research topics; no syntax or universal enforcement guarantee is accepted.
