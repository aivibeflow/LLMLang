# Research Preparation — RT-04 Provider Reconciliation and Guard Coverage

**Status:** Prepared; not executed.  
**Priority:** P0 — follow-up to the COR-13 shared workload.  
**Related open questions:** LL-008, LL-017, LL-024; RT-04, RT-10 and RT-16 gates.

## 1. Study objective

Test whether the invocation-scoped resource state and completion evidence remain sound when an operation crosses independent providers, concurrent observers, process interruption, snapshot restoration, alias escape, callback reentry and effects outside a wrapper's local view.

Current SQLite probes establish specific local facts. They do not establish a general cross-provider transaction, complete foreign footprint, authenticated completion source, or concurrency policy.

## 2. Required baseline

Read:
- [Scenarios 120–130](../language-design/RT-04/RESEARCH-SCENARIO-120-SQLITE-CLEANUP-DEPENDENCIES.md) for native cleanup, guards, reentry, multi-resource reservations, cancellation and durable invocation evidence.
- [Scenarios 131–133](../language-design/RT-04/RESEARCH-SCENARIO-131-SHARED-OWNED-RESULT-WORKLOAD.md) for the composed workload, typed caller recovery and generated Rust.
- [RT-04 alternatives](../language-design/RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md).
- [Shared semantics corpus](../language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md), COR-13.
- [Draft Glossary](../../draft/GLOSSARY.md) before changing any identity-bearing evidence field.

## 3. Research questions

### Provider boundary
- What is the authoritative owner of a resource and its current disposition?
- Which provider can report operation completion, cleanup completion, cancellation, consumption and durable commit?
- Can two providers disagree, deliver evidence out of order, or restore snapshots from different generations?
- What does UNKNOWN mean when one provider is unavailable or cannot attest to its observation scope?
- Which operations need one transaction, a coordinator, a reconciliation protocol, or an explicitly weaker guarantee?

### Concurrency and delivery
- What is the linearization point for reservation, effect, terminal result and release?
- Can acknowledgement arrive before cleanup or terminal completion?
- How are duplicate, delayed, reordered and replayed receipts handled?
- Can concurrent observers see incompatible intermediate states?
- How do invocation identity and resource-generation identity prevent stale evidence from releasing a newer reservation?

### Guard coverage
- Which aliases, handles, callbacks, reentrant operations and external producers can create or retain a dependent resource?
- Does a guard cover the resource identity, not merely one wrapper object or argument name?
- Which effect set is covered by the guard?
- What happens when a callback re-enters under a recursive lock or accesses an alias governed by another lock?
- Can observation, close and retirement be made atomic with respect to every producer, or must close remain fallible?

### Restore and recovery
- Which state is durable: reservation, invocation allocation, effect, terminal receipt, cleanup completion, snapshot generation?
- What is reconstructed after process restart, provider failover and snapshot restore?
- How are partially committed effects distinguished from missing terminal evidence?
- What retention/tombstone policy prevents an old receipt from matching a new invocation?

## 4. Preparation of fixtures

Create provider adapters with an intentionally small interface: allocate invocation, reserve role, perform effect, publish terminal disposition, read snapshot, restore snapshot, and reconcile. Model at least two independent providers; do not assume they share a transaction manager.

Prepare scenarios for:
1. successful operation and completion;
2. effect committed, terminal receipt delayed;
3. cleanup acknowledged while still running;
4. duplicate terminal receipt;
5. reordered receipts for the same resource;
6. stale receipt after resource reuse;
7. provider restart before and after effect commit;
8. restore from an older snapshot while a newer result exists;
9. disagreement about live dependent resources;
10. concurrent close and new prepare through different aliases;
11. reentry through callback during guarded close;
12. provider unavailable / receipt unverifiable / incomplete scope;
13. failure while reconciling a multi-resource role pair.

Each scenario must define a happens-before relation, the authoritative evidence source, and the safe fallback state.

## 5. Proposed method

- Specify provider event records and invocation/resource generation keys.
- Draw the state machine and identify every durable transition before coding.
- Use deterministic schedule exploration for small concurrent cases; add fault injection at every durable boundary.
- Preserve provider-specific raw receipts and record the adapter's normalized interpretation separately.
- Compare reconciliation decisions with an independent oracle.
- Test restore into a fresh process and, where applicable, a fresh provider instance.
- Test safety (no premature release or conflicting operation) separately from liveness (eventual reconciliation or explicit unresolved state).
- Never convert missing evidence into successful cleanup.

## 6. Acceptance gates

A bounded positive result requires:
- a documented provider contract and trust boundary;
- unique invocation and resource-generation identity across restart/restore;
- idempotent receipt application;
- no early release on acknowledgement, stale or missing evidence;
- guard coverage for every producer in the declared footprint;
- explicit handling of alias escape, callback reentry and concurrent producers;
- failure-injection evidence at every durable boundary;
- a separate account of unresolved provider disagreement.

## 7. Deliverables and downstream impact

Deliver provider adapter fixtures, event schema, state-machine model, schedule/fault matrix, raw receipts, normalized evidence, replay commands and a limitations report. Update RT-04, RT-16 and RT-19/23 dependencies where evidence changes.

Do not claim distributed atomicity, universal guard completeness or a selected ownership policy from a finite provider fixture.
