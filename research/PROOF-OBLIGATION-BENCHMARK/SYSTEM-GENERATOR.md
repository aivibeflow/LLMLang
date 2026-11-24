# Structural and system contract generator v1

Status: proposed, synthetic finite development profile, not independently adjudicated or normative LLMLang semantics. Supports [#402](https://github.com/aivibeflow/LLMLang/issues/402), [#403](https://github.com/aivibeflow/LLMLang/issues/403), #394 and RT-33.

## Seven parameterized families

| Family | Distinct property | Scope and bound |
|---|---|---|
| heap_separation | Disjoint ownership regions, authorized graph mutation, frame | Two roots and two target nodes; depth 5 |
| graph_gc | Transitive reachability, reachable and unreachable cycles | Five nodes, fixed graph, mutable roots and live set; depth 4 |
| partition_retry | Network partition, lost acknowledgement, crash and durable deduplication | One request, abstract network and receiver, depth 6 |
| quorum | Non-equivocation, majority and agreement | Three voters, two values, depth 6; no leader election or liveness |
| fulfillment | Inventory, payment and shipping assume-guarantee interaction | One order, atomic component actions, cancellation and retry; depth 5 |
| rolling_upgrade | Version skew, explicit false/default preservation and compatibility | Two endpoints, one pending message, depth 5 |
| ffi_buffer | Lifetime, capability, write bounds and zero-length effect | Two-cell abstract external buffer, depth 4; not actual FFI/ABI |

The [profile](generative/system/profile.json) uses integer-valued explicit state, named atomic actions and event observations. Breadth-first exploration visits reachable states once at minimum depth and checks every outgoing edge before the depth limit. This is sound for the stated local Markovian predicates, not for arbitrary history properties. No state-space reduction across different state identities. Resource caps fail closed. Each family has a reference, mutation and alternative (some only implementation rewrites). The separately written relational oracle checks state frames, observations and system invariants; graph collection uses an adjacency-matrix closure rather than the candidate DFS. Failed obligations retain a shortest reachable edge witness, replayed against the exact candidate. A bounded pass is not a proof. Individual obligations without a distinguishing mutation are not deemed fully covered.

## Reproduce

```sh
python research/PROOF-OBLIGATION-BENCHMARK/generative/system/test_system.py
python research/PROOF-OBLIGATION-BENCHMARK/generative/system/generate.py --count 140 --seed 42
```

Optional --output gold.jsonl includes results; --blind-output stage-b.jsonl contains initial state, action alphabet, scope/depth and contract only, without verdicts or candidate code. Public development templates are not a private holdout. The summary includes code/profile hashes, corpus hash, checked reachable-state and edge counts (sums over variants; not distinct across variants), family and mutation-obligation counts. Parameters are mostly integer origins/quantities, not independent semantic classes.

## Relationship to LLMLang and limits

These fixtures motivate rather than settle RT-03/RT-04 semantics. See [RT-03](../RT-03/CORE-LANGUAGE-SEMANTICS.md), [effect/ownership alternatives](../RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [durable invocation results](../RT-10/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md), [wire schema evolution](../RT-18/RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md), and [business rule binding](../RT-02/RESEARCH-SCENARIO-13-MULTI-LEVEL-BUSINESS-RULE-AND-IMPLEMENTATION-BINDING.md) at baseline 991c053ffbc9e3ed0885763e3034f0d3c9354c2a. No source correspondence or proof is inherited.

Remaining: arbitrary heap topology, aliasing/permissions and formal separation logic; consensus leader election, partitions with multiple replicas and eventual delivery; real foreign memory/ABI; history-dependent and unbounded temporal properties; weak memory, higher-order/inductive/coinductive semantics; reviewed form/domain applicability and independently derived formal oracles. Registry entries remain candidates, not adjudicated coverage. See #404, #395 and #397.
