# RT-14 context candidate records and concurrent ownership

The research separates a read-only Knowledge Context manifest, a versioned Task Context and current authorization. Each record is inspectable and has its own identity and scope. The candidate below composes the bounded results without selecting a syntax or production architecture.

## Records and alternatives

| Record | Candidate fields |
| --- | --- |
| Knowledge Context manifest | Snapshot, purpose, exact authorized sources and approved projections, budget policy, omissions and completeness evidence |
| Task Context | Stable task ID, requirement revision, objective and scope, dependencies, typed deliverables, acceptance criteria and exact references to authoritative inputs |
| Execution attempt | Exact task revision and epoch, owner, delegated scopes, prerequisite and outcome records |
| Completion receipt | Exact subject, checked obligation digests, and outcome under one policy |
| External action grant | Principal, repository, operation, exact target, expiry or policy epoch and replay control |

A phase-only lifecycle admits stale retries. A revision- and attempt-bound lifecycle separates refinement from re-execution. Concurrent work can use disjoint delegated scopes under a parent or a single active lease for an overlapping mutable scope. A settled sibling does not prove parent coverage. Task completion and commit or push permission remain separate. [Task phase comparison](RT-14-TASK-LIFECYCLE-BOUNDARY-2026-11-25.md) · [Pinned producer references](RT-14-TASK-PINNED-REFERENCES-2026-11-25.md)

## Invariants and distinguishing tests

| Invariant | Fixture and expected falsifier |
| --- | --- |
| At most one owner for an overlapping mutable scope | Race two delegates in SQLite. Admitting both would falsify ownership isolation. |
| A task can settle only against its exact current prerequisites | Change the parent or child revision, owner or epoch. A stale result settling the new task would falsify the gate. |
| Exact retries preserve one durable outcome | Interrupt before receipt and reopen the transaction. A duplicate outcome or reused key with different work would falsify idempotency. |
| The parent retains incomplete scope | Settle siblings that cover only part of the parent or cancel before child settlement. Completion despite incomplete scope would falsify the gate. |
| A completion cannot grant an external action | Try a current completion with unrelated operation authority. Commit approval admitting push would falsify separation. |

The checker validates three exact archived ledgers. Sixteen native delegation races distinguish overlapping and disjoint scopes. Both cancellation orders produce different valid terminal histories. Across the 27 settlement schedules, phase-only and task-only comparators admit six and three stale transitions, while exact prerequisite checks admit none. Interrupted retry leaves one final receipt. Of 120 action and approval profiles, only the separately authorized commit and push pass. [Sibling ownership](RT-14-TASK-SIBLINGS-2026-11-25.md) · [SQLite settlement](RT-14-TASK-CONTEXT-SQLITE-2026-11-25.md) · [Commit and push authority](RT-14-TASK-AUTHORITY-2026-11-25.md)

A bounded next prototype can connect immutable RT-05/06 identity and dependency evidence, RT-02 requirements, RT-16 grants, RT-19 workspaces and RT-20 plans. Replay the existing receipts against those producers, then inject partial availability, stale concurrent deliveries and cancellation. Retain representative controlled participant results under a separate gate. The plan leaves production integration, lifecycle ownership policy and normative decisions open.

## Reproduce

CPython 3.12.14 and Python hash seeds 37 and 71 produce evidence SHA-256 `a5deec2fc2630cdd94b0812a40a2ff6729708a30734e6acbb06db6eeb76c84d1`. [Evidence ledger](CONTEXT-CANDIDATE-COVERAGE-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/toolchain-and-collaboration/RT-14/CONTEXT-CANDIDATE-COVERAGE-01/check.py > /tmp/rt14-context-candidate.json
```
