# RT-10 — Scope exit, nested cleanup, and failure publication

**Date** · 2026-11-21  
**Baseline** · `017e64b87c87371309197a392165258b8b088dd1`  
**Status** · Finite schedule experiment for [Plan §5.2](../../PLAN.md#52-execution-semantics-and-runtime-architecture)

## Question and assumptions

When can a parent publish a terminal result and release its borrowed state after requesting cancellation? [Scenario 57](RESEARCH-SCENARIO-57-STRUCTURED-CONCURRENCY-AND-TASK-LIFETIMES.md) proposes comparing nested task lifetimes. [Scenario 129](RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md) tests evidence for a single provider invocation. This experiment targets closure across an entire nested scope and which failures are visible at publication.

The parent has two children and one of them owns a nested grandchild. The sibling and grandchild each borrow from the parent. The sibling body fails. Grandchild cleanup reports a separate error, then returns its borrow under the fixture contract. A child's completion waits for its nested scope. A cancellation request and a poll of parent readiness are separate events. The fixture has no early transfer of ownership, forced termination, or scheduler progress guarantee. [Swift structured concurrency proposal](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0304-structured-concurrency.md#task-groups) · [Rust scoped threads](https://doc.rust-lang.org/std/thread/fn.scope.html)

## Compared policies

| Policy | Evidence available at publication |
|---|---|
| Publish after the exit request | High apparent responsiveness. A request is evidence about intent and can leave borrowers and pending errors. Returning a pending handle with retained ownership would be a different interface. |
| Publish after direct child bodies settle | Waits for direct returns. A body report can precede descendant joins or cleanup, so it does not establish final outcomes or loan release. |
| Publish after transitive join | Waits for body settlement, nested joins, and all tracked cleanup. Can delay completion indefinitely if any required task is uncooperative. |
| Allow explicit supervised detach | Offers a separate route for legitimately long-lived work. It needs no outstanding borrow from the exiting scope, an alternate supervisor, accounting transfer, and a failure sink. The current fixture intentionally has live borrows and does not implement detach. |

## Results

The runner enumerates all 1,260 orderings of seven distinct events with the two body-before-cleanup constraints. An independent predicate examines the prefix before the poll. It allows publication exactly when an exit request, the direct child body, and both required cleanups are present. When published, it compares the expected loans and failure order with the state-machine observation.

| Policy | Published at scheduled poll | Outstanding loan at publication | Missing failure at publication | Oracle disagreements |
|---|---:|---:|---:|---:|
| After request | 630 | 420 | 336 | 450 |
| After direct bodies | 378 | 198 | 138 | 198 |
| After transitive join | 180 | 0 | 0 | 0 |

The direct-body witness returns while the grandchild still has a borrow. The transitive join remains pending and the later poll reports both failures after cleanup. With transitive join, a final poll after all events sees the same declared task-order failures in every schedule, including schedules in which the failures arrived in the opposite order. Removing the grandchild's body and cleanup leaves transitive join pending across repeated polls. The result supports a distinction between requesting cancellation, reaching quiescence, and deciding how errors should be ordered.

The evidence supports using transitive join as a candidate for borrowed captures. Explicit detachment and a finite completion deadline need further rules. This fixed tree does not model dynamic spawn, retained resources after failed cleanup, selective cancellation delivery, async wakeup races, or resource budgets. RT-03 defines outcome order, RT-04 owns borrow and cleanup disposition, and RT-10 needs to implement and publish the checked lifetime state. [Dependency map](../RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

Run from the root with CPython 3.12.14. The runner prints the table counts and asserts the transitive-join, unsafe-publication and uncooperative-task witnesses. [Executable model](../PROTOTYPES/STRUCTURED-SCOPE-01/scope_join.py)

```sh
python -B research/PROTOTYPES/STRUCTURED-SCOPE-01/scope_join.py
```
