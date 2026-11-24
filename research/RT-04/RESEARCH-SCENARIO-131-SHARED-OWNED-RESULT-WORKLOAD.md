# Research Scenario 131 — A Shared Ownership and Cleanup Workload

**Status:** differential execution of a bounded source fixture across two transfer rules

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

How does returning an owned resource across fallible cleanup change admission of a later foreign call? COR-13 specifies a common workload. This experiment connects the owned-result model to an independently evaluated role guard across one callee and an aliased call site. [Shared corpus](../RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md#cor-13-follow-up-on-foreign-resource-lifetimes) · [Owned result matching](RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md)

## Common source and compared execution

The callee acquires an outer backup and an inner scratch value. It attempts to move the backup on one Boolean branch and returns a domain error on the other. The caller records the outcome and checks a second proposal through aliases.

```python
outcome = make(a, b, wants_value)
source_alias = c
destination_alias = d
propose(outcome, source_alias, destination_alias)
```

The source adapter validates the fixed callee body and resolves the caller's local bindings. Inputs may give distinct names the same underlying resource identity. Each release can succeed, consume on error, retain on error, or remain indeterminate. The proposal checks a shared source and an exclusive destination. An acquired backup or a reconciliation obligation for it still contributes its role footprint. A scratch obligation is forwarded separately and has no reservation over the connections. [Source fixture and composed evaluator](../PROTOTYPES/RT-04-01/rt04_shared_owned_workload.py) · [Multi-resource roles](../RT-13/RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md)

One execution composes the existing owned-call evaluator and role checker. The other implements the transfer, release transitions, and role-conflict predicate directly. They share the parsed fixture representation. The comparison checks the result tag and obligations, ordered events, domain and cleanup diagnostics, the proposal decision, and reservations at the boundary. [Direct transition evaluator](../PROTOTYPES/RT-04-01/rt04_shared_owned_transitions.py) · [Differential tests](../PROTOTYPES/RT-04-01/test_rt04_shared_owned_workload.py)

## Results

The corpus assigns four argument slots to three resource identities, varies the body branch, and declares four outcomes for each release. It counts input assignments even when a release branch is skipped. The two transfer orders give 5,184 total inputs. Both executions agree on every observation. Their output shapes also match the static inference, with 14 shapes before cleanup and 20 after cleanup. Exact forwarding can retain each shape with a tagged payload. A diagnostics-only error carrier loses obligations on some shapes. [Shape matcher](../PROTOTYPES/RT-04-01/rt04_owned_call_match.py)

| Transfer order | First call refused | Second call refused | Second call started | Conflicting second calls admitted by erasing roles on a first-call error |
|---|---:|---:|---:|---:|
| Before cleanup | 864 | 1,296 | 432 | 600 |
| After cleanup | 864 | 1,116 | 612 | 420 |

A specific input starts `a → b`, tries to return it, then proposes `c → b`. The scratch release reports a consuming error. With transfer before cleanup, the error carries the owned backup and the second proposal is refused. With transfer after cleanup, the failed scratch release prevents transfer and the callee attempts to release the backup. A consuming error on that release leaves both diagnostics and lets the proposal start. A retaining or indeterminate release preserves the older role footprint and the proposal is refused. Changing an alias in the source can also change admission while keeping the caller's other bindings fixed. [Discriminating fixtures](../PROTOTYPES/RT-04-01/test_rt04_shared_owned_workload.py)

The additional admissions under staged transfer measure when the older reservation can be released. A caller that needs the original value on cleanup failure observes a different outcome. This trade-off belongs in the comparison of transfer rules.

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_shared_owned_workload.py' -v
```

The runs used Python 3.12.14. The parser validates a fixed source shape, the outcome contracts are fixture inputs, and admission is followed by a modeled successful acquisition. The native SQLite probe in Scenario 128 separately validates consumption on a reported backup finish error. General source lowering, typed branch-specific control flow across profiles, native integration, and wider FFI contracts remain open. [Native finish evidence](../RT-13/RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md)
