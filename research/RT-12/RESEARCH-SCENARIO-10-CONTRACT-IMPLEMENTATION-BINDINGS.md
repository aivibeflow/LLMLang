# Research Scenario 10: Contract Identity and Implementation Binding Snapshots

**Status:** Research / exploratory; not normative.  
**Date:** 2026-11-16  
**Predecessors:** Scenarios 05–09 and Dependency Graph Prototype 01.

## Executive summary

A direct call can depend on an exact implementation hash. That is precise, but couples the caller to one implementation. An alternative is to make the caller depend on an immutable contract and move implementation selection into a separate immutable binding snapshot.

The identities answer different questions:

- **Contract hash:** what behavior is promised at the boundary?
- **Implementation hash:** what exact implementation exists?
- **Caller hash:** what contracts and values does the caller depend on?
- **Binding snapshot root:** which implementation is selected for each context-local binding key?
- **Execution identity:** under which binding snapshot, runtime, and configuration is execution performed?

A swap from implementation I1 to I2 can therefore preserve the caller hash while changing the binding snapshot root. This is safe only if the caller truly relies on the contract rather than undocumented implementation behavior.

## 1. Proposed model

```
Contract {
  canonical_behavior
  types
  effects
  preconditions
  postconditions
}

Implementation {
  body
  dependencies[]
  implements: ContractHash
}

Caller -> ContractHash

Binding {
  key
  contract_hash
  implementation_hash
}

BindingSnapshot {
  root_hash
  bindings[]
  parent_roots[]
}
```

Contracts and implementations are immutable semantic values. An implementation's `implements` edge is a claim/relationship, not proof of conformance. Conformance requires independent evidence bound to the exact implementation hash, contract hash, verifier, assumptions, and configuration.

Binding keys are local to a snapshot/context; they do not imply a global identity for every call site. A snapshot hashes its sorted binding rows and parent roots. Resolution requires both a key and expected contract hash. Missing or ambiguous bindings must fail rather than silently select a default.

## 2. Replacement experiment

Let contract C0 be implemented by I1 and I2. Caller F references C0.

| Item | Production | Candidate |
|---|---|---|
| Caller | F | F |
| Contract | C0 | C0 |
| Selected implementation | I1 | I2 |
| Binding root | B1 | B2 |

Expected:
1. F's semantic hash remains unchanged.
2. I1 and I2 coexist.
3. B1 differs from B2.
4. An execution pinned to B1 cannot silently resolve through B2.
5. Conformance evidence for I1 is not evidence for I2.
6. A caller-local proof against C0 may remain reusable if it relies only on C0's promises.
7. End-to-end tests/builds whose behavior depends on the implementation must include the binding root in their identity.

## 3. Hash boundaries

| Object | Includes | Excludes |
|---|---|---|
| Contract | promised behavior and semantic dependencies | implementation body |
| Implementation | body, dependencies, exact implemented contract(s) | current project selection |
| Caller | body and contracts invoked | selected implementation when abstract dispatch is explicit |
| Binding snapshot | keys and exact contract/implementation pairs | unrelated project metadata |
| Execution identity | program root, binding root, runtime/configuration inputs | mutable unpinned defaults |

If source code directly calls a concrete implementation, its hash remains a direct caller dependency. Contract indirection must be explicit in language semantics; it cannot be inferred from matching signatures.

## 4. Compatibility is not conformance

Four checks must remain distinct:

1. Type/effect compatibility.
2. Behavioral conformance to preconditions, postconditions, invariants, and laws.
3. Context admissibility (platform, tenant, policy, environment).
4. Selection validity and deterministic resolution.

A type check does not prove behavior. A conformance proof does not grant deployment permission. A policy-approved binding does not prove correctness.

## 5. Precedents

- **Bazel toolchains:** rules declare abstract toolchain requirements; resolution selects concrete toolchains according to platform constraints and registrations. The resolved choice affects configured build state. https://bazel.build/docs/toolchains
- **Unison abilities/handlers:** computations declare abstract ability requirements; handlers provide interpretations at a handling boundary. This is a language-level analogy, not the same snapshot design. https://www.unison-lang.org/docs/language-reference/abilities-and-ability-handlers/
- **Nix content-addressed outputs:** derivation identity and output content identity answer different questions; input changes need not always imply different output bytes. https://github.com/NixOS/nix/blob/master/doc/manual/source/store/derivation/outputs/content-address.md

