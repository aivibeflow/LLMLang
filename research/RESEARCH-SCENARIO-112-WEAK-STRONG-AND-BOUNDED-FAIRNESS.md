# Research Scenario 112 — Weak, Strong, and Bounded Fairness

**Status:** Finite abstract cycle comparison; no LLMLang scheduler guarantee selected
**Research area:** RT-03 concurrency semantics, RT-04 scheduler/runtime contracts, RT-08 liveness evidence
**Updated:** 2026-11-20

## Question

Which starvation traces are excluded by weak fairness, strong fairness, and a bounded two-task scheduler? In particular, can a task be enabled infinitely often yet starved without violating weak fairness?

## Model

`PROTOTYPES/RT-04-01/scheduler_fairness_model.py` models task A as always runnable and task B either continuously runnable or intermittently enabled by an abstract environment. It replays cycles and checks two fairness predicates for a starving B:

- A cycle is weak-fair for B if B is not enabled in every state of the repeated cycle. A continuously enabled task cannot be starved on such a cycle.
- A cycle is strong-fair for B if B is never enabled on the cycle. Thus starvation is excluded when B is enabled in even one cycle state and that cycle repeats infinitely.
- A separate two-task round-robin function checks a bounded premise: if both tasks remain runnable and each selection returns, B is selected at turn 0 or 1, depending on the starting cursor.

Five focused tests replay the cycle witnesses, check fairness classification, enforce the two-task bound, and reject illegal/non-cyclic sequences.

## Results

| Repeating trace | B enabled? | Weak fairness permits starvation? | Strong fairness permits starvation? |
|---|---|---:|---:|
| `B enabled; A runs` | Continuously enabled in a self-cycle | No | No |
| `environment enables B; A runs; environment disables B` | Infinitely often, but not continuously | Yes | No |

The second trace is the discriminator: weak fairness does not imply strong fairness. Bounded round-robin scheduling gives a numeric selection bound only under its stated fixed-task, always-runnable, returning-step assumptions; it says nothing about tasks that are intermittently enabled or blocked on external resources.

These checks classify explicit finite cycles and a fixed two-task policy. They do not prove general liveness, model executor crashes or unbounded task creation, or show that real runtime polls return. The model does not imply I/O completion, lock fairness, protocol progress, or task termination.

## Implications and next discriminators

Scenario 94's prior-art comparison remains broader. The executable witness shows why a spec must say whether enabledness is continuous or intermittent and what the scheduler step represents. Next extend the transition system with priorities, external wakeups, task creation, cancellation, and resource waiters; check fairness assumptions with SCC-based liveness analysis and compare a pinned runtime harness. Keep observed latency distinct from a normative bound.

## Reproduction

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_scheduler_fairness_model.py' -v
```