These precedents support the separation pattern, not LLMLang's full business, governance, or verification model.

## 6. Binding scope and late binding

Potential scopes: project, module, deployment, test fixture, tenant, request/session. Scope and precedence must be explicit and deterministic. The resolved binding map—not just unresolved declarations—must be pinned into execution configuration.

For runtime/request-level dispatch, capture the resolved binding for that execution. A mutable registry changing mid-request creates an untracked semantic input. Plugin resolution may need to hash the admissible candidate set and resolution policy, not just the winner.

External services cannot be considered pinned merely because their URL is stable. Version, contract, configuration, and observable external state must be modeled or claims narrowed.

## 7. Verification reuse

| Evidence | Relevant identity |
|---|---|
| Contract well-formedness | Contract + verifier/config |
| Implementation type check | Implementation + contract + type environment |
| Contract conformance | Implementation + contract + assumptions + verifier |
| Caller proof against abstract contract | Caller + contract + proof assumptions |
| Resolved call graph | Program root + binding root |
| End-to-end test | Program + binding + test + runtime/environment |
| Deployment artifact | Program + binding + compiler/toolchain/runtime |

A binding swap invalidates implementation-specific evidence and binding-sensitive results. It need not invalidate a proof about caller logic that depends only on an unchanged contract. Cache keys must encode the actual claim's complete input set.

## 8. Prototype

Added an experimental `BindingSnapshot` model to Prototype 01. It validates semantic kinds, requires the implementation to declare a hash-relevant `implements` edge to the exact contract, canonicalizes rows, resolves by key plus expected contract, and serializes with deterministic JSON/checksum/root validation.

Acceptance tests cover:
- two implementations for one contract;
- caller hash independent of selected implementation;
- changed binding root;
- contract mismatch rejection;
- wrong implementation kind / missing implements edge;
- deterministic round-trip and tamper rejection;
- execution-verification key change across binding roots.

Binding snapshots are currently a separate serialized document, not yet atomically integrated with project snapshot persistence. No runtime dispatcher, overload resolution, compatibility checker, or formal conformance engine is implemented.

## 9. Falsification cases

- Contract omits behavior callers actually rely on.
- Runtime uses hidden mutable binding state.
- Implementation behavior depends on unmodeled tenant/locale/time/external inputs.
- Multiple eligible implementations have no deterministic resolution.
- Contract evolution breaks compatibility but is silently treated as same contract.
- Abstract caller proof is misrepresented as proof of selected implementation.
- Binding changes during one execution.

These cases require stronger contracts, explicit dependencies, deterministic resolution, and claim-specific verification—not merely more hashes.

## 10. Preliminary recommendation

Research direction, not a normative decision:

1. Contracts are first-class immutable semantic values.
2. Implementations are separate immutable values and declare exact contracts.
3. Callers may depend on contracts when abstract dispatch is explicit.
4. Concrete selection lives in immutable binding snapshots.
5. Binding roots enter build/deployment/execution identities when selection can affect behavior.
6. Verification evidence is keyed by the exact contract, implementation, binding, environment, and verifier inputs relevant to its claim.
7. No global stable ID is required for every binding row.

**A caller hash describes what the caller depends on; a binding snapshot describes what the environment supplies for those dependencies.**

## References

1. Bazel toolchains: https://bazel.build/docs/toolchains
2. Unison abilities: https://www.unison-lang.org/docs/language-reference/abilities-and-ability-handlers/
3. Nix content-addressed outputs: https://github.com/NixOS/nix/blob/master/doc/manual/source/store/derivation/outputs/content-address.md

## Public-interface integration (2026-11-24; proposed)

Follow-up (not part of the original experiment): public name resolution should be separately revision-pinned before resolving an operation/provider. A stable name is a discovery/continuity handle, not the call target. Compare the earlier contract-keyed snapshot with an OpHash-keyed provider binding; different operations can share ContractHash but differ in signature or context. Validate the implementation's own contract and its refinement of the public contract, including exact profile and assumptions. Preserve conditional caller proofs independently of closed executable evidence.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
